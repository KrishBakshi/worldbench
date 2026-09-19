"""Static checks for a generated world.html — the class of failure the
browser never gets a clean shot at.

A model that hits a length cap, panics, and *restarts* will still emit a
closing ``</html>``, so ``harness.model_call._looks_complete`` treats the
file as finished. What it actually wrote is two drafts glued together:
an unfinished ``const w = Math.max(8*`` jammed into a markdown fence and
a second ``<!DOCTYPE html>``. Chromium then reports a syntax error at
that line, or (with ``file://`` + ``type=module``) a MIME/import failure
that hides the real cut. Either way the fix agent is told "Unexpected
token" and asked to patch surgically — which cannot unglue two files.

These checks name that failure as a generation artifact so the fix node
rewrites one complete document instead of nibbling at the fence.
"""

from __future__ import annotations

import re
from pathlib import Path

_FENCE_RE = re.compile(r"```")
_SCRIPT_OPEN_RE = re.compile(r"<script\b", re.I)
_SCRIPT_CLOSE_RE = re.compile(r"</script\s*>", re.I)
_SCRIPT_BODY_RE = re.compile(r"<script\b[^>]*>(.*?)</script\s*>", re.I | re.S)
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

_TRUNC_RE = re.compile(
    r"(?:"
    r"[\(\[\{,=+\-*/%<!&|?:]\s*$"
    r"|\b(?:const|let|var|function|return|if|for|while|else|class)\s+\w*\s*$"
    r")"
)
_HTML_TAIL_RE = re.compile(r"</(?:body|html)\s*>", re.I)

MAX_FENCE_REPORTS = 3


def lint_world_html(html: str) -> list[str]:
    """Return ``[structure] …`` findings. Empty list means the document
    looks like one finished HTML file (runtime errors are not this function's
    job — see ``harness.browser_debug``)."""
    errors: list[str] = []
    if not html or not html.strip():
        return ["[structure] file is empty"]

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

    bodies = _SCRIPT_BODY_RE.findall(html)
    if not bodies and opens:
        last_open = None
        for match in _SCRIPT_OPEN_RE.finditer(html):
            last_open = match
        if last_open is not None:
            tail = html[last_open.end() :]
            html_end = _HTML_TAIL_RE.search(tail)
            if html_end:
                tail = tail[: html_end.start()]
            bodies = [tail]
    if bodies:
        last = bodies[-1]
        last_code = _last_code_line(last)
        if last_code and _TRUNC_RE.search(last_code):
            errors.append(
                f"[structure] last script ends on a truncated statement: {last_code.strip()!r}. "
                "Continue or rewrite from that cut; the expression never finished."
            )
        brace = _unbalanced(last)
        if brace:
            errors.append(f"[structure] last <script> has {brace}")

    return errors


def _last_code_line(script: str) -> str:
    for raw in reversed(script.splitlines()):
        line = raw.strip()
        if not line or line.startswith("//") or line.startswith("*"):
            continue
        return raw
    return ""


def _unbalanced(script: str) -> str | None:
    """Cheap brace/paren count on the last script. Strings/comments can fool
    this; a hit is a hint for the fix agent, not a JS parser."""
    counts = {"(": 0, "[": 0, "{": 0}
    close = {")": "(", "]": "[", "}": "{"}
    in_str = None
    escape = False
    for ch in script:
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_str:
                in_str = None
            continue
        if ch in "\"'`":
            in_str = ch
            continue
        if ch in counts:
            counts[ch] += 1
        elif ch in close:
            opener = close[ch]
            counts[opener] -= 1
            if counts[opener] < 0:
                return f"extra {ch!r} (unbalanced)"
    leftover = [f"{n} extra {ch!r}" for ch, n in counts.items() if n > 0]
    if leftover:
        return ", ".join(leftover) + " — the script was cut off mid-function"
    return None


def check_world(html_path: Path) -> list[str]:
    """Structure lint, then headless console capture.

    Structure findings come first so a mashed-together file is named as
    such before Chromium's SyntaxError (or a ``file://`` module-load miss)
    is appended.
    """
    from harness.browser_debug import check_console_errors

    html_path = Path(html_path)
    html = html_path.read_text(encoding="utf-8") if html_path.is_file() else ""
    errors = lint_world_html(html)
    errors.extend(check_console_errors(html_path))
    return errors
