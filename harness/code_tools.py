"""Read-only code-inspection tools over one source file, for agents on both
sides: the fix loop (harness/generate.py) and the evidence agent
(eval/evidence_agent.py).

A leaf module, like status.py, and the second deliberate exception to "eval
never imports harness": this is a security boundary, and a boundary kept in
two copies drifts apart. It imports nothing from either side.

The boundary, outermost first:

- The agent never sees the real file. ReadOnlySource writes a *copy* into a
  fresh temp directory outside the repo, then makes the file and the
  directory read-only. inputs/<name>/world.html is not reachable through
  these tools at all, and nothing here can write — the model-generated file
  being inspected is untrusted, and so is whatever an agent decides to run.
- `shell` is not a shell. No interpreter is started (no `shell=True`), so
  `;`, `&&`, `$(…)`, backticks, globbing and redirection have no meaning;
  the ones that look like control operators are refused outright rather
  than passed through as literal text. `|` pipelines are built by hand.
- Every stage's program is on an allowlist of text readers, and the
  flags that would make one write (`sed -i`, `sort -o`, …) are refused.
- Path arguments may not escape the temp directory (`/…`, `~…`, `..`).
- The environment is scrubbed (fixed PATH, no HOME, no API keys).

There is deliberately no way to *run* the inspected JavaScript: evaluating
untrusted generated code is a different risk class from reading it.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

MAX_OUTPUT_CHARS = 12_000  # per call; the agent pages with read_lines / head / sed ranges
MAX_READ_LINES = 400  # per read_lines call, same reason
SHELL_TIMEOUT_S = 15
FILE_NAME = "world.html"

_ALLOWED = {"grep", "egrep", "head", "tail", "wc", "nl", "cut", "sort", "uniq", "tr", "cat", "sed"}
_CONTROL = {";", "&", "&&", "||", ">", ">>", "<", "<<", "(", ")", "&>", ">&", "|&"}
_SED_SCRIPT = re.compile(r"^(\d+|\$)(,(\d+|\$))?p$")
_SAFE_ENV = {"PATH": "/usr/bin:/bin", "LC_ALL": "C"}


DEPS_DIR = "deps"


def dep_path(url: str) -> str:
    """deps/<host>/<path> for a fetched module URL — readable, and never able
    to climb out of the copy's directory whatever the URL contains."""
    from urllib.parse import urlsplit

    parts = urlsplit(url)
    segments = [parts.netloc, *parts.path.split("/")]
    safe = [re.sub(r"[^A-Za-z0-9._@-]", "_", seg) for seg in segments if seg and seg not in (".", "..")]
    return "/".join([DEPS_DIR, *safe]) or f"{DEPS_DIR}/module.js"


