"""Headless-Chromium console-error capture for a world.html.

Deliberately does NOT try to verify anything about rendering (no screenshot,
no waiting on a render/camera signal, no GPU flag tuning). It only needs the
page's JS to execute far enough to throw or not — console.error calls and
uncaught exceptions fire from the JS engine regardless of whether WebGL ever
paints a pixel, so this sidesteps the swiftshader/rAF-throttling uncertainty
that sank the earlier headless-rendering spike (see project memory
avoid-headless-browser-infra). If that assumption stops holding for some
world.html, treat it as a fresh signal to revisit, not something to force
through by adding rendering waits here.

Each returned error string carries a `(line N, col N)` suffix when a source
location could be found — this is what lets the fix node send the model a
small windowed excerpt around the error instead of the entire file (see
generate.py's _build_fix_context). Getting that location isn't free:
Playwright's `pageerror` gives a full call-stack for a runtime error
(TypeError, ReferenceError, ...) but an EMPTY stack for a parse-time
SyntaxError — confirmed directly against a real broken world.html, not
assumed — because V8 never builds a call stack for a script that failed to
parse in the first place. A `window.addEventListener('error'/'unhandled
rejection')` listener injected via `add_init_script` gets lineno/colno for
both cases, since the ErrorEvent/PromiseRejectionEvent carries source
position independent of whether a stack exists. `console.error()` calls
get their location straight from Playwright's own `msg.location`, no
injection needed.

The suffix reports the CALLER FRAMES too, not just the throw site:
`(line 104, col 27; called from line 383, line 397)`. This is not
cosmetic — for a whole class of JS errors the throw site is correct code
and the bug is in the caller. Seen for real: a world.html defined
`jit=(c,rnd)=>c*(0.9+rnd()*0.2)` on line 104 and called it as
`jit(color, Rv())` — passing the RNG's *result* instead of the RNG
itself — on lines 383/397/412. `rnd is not a function` was reported at
line 104, the fix node windowed +/-40 lines around it, and the model was
handed a perfectly correct arrow function and asked what was wrong with
it. Three fix rounds produced zero edits, which was the only honest
answer available to it. The caller frames were sitting in `exc.stack`
the whole time and were being discarded here. Frames are filtered to
this document (CDN/three.module.js frames are noise for a fix window),
deduplicated for recursion, and capped at MAX_CALLER_FRAMES so a deep
in-file stack can't expand the "windowed" excerpt into the whole file.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

DEFAULT_TIMEOUT_MS = 5000
DEFAULT_NAV_TIMEOUT_MS = 15000
# How many caller frames (beyond the throw site) to report. Each one becomes
# another +/-FIX_CONTEXT_LINES window in the fix prompt, so this is the knob
# that keeps a "windowed" fix round actually windowed: 4 callers x 81 lines is
# a worst case of ~405 lines before overlap-merging, still a small fraction of
# a typical several-hundred-to-thousand-line world.html. Frames past this are
# dropped from the deepest end — the immediate caller is where these bugs
# overwhelmingly live, and top-level init frames add the least.
MAX_CALLER_FRAMES = 4

_LOC_MARKER = "__WB_LOC__"
_ERR_STACK_MARKER = "__WB_ERRSTACK__"
_LOCATION_INIT_SCRIPT = f"""
window.addEventListener('error', (e) => {{
  try {{
    console.log({_LOC_MARKER!r}, JSON.stringify({{lineno: e.lineno, colno: e.colno}}));
  }} catch (_) {{}}
}});
// console.error carries no stack of its own, and when a library logs it
// (three.module.js's `computeBoundingSphere(): radius is NaN`) its location is
// the library's line, which the fix node can't edit or window. Record the JS
// stack at the call so the page's own frames — the code that handed the
// library bad data — can be reported instead. Keyed by the first argument
// so it's matched to its console message by text, not by arrival order:
// the browser emits console errors of its own (failed resource loads) that
// never pass through this wrapper, and an ordering queue would desync.
(() => {{
  const original = console.error.bind(console);
  console.error = (...args) => {{
    try {{
      console.debug({_ERR_STACK_MARKER!r}, JSON.stringify({{first: String(args[0]), stack: new Error().stack}}));
    }} catch (_) {{}}
    original(...args);
  }};
}})();
window.addEventListener('unhandledrejection', (e) => {{
  try {{
    const r = e.reason;
    const m = r && r.stack ? String(r.stack).match(/:(\\d+):(\\d+)\\)?\\s*$/m) : null;
    console.log({_LOC_MARKER!r}, JSON.stringify({{lineno: m ? +m[1] : null, colno: m ? +m[2] : null}}));
  }} catch (_) {{}}
}});
"""


def _loc_suffix(lineno: int | None, colno: int | None, callers: list[int] | None = None) -> str:
    """Render the `(line N, col N; called from line A, line B)` suffix.

    generate.py's _LOCATION_RE parses this exact shape back out, so the
    two must change together — the whole parenthesized group is isolated
    there and every `line N` inside it becomes a fix-context window.
    """
    if not lineno:
        # 0 is not a line: the browser reports lineno 0 for failures with no
        # position in the page (a module that fails to resolve inside an
        # imported file). Printing `(line 0, col 0)` pointed the fix node at
        # the top of world.html for a problem that wasn't in it.
        return ""
    head = f"line {lineno}, col {colno}" if colno is not None else f"line {lineno}"
    if callers:
        head += "; called from " + ", ".join(f"line {n}" for n in callers)
    return f" ({head})"


def _stack_frames(stack: str, page_url: str) -> list[tuple[int, int]]:
    """Every `(line, col)` in `stack` belonging to `page_url`, in call order.

    Frames from the Three.js CDN are deliberately excluded: they're not
    editable by the fix node, and windowing around them would waste the
    context budget on library internals. Deduplicated because a recursive
    or per-frame throw repeats the same frame many times over.
    """
    frame_re = re.compile(re.escape(page_url) + r":(\d+):(\d+)")
    frames: dict[tuple[int, int], None] = {}
    for line in stack.split("\n"):
        m = frame_re.search(line)
        if m:
            frames.setdefault((int(m.group(1)), int(m.group(2))), None)
    return list(frames.keys())


_UNRESOLVED_RE = re.compile(r'Failed to resolve module specifier "([^"]+)"')


def _importers(specifier: str, sources: dict[str, str]) -> list[tuple[str, int]]:
    """(url, line) of every `from 'X'` / `import 'X'` / `import('X')` of `specifier`."""
    rx = re.compile(r"""(?:\bfrom|\bimport)\s*\(?\s*['"]""" + re.escape(specifier) + r"""['"]""")
    hits = []
    for url, text in sources.items():
        for i, line in enumerate(text.split("\n"), 1):
            if rx.search(line):
                hits.append((url, i))
    return hits


def check_console_errors(
    html_path: Path,
    *,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    nav_timeout_ms: int = DEFAULT_NAV_TIMEOUT_MS,
    modules: dict[str, str] | None = None,
) -> list[str]:
    """Load `html_path` headless and return distinct console/page errors seen,
    each suffixed with `(line N, col N)` when a location could be found, plus
    `; called from line A, line B` for up to MAX_CALLER_FRAMES in-document
    caller frames when the error carries a stack.

    Order-preserving de-duplication: a per-frame throw inside an animation
    loop (requestAnimationFrame) repeats the identical message every frame
    and would otherwise flood the result with hundreds of copies of the same
    error (seen for real: 604 identical entries for one bug) — collapsed to
    one here since that's one bug, not six hundred.

    `modules`, if given, is filled with {url: source} for every script module
    the page fetched over http(s) — the imported files an error can live in
    but that no tool looking at world.html alone can see. A bare-specifier
    failure (`Failed to resolve module specifier "three"`) raised inside an
    imported file is annotated with the file and line that imported it.
    """
    html_path = Path(html_path).resolve()
    page_url = f"file://{html_path}"
    seen: dict[str, None] = {}
    # window.onerror/unhandledrejection fire in the same browser-side order as
    # the pageerror events they correspond to, so a FIFO queue correlates them
    # without needing to text-match the two independent event streams.
    loc_queue: list[tuple[int | None, int | None]] = []
    # (first console.error argument, in-document frames), see the init script.
    error_stacks: list[tuple[str, list[tuple[int, int]]]] = []

    def _record(text: str) -> None:
        seen.setdefault(text, None)

    def _on_console(msg) -> None:
        if msg.text.startswith(_LOC_MARKER):
            try:
                data = json.loads(msg.text[len(_LOC_MARKER) :].strip())
            except (json.JSONDecodeError, ValueError):
                return
            loc_queue.append((data.get("lineno"), data.get("colno")))
            return
        if msg.text.startswith(_ERR_STACK_MARKER):
            try:
                data = json.loads(msg.text[len(_ERR_STACK_MARKER) :].strip())
            except (json.JSONDecodeError, ValueError):
                return
            error_stacks.append((data.get("first") or "", _stack_frames(data.get("stack") or "", page_url)))
            return
        if msg.type == "error":
            frames: list[tuple[int, int]] = []
            for i, (first, stack_frames) in enumerate(error_stacks):
                if msg.text.startswith(first):
                    frames = stack_frames
                    del error_stacks[i]
                    break
            loc = msg.location or {}
            lineno, colno = loc.get("lineNumber"), loc.get("columnNumber")
            if loc.get("url") != page_url:
                # Logged from inside a library: its line is the library's, not
                # ours. The page's own frames say which of our lines called in.
                lineno, colno = frames[0] if frames else (None, None)
            callers = [ln for ln, _ in frames if ln != lineno][:MAX_CALLER_FRAMES]
            _record(f"[console.error] {msg.text}{_loc_suffix(lineno, colno, callers)}")

    def _on_pageerror(exc) -> None:
        # Runtime errors (unlike parse-time SyntaxErrors, which V8 never
        # builds a stack for) carry a real stack. Parse it always, not just
        # as a fallback for a missing primary location: the frames AFTER the
        # throw site are the point — see the module docstring's jit/rnd case.
        frames = _stack_frames(getattr(exc, "stack", "") or "", page_url)
        lineno = colno = None
        if loc_queue:
            lineno, colno = loc_queue.pop(0)
        if not lineno and frames:
            lineno, colno = frames[0]
        callers = [ln for ln, _ in frames if ln != lineno][:MAX_CALLER_FRAMES]
        _record(f"[uncaught] {exc}{_loc_suffix(lineno, colno, callers)}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.add_init_script(_LOCATION_INIT_SCRIPT)
        page.on("console", _on_console)
        page.on("pageerror", _on_pageerror)
        script_responses: list = []
        page.on(
            "response",
            lambda r: script_responses.append(r)
            if r.request.resource_type == "script" and r.url.startswith(("http://", "https://"))
            else None,
        )

        try:
            page.goto(page_url, timeout=nav_timeout_ms)
        except Exception as exc:  # noqa: BLE001 — navigation failure is itself a finding
            _record(f"[navigation] {exc}")
        else:
            page.wait_for_timeout(timeout_ms)

        # Read bodies after the page settled, not inside the event callback
        # (the sync API must not block inside its own event dispatch).
        fetched: dict[str, str] = {}
        for response in script_responses:
            try:
                fetched.setdefault(response.url, response.text())
            except Exception:  # noqa: BLE001 — a body that can't be read is simply not available
                pass
        browser.close()

    if modules is not None:
        modules.update(fetched)
    page_source = html_path.read_text(encoding="utf-8", errors="ignore")
    return [_annotate_unresolved(e, fetched, page_source) for e in seen]


def _annotate_unresolved(error: str, fetched: dict[str, str], page_source: str) -> str:
    """Name where an unresolvable import actually is.

    The browser gives no position for this failure, and the culprit is often
    not the page: a CDN module like OrbitControls.js does `from 'three'`, a
    bare specifier that only resolves through an import map in the page. A
    fix agent told only the message searches world.html, finds nothing but
    full URLs, and has nothing left but guesses.
    """
    m = _UNRESOLVED_RE.search(error)
    if not m or "imported by" in error:
        return error
    spec = m.group(1)
    in_page = _importers(spec, {"": page_source})
    if in_page:
        return f"{error} (line {in_page[0][1]})"
    where = _importers(spec, fetched)
    if not where:
        return error
    by = "; ".join(f"{url} line {line}" for url, line in where[:4])
    return (
        f"{error} — imported by {by}, not by world.html. A bare specifier in an "
        f"imported module only resolves through an import map in the page "
        f"(<script type=\"importmap\">) that maps \"{spec}\" to a URL."
    )
