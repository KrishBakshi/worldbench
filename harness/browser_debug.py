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
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

DEFAULT_TIMEOUT_MS = 5000
DEFAULT_NAV_TIMEOUT_MS = 15000

_LOC_MARKER = "__WB_LOC__"
_LOCATION_INIT_SCRIPT = f"""
window.addEventListener('error', (e) => {{
  try {{
    console.log({_LOC_MARKER!r}, JSON.stringify({{lineno: e.lineno, colno: e.colno}}));
  }} catch (_) {{}}
}});
window.addEventListener('unhandledrejection', (e) => {{
  try {{
    const r = e.reason;
    const m = r && r.stack ? String(r.stack).match(/:(\\d+):(\\d+)\\)?\\s*$/m) : null;
    console.log({_LOC_MARKER!r}, JSON.stringify({{lineno: m ? +m[1] : null, colno: m ? +m[2] : null}}));
  }} catch (_) {{}}
}});
"""


def _loc_suffix(lineno: int | None, colno: int | None) -> str:
    if lineno is None:
        return ""
    return f" (line {lineno}, col {colno})" if colno is not None else f" (line {lineno})"


def check_console_errors(
    html_path: Path,
    *,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
    nav_timeout_ms: int = DEFAULT_NAV_TIMEOUT_MS,
) -> list[str]:
    """Load `html_path` headless and return distinct console/page errors seen,
    each suffixed with `(line N, col N)` when a location could be found.

    Order-preserving de-duplication: a per-frame throw inside an animation
    loop (requestAnimationFrame) repeats the identical message every frame
    and would otherwise flood the result with hundreds of copies of the same
    error (seen for real: 604 identical entries for one bug) — collapsed to
    one here since that's one bug, not six hundred.
    """
    html_path = Path(html_path).resolve()
    seen: dict[str, None] = {}
    # window.onerror/unhandledrejection fire in the same browser-side order as
    # the pageerror events they correspond to, so a FIFO queue correlates them
    # without needing to text-match the two independent event streams.
    loc_queue: list[tuple[int | None, int | None]] = []

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
        if msg.type == "error":
            loc = msg.location or {}
            suffix = _loc_suffix(loc.get("lineNumber"), loc.get("columnNumber"))
            _record(f"[console.error] {msg.text}{suffix}")

    def _on_pageerror(exc) -> None:
        lineno = colno = None
        if loc_queue:
            lineno, colno = loc_queue.pop(0)
        if lineno is None:
            # runtime errors (unlike parse-time SyntaxErrors) carry a real
            # stack — pull "file:LINE:COL" off its first frame as a fallback
            stack = getattr(exc, "stack", "") or ""
            m = re.search(r":(\d+):(\d+)\)?\s*(?:\n|$)", stack)
            if m:
                lineno, colno = int(m.group(1)), int(m.group(2))
        _record(f"[uncaught] {exc}{_loc_suffix(lineno, colno)}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.add_init_script(_LOCATION_INIT_SCRIPT)
        page.on("console", _on_console)
        page.on("pageerror", _on_pageerror)

        try:
            page.goto(f"file://{html_path}", timeout=nav_timeout_ms)
        except Exception as exc:  # noqa: BLE001 — navigation failure is itself a finding
            _record(f"[navigation] {exc}")
        else:
            page.wait_for_timeout(timeout_ms)

        browser.close()

    return list(seen.keys())