class ReadOnlySource:
    """A read-only temp copy of one source text (as world.html), plus any
    extra files (the modules the page imported, under deps/), and the tools
    over them.

    Line numbers in every tool's output are the files' own, so a quote an
    agent finds can be checked against the real file afterwards.
    """

    def __init__(self, text: str, extra: dict[str, str] | None = None) -> None:
        self._dir = Path(tempfile.mkdtemp(prefix="wb-source-"))
        self._files: dict[str, list[str]] = {}
        self._unlock()
        for rel, body in (extra or {}).items():
            self._put(rel, body)
        self._put(FILE_NAME, text)
        self._lock()

    # -- lifecycle ---------------------------------------------------------

    def _unlock(self) -> None:
        for root, dirs, files in os.walk(self._dir):
            Path(root).chmod(stat.S_IRWXU)
            for f in files:
                (Path(root) / f).chmod(stat.S_IRUSR | stat.S_IWUSR)

    def _lock(self) -> None:
        for root, dirs, files in os.walk(self._dir, topdown=False):
            for f in files:
                (Path(root) / f).chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            Path(root).chmod(stat.S_IRUSR | stat.S_IXUSR)

    def _put(self, rel: str, text: str) -> None:
        path = self._dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self._files[rel] = text.split("\n")

    @property
    def extra_paths(self) -> list[str]:
        return [rel for rel in self._files if rel != FILE_NAME]

    def refresh(self, text: str) -> None:
        """Replace world.html's contents (the fix loop, after an edit lands)."""
        self._unlock()
        self._put(FILE_NAME, text)
        self._lock()

    def close(self) -> None:
        if self._dir.exists():
            self._unlock()
            shutil.rmtree(self._dir, ignore_errors=True)

    def __enter__(self) -> ReadOnlySource:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- tools -------------------------------------------------------------

    def grep(self, pattern: str, ignore_case: bool = False, context: int = 0, file: str = FILE_NAME) -> str:
        """Python regex over one file (or every file with file="*"); matches as
        `N: line` for world.html and `path:N: line` for anything else."""
        try:
            rx = re.compile(pattern, re.I if ignore_case else 0)
        except re.error as exc:
            return f"ERROR: bad regex ({exc})"
        targets = list(self._files) if file == "*" else [file]
        missing = [t for t in targets if t not in self._files]
        if missing:
            return f"ERROR: no file {missing[0]!r} (files: {', '.join(self._files)})"
        context = max(0, min(int(context), 20))
        blocks, total = [], 0
        for rel in targets:
            lines = self._files[rel]
            hits = [i for i, line in enumerate(lines) if rx.search(line)]
            total += len(hits)
            shown: dict[int, None] = {}
            for i in hits:
                for j in range(max(0, i - context), min(len(lines), i + context + 1)):
                    shown.setdefault(j, None)
            prefix = "" if rel == FILE_NAME else f"{rel}:"
            blocks.extend(f"{prefix}{j + 1}: {lines[j]}" for j in sorted(shown))
        if not total:
            return "no matches"
        return _clip(f"{total} matching line(s)\n" + "\n".join(blocks))

    def read_lines(self, start: int, end: int, file: str = FILE_NAME) -> str:
        """Lines start..end (1-based, inclusive) of one file as `N: line`."""
        if file not in self._files:
            return f"ERROR: no file {file!r} (files: {', '.join(self._files)})"
        lines = self._files[file]
        total = len(lines)
        start = max(1, int(start))
        end = min(total, int(end), start + MAX_READ_LINES - 1)
        if start > total:
            return f"ERROR: {file} has only {total} lines"
        body = "\n".join(f"{n}: {lines[n - 1]}" for n in range(start, end + 1))
        return _clip(f"{file} lines {start}-{end} of {total}\n{body}")

    def shell(self, command: str) -> str:
        """Run an allowlisted read-only pipeline in the copy's directory."""
        try:
            stages = _parse_pipeline(command)
        except ValueError as exc:
            return f"REFUSED: {exc}"
        procs: list[subprocess.Popen] = []
        try:
            prev = None
            for argv in stages:
                proc = subprocess.Popen(
                    argv,
                    cwd=self._dir,
                    env=_SAFE_ENV,
                    stdin=prev.stdout if prev else subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                if prev and prev.stdout:
                    prev.stdout.close()  # so an early-exiting reader (head) ends the writer
                procs.append(proc)
                prev = proc
            out, _ = procs[-1].communicate(timeout=SHELL_TIMEOUT_S)
            for proc in procs[:-1]:
                proc.wait(timeout=SHELL_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            for proc in procs:
                proc.kill()
            return f"ERROR: timed out after {SHELL_TIMEOUT_S}s"
        except FileNotFoundError as exc:
            return f"ERROR: {exc}"
        code = procs[-1].returncode
        out = out or ""
        if code not in (0, 1) or (code == 1 and out):  # grep exits 1 on "no match": not an error
            out = f"{out}\n[exit {code}]"
        return _clip(out.strip() or "(no output)")

    def tools(self) -> list:
        """The three tools as LangChain tools bound to this copy."""
        from langchain_core.tools import tool

        source = self

        @tool
        def grep(pattern: str, ignore_case: bool = False, context: int = 0, file: str = FILE_NAME) -> str:
            """Search a file with a Python regex; every match as `N: line`, with `context`
            lines around each. `file` defaults to world.html; pass a deps/... path to search an
            imported module, or "*" to search every file."""
            return source.grep(pattern, ignore_case, context, file)

        @tool
        def read_lines(start: int, end: int, file: str = FILE_NAME) -> str:
            """Read lines start..end (1-based, inclusive) of a file (default world.html, or a
            deps/... path) as `N: line`. Page through long ranges with several calls."""
            return source.read_lines(start, end, file)

        @tool
        def shell(command: str) -> str:
            """Run a read-only command pipeline in the directory holding world.html (and deps/,
            the modules the page imported). Allowed programs: grep, egrep, head, tail, wc, nl,
            cut, sort, uniq, tr, cat, and `sed -n 'A,Bp'`. Pipes `|` work; redirection, `;`,
            `&&` and subshells don't. Example: grep -rn "from 'three'" deps | head"""
            return source.shell(command)

        return [grep, read_lines, shell]


def _clip(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + f"\n… [truncated at {MAX_OUTPUT_CHARS} chars — narrow the search or page]"


def _parse_pipeline(command: str) -> list[list[str]]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars="|;&<>()")
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError as exc:
        raise ValueError(f"could not parse command ({exc})") from exc
    if not tokens:
        raise ValueError("empty command")
    stages: list[list[str]] = [[]]
    for tok in tokens:
        if tok == "|":
            stages.append([])
        elif tok in _CONTROL or tok.startswith(("|", ";", "&", ">", "<")):
            raise ValueError(f"{tok!r} is not allowed — only `|` pipelines of allowed programs")
        else:
            stages[-1].append(tok)
    for argv in stages:
        _check_stage(argv)
    return stages


def _check_stage(argv: list[str]) -> None:
    if not argv:
        raise ValueError("empty pipeline stage")
    prog = argv[0]
    if prog not in _ALLOWED:
        raise ValueError(f"{prog!r} is not allowed (allowed: {', '.join(sorted(_ALLOWED))})")
    for arg in argv[1:]:
        if arg.startswith(("/", "~")) or arg == ".." or arg.startswith("../") or "/../" in arg:
            raise ValueError(f"path {arg!r} is outside the source directory")
    if prog == "sed":
        flags = [a for a in argv[1:] if a.startswith("-")]
        scripts = [a for a in argv[1:] if not a.startswith("-") and a != FILE_NAME]
        scripts = [a for a in scripts if not a.startswith(DEPS_DIR + "/")]
        if flags != ["-n"] or len(scripts) != 1 or not _SED_SCRIPT.match(scripts[0]):
            raise ValueError("sed is only allowed as: sed -n 'A,Bp' world.html")
    if prog == "sort" and any(a.startswith(("-o", "--output")) for a in argv[1:]):
        raise ValueError("sort -o writes a file")
    if prog == "uniq" and len([a for a in argv[1:] if not a.startswith("-")]) > 1:
        raise ValueError("uniq with an output file writes a file")
    if prog in ("grep", "egrep") and any(a.startswith(("-f", "--file")) for a in argv[1:]):
        raise ValueError("grep -f is not needed here; pass the pattern directly")
