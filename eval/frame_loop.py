"""Does a quoted line run every frame? Shared by the WC004 and WC005 graders.

`runs_every_frame(quote, js)` is True only if the quote's line sits inside the
frame loop: the function registered with requestAnimationFrame /
setAnimationLoop, an anonymous callback passed to it, or a function those call
(LOOP_DEPTH deep). Anything it can't establish is False, so callers fall back
to their strict rule.

This answers "is this an update?" from where the code runs, not from what its
variables are called. Name lists can't: `burst(time, …)` matched one while
`envelope(t, …)` and `burstEnvelope(elapsedTotal, …)` (the same per-frame
call) did not, which moved real worlds by up to 12 points.

It reads the raw script (probe.strip_html), not eval.evidence.normalize's
whitespace-free text. With whitespace gone, a `//` comment can't be told from
the code after it: `// start late morning` + `function frame(){` became one
word, `//startlatemorningfunctionframe(){`, the loop was never found, and
every per-frame line of that world was rejected. Here comments are dropped
first, and whitespace between two word characters is kept as one space, so
nothing glues together.
"""

from __future__ import annotations

import functools
import re

from eval.evidence import strip_comments

LOOP_DEPTH = 4

_LOOP_ROOT = re.compile(r"(?:requestAnimationFrame|setAnimationLoop)\((\w+)\)")
_LOOP_OPEN = re.compile(
    r"(?:requestAnimationFrame|setAnimationLoop)\((?:async )?(?:function(?: \w+)?)?\(?[\w,]*\)?(?:=>)?$"
)
# Tried in this order; the first that matches names the function. Each is
# anchored at the `{` it precedes.
_FUNC_HEADS = (
    re.compile(r"function (\w+)\([^()]*\)$"),                     # function name(...)
    re.compile(r"(\w+)=(?:async )?function(?: \w+)?\([^()]*\)$"),  # name=function(...)
    re.compile(r"(\w+)=(?:async )?\(?[\w,=.]*\)?=>$"),             # name=(...)=> / name=x=>
    re.compile(r"(?<![.\w])(\w+)\([^()]*\)$"),                    # method name(...)
)
_NOT_FUNCS = {"if", "for", "while", "switch", "catch", "with", "function", "return"}
_CALLED = re.compile(r"(\w+)\(")
_WORD = re.compile(r"\w")


def _collapse(text: str) -> str:
    """Remove whitespace, except one space where it separates two word characters."""
    out: list[str] = []
    for part in re.split(r"(\s+)", text):
        if not part:
            continue
        if part.isspace():
            if out and _WORD.match(out[-1][-1:]):
                out.append(" ")
            continue
        if out and out[-1] == " " and not _WORD.match(part[0]):
            out.pop()
        out.append(part)
    return "".join(out).strip()


@functools.lru_cache(maxsize=8)
def _prepared(js: str) -> str:
    return _collapse(strip_comments(js))


def _open_brace_before(src: str, pos: int) -> int:
    """Index of the `{` that encloses src[pos], or -1."""
    depth = 0
    for i in range(pos - 1, -1, -1):
        c = src[i]
        if c == "}":
            depth += 1
        elif c == "{":
            if depth == 0:
                return i
            depth -= 1
    return -1


def _body(src: str, open_at: int) -> str:
    depth = 0
    for i in range(open_at, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[open_at + 1 : i]
    return src[open_at + 1 :]


def _func_name(before: str) -> str | None:
    for head in _FUNC_HEADS:
        m = head.search(before)
        if m:
            name = m.group(1)
            return None if name in _NOT_FUNCS else name
    return None


@functools.lru_cache(maxsize=8)
def _per_frame_functions(src: str) -> frozenset[str]:
    """Names of the frame-loop callbacks and everything they call, LOOP_DEPTH deep."""
    heads: dict[str, int] = {}
    for m in re.finditer(r"\{", src):
        name = _func_name(src[max(0, m.start() - 160) : m.start()])
        if name and name not in heads:
            heads[name] = m.start()
    frontier = set(_LOOP_ROOT.findall(src)) & set(heads)
    seen = set(frontier)
    for _ in range(LOOP_DEPTH):
        called = set()
        for name in frontier:
            called |= {c for c in _CALLED.findall(_body(src, heads[name])) if c in heads and c not in seen}
        seen |= called
        frontier = called
    return frozenset(seen)


def runs_every_frame(quote: str, js: str | None) -> bool:
    """True only if `quote` is found in `js` (the page's raw script text) inside
    the frame loop. No source, quote not found, or loop not established: False."""
    if not js:
        return False
    src = _prepared(js)
    code = _collapse(strip_comments(quote))
    at = src.find(code) if code else -1
    if at < 0:
        return False
    per_frame = _per_frame_functions(src)
    pos = at
    while (open_at := _open_brace_before(src, pos)) >= 0:
        before = src[max(0, open_at - 160) : open_at]
        if _LOOP_OPEN.search(before):
            return True
        name = _func_name(before)
        if name and name in per_frame:
            return True
        pos = open_at
    return False
