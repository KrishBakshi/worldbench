"""Static checks for a generated world.html — the class of failure the
browser never gets a clean shot at.

Two tags, because they need different repairs:

``[structure]`` — the *document* is damaged. A model that hits a length cap,
panics, and *restarts* will still emit a closing ``</html>``, so
``harness.model_call._looks_complete`` treats the file as finished. What it
actually wrote is two drafts glued together: an unfinished
``const w = Math.max(8*`` jammed into a markdown fence and a second
``<!DOCTYPE html>``. Patching cannot unglue two files, so the fix node
rewrites the whole document for these.

``[syntax]`` — the document is fine but a script doesn't parse. Found by a
real JS parser (``node --check``), never by counting characters, and always
carrying a ``(line N; see also line …)`` location so the fix node can send a
small excerpt and patch it with ``str_replace``.

Why a real parser: the old check counted braces character by character and
didn't understand comments. In a real run it reported
``last <script> has 1 extra '{'`` for three straight rounds against a script
that parsed cleanly — an apostrophe in ``// Swamp on jungle's far side``
opened a phantom string. The fix node believed it, got the whole 54KB file,
was told to rewrite it, and the provider timed out (504) while the model
built that rewrite as one silent tool-call argument. A false error is worse
than no error: it costs every round it survives. So the parser is the
authority on whether a script parses; the lexer below is only used to
*localize* an error the parser already confirmed (``Unexpected end of
input`` points at the last line, never at the missing ``}``).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

_FENCE_RE = re.compile(r"```")
_SCRIPT_OPEN_RE = re.compile(r"<script\b", re.I)
_SCRIPT_CLOSE_RE = re.compile(r"</script\s*>", re.I)
_SCRIPT_RE = re.compile(r"<script\b([^>]*)>(.*?)</script\s*>", re.I | re.S)
_TYPE_ATTR_RE = re.compile(r"""\btype\s*=\s*["']?([^"'\s>]+)""", re.I)
_SRC_ATTR_RE = re.compile(r"\bsrc\s*=", re.I)
_JS_TYPES = {"", "module", "text/javascript", "application/javascript", "text/ecmascript", "application/ecmascript"}
_DOCTYPE_RE = re.compile(r"<!DOCTYPE\s+html\b|<html\b", re.I)
_HTML_CLOSE_RE = re.compile(r"</html\s*>", re.I)

# Phrases that only appear when the model started talking *about* the file
# instead of writing it — seen for real in a mashed continuation.
_LEAK_RE = re.compile(
    r"Incomplete cut-off|Let me provide a clean|The key issue is|"
    r"I need to (?:finish|output)|Key areas still missing|"
    r"Output ONLY the complete|no prose, no commentary|"
    r"Let's write a clean continuation",
    re.I,
)

MAX_FENCE_REPORTS = 3
NODE_CHECK_TIMEOUT_S = 30
_NODE = shutil.which("node")


def lint_world_html(html: str) -> list[str]:
    """Return ``[structure] …`` and ``[syntax] …`` findings. Empty list means
    the document is one finished HTML file whose scripts all parse (runtime
    errors are not this function's job — see ``harness.browser_debug``)."""
    if not html or not html.strip():
        return ["[structure] file is empty"]
    return _structure_findings(html) + syntax_findings(html)


def has_syntax_error(findings: list[str]) -> bool:
    return any(f.startswith("[syntax]") for f in findings)


def _structure_findings(html: str) -> list[str]:
    errors: list[str] = []
    if not _DOCTYPE_RE.search(html[:800]):
        errors.append("[structure] file does not start with <!DOCTYPE html> / <html>")
    if not _HTML_CLOSE_RE.search(html[-4000:]):
        errors.append("[structure] missing </html> closing tag — generation looks truncated")

    fence_hits = 0
    for i, line in enumerate(html.splitlines(), 1):
        if not _FENCE_RE.search(line):
            continue
        fence_hits += 1
        if fence_hits > MAX_FENCE_REPORTS:
            continue
        snippet = line.strip()
        if len(snippet) > 100:
            snippet = snippet[:100] + "…"
        errors.append(
            f"[structure] markdown fence leaked into the file at line {i}: {snippet!r}. "
            "The generator restarted mid-document (two drafts glued together). "
            "Rewrite one complete HTML file; do not patch around the fence."
        )
    extra_fences = fence_hits - MAX_FENCE_REPORTS
    if extra_fences > 0:
        errors.append(f"[structure] …and {extra_fences} more markdown fence(s)")

    opens = len(_SCRIPT_OPEN_RE.findall(html))
    closes = len(_SCRIPT_CLOSE_RE.findall(html))
    if opens == 0:
        errors.append("[structure] no <script> tag — the page has nothing to run")
    elif opens != closes:
        errors.append(
            f"[structure] <script> tags are unbalanced ({opens} open, {closes} close). "
            "A draft was cut off before </script>, or the closer was written as "
            "something like '*/script />'."
        )

    leak = _LEAK_RE.search(html)
    if leak:
        line_no = html[: leak.start()].count("\n") + 1
        errors.append(
            f"[structure] model commentary leaked into the file at line {line_no}: "
            f"{leak.group(0)!r}. That text is not HTML/JS — the model broke out of "
            "the file and started explaining. Rewrite the complete file with no prose."
        )
    return errors


# --------------------------------------------------------------------------
# [syntax]: real parser first, lexer only to localize what it confirmed.
# --------------------------------------------------------------------------


@dataclass
class _Script:
    body: str
    first_line: int  # file line holding the body's first character
    module: bool


def _inline_scripts(html: str) -> list[_Script]:
    scripts = []
    for m in _SCRIPT_RE.finditer(html):
        attrs, body = m.group(1), m.group(2)
        type_m = _TYPE_ATTR_RE.search(attrs)
        script_type = type_m.group(1).lower() if type_m else ""
        # importmap/shader/json blocks aren't JS; a src= script's body is ignored by the browser.
        if script_type not in _JS_TYPES or _SRC_ATTR_RE.search(attrs) or not body.strip():
            continue
        scripts.append(_Script(body, html[: m.start(2)].count("\n") + 1, script_type == "module"))
    return scripts


def _node_check(body: str, module: bool) -> tuple[int, str] | None:
    """(script-relative line, message) for the first SyntaxError, or None if
    it parses. `.mjs` vs `.cjs` mirrors the browser: a module may `import`,
    a classic script may not."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / ("script.mjs" if module else "script.cjs")
        path.write_text(body, encoding="utf-8")
        proc = subprocess.run(
            [_NODE, "--check", str(path)], capture_output=True, text=True, timeout=NODE_CHECK_TIMEOUT_S, check=False
        )
    if proc.returncode == 0:
        return None
    # node prints `<path>:<line>`, the source line, a caret line, then `SyntaxError: …`.
    stderr = proc.stderr
    line_m = re.search(re.escape(str(path)) + r":(\d+)", stderr)
    msg_m = re.search(r"^(SyntaxError: .*)$", stderr, re.M)
    line = int(line_m.group(1)) if line_m else 0
    msg = msg_m.group(1).strip() if msg_m else (stderr.strip().splitlines() or ["SyntaxError"])[-1]
    return line, msg


def syntax_findings(html: str) -> list[str]:
    """One ``[syntax]`` finding per inline script that fails to parse.

    Without node on PATH this falls back to the lexer's bracket balance —
    still comment/string/regex-aware, so far better than the old character
    count, but worded as a hint since it isn't a parser. The browser's own
    SyntaxError (browser_debug) is the backstop either way.
    """
    findings = []
    for script in _inline_scripts(html):
        if _NODE:
            result = _node_check(script.body, script.module)
            if result is None:
                continue
            rel_line, msg = result
        else:
            if _unclosed_brackets(script.body) is None:
                continue
            rel_line, msg = 0, "SyntaxError (bracket balance, no JS parser available): Unexpected end of input"
        findings.append(_describe_syntax_error(script, rel_line, msg))
    return findings


def _describe_syntax_error(script: _Script, rel_line: int, msg: str) -> str:
    lines = script.body.split("\n")

    def to_file(n: int) -> int:
        return script.first_line + n - 1

    def quote(n: int) -> str:
        return repr(lines[n - 1].strip()[:100])

    end_of_input = "end of input" in msg or not rel_line

    # The parser's own line is exact for most errors, but not for a missing or
    # extra brace: `Unexpected end of input` points at the last line, and
    # inside a class a missing `}` makes the parser read the next method
    # header `foo() {` as a call plus a stray `{` — reported dozens of lines
    # past the real gap. So ask the lexer where pairing went wrong before the
    # reported line. Mid-file an open stack is normal, so only an end-of-input
    # error may use "this opener was never closed".
    loc = _confirmed_location(script, rel_line, end_of_input)
    if loc is None:
        if not end_of_input:
            return f"[syntax] {msg} (line {to_file(rel_line)})"
        last = next((i for i in range(len(lines), 0, -1) if lines[i - 1].strip()), len(lines))
        return (
            f"[syntax] {msg} — the script ends mid-statement or inside an unterminated "
            f"string/template: {quote(last)} (line {to_file(last)})"
        )

    if loc.kind == "extra":
        detail = (
            f"the '}}' on line {to_file(loc.closer)} is more indented than the '{{' it closes "
            f"(line {to_file(loc.opener)}, {quote(loc.opener)}) — it is most likely an extra '}}' "
            f"that ends that block early. Remove it"
        )
    elif loc.kind == "mispaired":
        detail = (
            f"the '{{' opened on line {to_file(loc.opener)} ({quote(loc.opener)}) is closed by the "
            f"'}}' on line {to_file(loc.closer)}, whose indentation belongs to an outer block — so a "
            f"'}}' is missing, most likely just before line {to_file(loc.suspect)}. Add it"
        )
    elif loc.kind == "deeper":
        detail = (
            f"{quote(loc.suspect)} on line {to_file(loc.suspect)} is nested one block deeper than "
            f"every earlier declaration at its indentation, i.e. still inside the block opened on "
            f"line {to_file(loc.opener)} ({quote(loc.opener)}) — that block is most likely missing "
            f"its '}}' just before line {to_file(loc.suspect)}. Add it"
        )
    else:  # unclosed
        detail = (
            f"the bracket opened on line {to_file(loc.opener)} ({quote(loc.opener)}) is never closed; "
            f"it most likely should close before line {to_file(loc.suspect)}. Add the closer"
        )
    if loc.confirmed:
        detail += " (verified: with that one change the script parses)"
    where = "" if end_of_input else f" at line {to_file(rel_line)}, but the real cause is earlier:"
    see = [n for n in dict.fromkeys([loc.opener, loc.closer, None if end_of_input else rel_line]) if n and n != loc.suspect]
    see_text = f"; see also {', '.join(f'line {to_file(n)}' for n in see)}" if see else ""
    return (
        f"[syntax] {msg}{where} {detail}; do not rewrite the file. "
        f"(line {to_file(loc.suspect)}{see_text})"
    )


MAX_LOCATION_TRIALS = 8


def _confirmed_location(script: _Script, rel_line: int, end_of_input: bool) -> _BraceLocation | None:
    """First brace candidate the parser agrees with.

    Indentation is only a signal of intent, and valid code with sloppy
    indentation emits false ones (seen in two real worlds — correct code,
    earlier than any real gap). A false lead handed
    to the fix node is exactly the failure this module exists to prevent, so
    each candidate's one-brace repair is applied to a scratch copy and
    re-parsed: kept only if the script then parses, or (mid-file) the
    parser gets strictly further than before. Without node the first
    candidate is returned unconfirmed.

    Earliest-first, not nearest-to-the-error-first: tried both over 190
    synthetic single-brace breakages of the 17 real worlds in inputs/.
    Earliest put 90/91 missing-`}` and 97/102 extra-`}` cases inside a fix
    window; nearest-first was no better on extra and pulled the
    real-run missing-`}` case from its true line (393) to 444. The
    residual ambiguity is real — with an extra `}` at 222, removing a
    correct `}` at 99 rebalances the script too — which is why the finding
    always also names the parser's own line.
    """
    lines = script.body.split("\n")
    if end_of_input:
        candidates = _brace_candidates(script.body)
    else:
        candidates = (c for c in _brace_candidates("\n".join(lines[:rel_line])) if c.kind != "unclosed")
    for trial, loc in enumerate(candidates):
        if not _NODE:
            return loc
        if trial >= MAX_LOCATION_TRIALS:
            return None
        result = _node_check(_apply_candidate(lines, loc), script.module)
        if result is None or (not end_of_input and "end of input" not in result[1] and result[0] > rel_line):
            loc.confirmed = True
            return loc
    return None


def _apply_candidate(lines: list[str], loc: _BraceLocation) -> str:
    patched = list(lines)
    if loc.kind == "extra":
        text = patched[loc.closer - 1]
        at = text.index("}")
        patched[loc.closer - 1] = text[:at] + text[at + 1 :]
    else:
        patched.insert(loc.suspect - 1, loc.closer_char)
    return "\n".join(patched)


_REGEX_PREV_WORDS = frozenset(
    "return typeof case do else in of new delete void throw yield await instanceof".split()
)
_REGEX_PREV_PUNCT = set("(,=:[!&|?{};+-*%<>~^")
_OPEN = {"(": ")", "[": "]", "{": "}"}
_CLOSE = {v: k for k, v in _OPEN.items()}


def _brackets(src: str) -> list[tuple[str, int]]:
    """Every (bracket, line) in `src`, skipping comments, strings, template
    literal text and regex literals — the things that fooled the old counter."""
    out: list[tuple[str, int]] = []
    i, n, line = 0, len(src), 1
    template_depth: list[int] = []  # one entry per open `${`, counting `{` nested inside it
    prev = ""

    def scan_template(i: int) -> tuple[int, bool]:
        """From just inside a backtick; returns (index after, entered `${`)."""
        nonlocal line
        while i < n:
            c = src[i]
            if c == "\\":
                i += 2
                continue
            if c == "\n":
                line += 1
            if c == "`":
                return i + 1, False
            if c == "$" and src.startswith("${", i):
                return i + 2, True
            i += 1
        return n, False

    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        if c in " \t\r":
            i += 1
            continue
        if src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if src.startswith("/*", i):
            j = src.find("*/", i + 2)
            end = n if j < 0 else j + 2
            line += src.count("\n", i, end)
            i = end
            continue
        if c in "'\"":
            j = i + 1
            while j < n and src[j] != c and src[j] != "\n":
                j += 2 if src[j] == "\\" else 1
            i, prev = j + 1, "str"
            continue
        if c == "`":
            i, entered = scan_template(i + 1)
            if entered:
                template_depth.append(0)
            prev = "str"
            continue
        if c == "/" and (prev == "" or prev in _REGEX_PREV_PUNCT or prev in _REGEX_PREV_WORDS):
            j, in_class = i + 1, False
            while j < n and src[j] != "\n":
                ch = src[j]
                if ch == "\\":
                    j += 2
                    continue
                if ch == "[":
                    in_class = True
                elif ch == "]":
                    in_class = False
                elif ch == "/" and not in_class:
                    break
                j += 1
            j += 1
            while j < n and (src[j].isalnum()):
                j += 1
            i, prev = j, "regex"
            continue
        if c.isalnum() or c in "_$":
            j = i
            while j < n and (src[j].isalnum() or src[j] in "_$"):
                j += 1
            prev = src[i:j]
            i = j
            continue
        if c == "{" and template_depth:
            template_depth[-1] += 1
        if c == "}" and template_depth:
            if template_depth[-1] == 0:
                template_depth.pop()
                i, entered = scan_template(i + 1)
                if entered:
                    template_depth.append(0)
                prev = "str"
                continue
            template_depth[-1] -= 1
        if c in _OPEN or c in _CLOSE:
            out.append((c, line))
        prev = c
        i += 1
    return out


def _unclosed_brackets(src: str) -> tuple[str, int] | None:
    stack: list[tuple[str, int]] = []
    for ch, line in _brackets(src):
        if ch in _OPEN:
            stack.append((ch, line))
        elif stack and stack[-1][0] == _CLOSE[ch]:
            stack.pop()
    return stack[-1] if stack else None


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


# Only declarations that style guides (and every model in inputs/) keep at a
# fixed nesting level. `const`/`let` would misfire on flat code: some models
# write function bodies at column 0, so a body's `const` looks one level
# "too deep" next to the `function` line above it.
_DECL_RE = re.compile(r"(?:export\s+)?(?:async\s+)?(?:function|class)\b")


@dataclass
class _BraceLocation:
    kind: str  # "mispaired" (missing `}`), "extra" (extra `}`), "deeper" (missing `}`, flat code), "unclosed"
    opener: int
    closer: int | None
    suspect: int  # where the fix most likely goes — the line the fix window centres on
    closer_char: str = "}"  # what repairs it, for kinds that insert one
    confirmed: bool = False  # the parser accepted the one-brace repair (see _confirmed_location)


def _brace_candidates(src: str):
    """Where a brace went missing (or extra), from the code's own intent —
    yielded earliest-first; the caller keeps the first one the parser agrees
    with.

    A missing `}` doesn't show up where it's missing: every later `}` pairs
    one level too shallow, and the stack only ends up holding the *outermost*
    block. Signals:

    - `mispaired`: a `}` less indented than the `{` it paired with — pairing
      slipped a level; the missing `}` belongs where that opener's body first
      dedents back to the opener's level.
    - `extra`: a `}` *more* indented than its `{` — it closed an outer block
      early.
    - `deeper`: a `function`/`class` at an indent already seen at a shallower
      brace depth — for unindented code (seen in real worlds) where the
      indent signals can't fire.
    - `unclosed`: last resort — the innermost still-open bracket.
    """
    lines = src.split("\n")
    tokens = _brackets(src)
    stack: list[tuple[str, int, int]] = []  # (bracket, line, line whose indent it answers to)
    depths_at_indent: dict[int, set[int]] = {}
    last_paren: tuple[int, int] | None = None  # (line a `)` closed on, line its `(` opened on)
    ti = 0
    for ln in range(1, len(lines) + 1):
        text = lines[ln - 1]
        stripped = text.strip()
        if _DECL_RE.match(stripped):
            depth = sum(1 for t in stack if t[0] == "{")
            seen = depths_at_indent.setdefault(_indent(text), {depth})
            if depth > max(seen):
                opener = next(t for t in reversed(stack) if t[0] == "{")
                yield _BraceLocation("deeper", opener[2], None, ln)
            seen.add(depth)  # rejected, so this nesting is legitimate here
        while ti < len(tokens) and tokens[ti][1] == ln:
            ch = tokens[ti][0]
            ti += 1
            if ch in _OPEN:
                # `if (a ||\n    b) {` — the `{` sits on a continuation line
                # indented deeper than the statement; it answers to the
                # line the `(` opened on, or every correct block like this
                # would look mis-paired.
                anchor = last_paren[1] if ch == "{" and last_paren and last_paren[0] == ln else ln
                stack.append((ch, ln, anchor))
                last_paren = None
                continue
            last_paren = None
            if not stack:
                continue
            opener_ch, opener_line, anchor = stack.pop()
            if ch == ")" and opener_ch == "(":
                last_paren = (ln, opener_line)
            if ch != "}" or opener_ch != "{":
                continue
            if not stripped.startswith("}") or opener_line == ln:
                continue  # inline object/block — indentation says nothing
            closer_indent, opener_indent = _indent(text), _indent(lines[anchor - 1])
            if closer_indent < opener_indent:
                yield _BraceLocation("mispaired", anchor, ln, _dedent_point(lines, anchor, ln))
            elif closer_indent > opener_indent:
                yield _BraceLocation("extra", anchor, ln, ln)
    if stack:
        ch, _, anchor = stack[-1]
        # No dedent found means it runs to the end: the closer goes after the last line.
        yield _BraceLocation("unclosed", anchor, None, _dedent_point(lines, anchor, len(lines) + 1), _OPEN[ch])


def _dedent_point(lines: list[str], opener: int, limit: int) -> int:
    """First non-blank line after `opener` indented at or left of it that isn't
    itself a closer — where the opener's block should have ended."""
    base = _indent(lines[opener - 1])
    for n in range(opener + 1, min(limit, len(lines)) + 1):
        text = lines[n - 1]
        stripped = text.strip()
        if not stripped or stripped.startswith(("//", "*", "/*")):
            continue
        if _indent(text) <= base and not stripped.startswith(("}", ")", "]")):
            return n
    return limit


def check_world(html_path: Path, modules: dict[str, str] | None = None) -> list[str]:
    """Static lint, then headless console capture.

    Static findings come first so a mashed-together file is named as such
    before Chromium's SyntaxError is appended. If a script doesn't parse the
    browser is skipped entirely: nothing downstream of a parse failure can
    run, so its console would only repeat the same SyntaxError less precisely
    (and cost a Chromium launch plus a CDN fetch to say it).
    """
    from harness.browser_debug import check_console_errors

    html_path = Path(html_path)
    html = html_path.read_text(encoding="utf-8") if html_path.is_file() else ""
    errors = lint_world_html(html)
    if has_syntax_error(errors):
        return errors
    errors.extend(check_console_errors(html_path, modules=modules))
    return errors
