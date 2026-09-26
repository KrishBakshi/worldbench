"""A headless Chrome driven through the Chrome DevTools MCP server.

This is the same tool surface a coding agent gets from chrome-devtools-mcp
(navigate, evaluate_script, take_screenshot, take_snapshot, click), spoken
over MCP stdio. The fixed capture steps call it directly; navigator.py hands
a curated subset to an LLM agent.

The server has no coordinate drag, so orbit/pan/zoom dispatch synthetic
pointer and wheel events on the world's canvas. OrbitControls does not check
isTrusted, which was verified on opus-5, kimi-k-3 and gpt-5-6-sol.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from contextlib import AsyncExitStack
from pathlib import Path

import mcp.types as mcp_types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HOOK_JS = (Path(__file__).with_name("hook.js")).read_text(encoding="utf-8")
# The server only writes screenshots inside the client's declared roots.
REPO_ROOT = Path(__file__).resolve().parents[2]
VIEWPORT = (1280, 800)
SETTLE_S = 4.0

_JSON_BLOCK = re.compile(r"```json\s*(.*?)\s*```", re.S)
_SELECTED_PAGE = re.compile(r"^(\d+):.*\[selected\]", re.M)

_CANVAS = "[...document.querySelectorAll('canvas')].sort((a,b)=>b.width*b.height-a.width*a.height)[0]"

_DRAG_JS = """(dx, dy, button) => {
  const c = %s; if (!c) return 'no canvas';
  const r = c.getBoundingClientRect();
  const x0 = r.left + r.width / 2, y0 = r.top + r.height / 2;
  const buttons = button === 2 ? 2 : 1;
  const fire = (type, x, y, b) => c.dispatchEvent(new PointerEvent(type, {
    clientX: x, clientY: y, pointerId: 1, pointerType: 'mouse', button,
    buttons: b, bubbles: true, isPrimary: true }));
  fire('pointerdown', x0, y0, buttons);
  const steps = 12;
  for (let i = 1; i <= steps; i++) fire('pointermove', x0 + dx * i / steps, y0 + dy * i / steps, buttons);
  fire('pointerup', x0 + dx, y0 + dy, 0);
  return 'ok';
}""" % _CANVAS

_WHEEL_JS = """(steps) => {
  const c = %s; if (!c) return 'no canvas';
  const r = c.getBoundingClientRect();
  for (let i = 0; i < Math.abs(steps); i++) c.dispatchEvent(new WheelEvent('wheel', {
    deltaY: steps > 0 ? -120 : 120, clientX: r.left + r.width / 2,
    clientY: r.top + r.height / 2, bubbles: true, cancelable: true }));
  return 'ok';
}""" % _CANVAS


async def _repo_roots(_context) -> mcp_types.ListRootsResult:
    return mcp_types.ListRootsResult(roots=[mcp_types.Root(uri=REPO_ROOT.as_uri(), name="worldbench")])


class DevToolsBrowser:
    """One headless Chrome with one page. Use as `async with DevToolsBrowser() as b:`."""

    def __init__(self, viewport: tuple[int, int] = VIEWPORT):
        self.viewport = viewport
        self.page_id: int | None = None
        self._stack = AsyncExitStack()
        self._session: ClientSession | None = None

    async def __aenter__(self) -> "DevToolsBrowser":
        params = StdioServerParameters(
            command=shutil.which("npx") or "npx",
            args=[
                "-y", "chrome-devtools-mcp@latest", "--headless", "--isolated",
                "--viewport", f"{self.viewport[0]}x{self.viewport[1]}",
                "--no-usage-statistics", "--no-performance-crux",
            ],
        )
        read, write = await self._stack.enter_async_context(stdio_client(params))
        self._session = await self._stack.enter_async_context(
            ClientSession(read, write, list_roots_callback=_repo_roots)
        )
        await self._session.initialize()
        text = await self.call("new_page", {"url": "about:blank"})
        match = _SELECTED_PAGE.search(text)
        self.page_id = int(match.group(1)) if match else 1
        return self

    async def __aexit__(self, *exc) -> None:
        await self._stack.aclose()

    async def call(self, tool: str, args: dict) -> str:
        assert self._session is not None
        res = await self._session.call_tool(tool, args)
        text = "\n".join(getattr(c, "text", "") or "" for c in res.content)
        if getattr(res, "is_error", False) or getattr(res, "isError", False):
            raise RuntimeError(f"{tool}: {text[:500]}")
        return text

    def _page(self, extra: dict | None = None) -> dict:
        return {"pageId": self.page_id, **(extra or {})}

    async def open(self, url: str, settle_s: float = SETTLE_S) -> None:
        await self.call("navigate_page", self._page({"type": "url", "url": url, "initScript": HOOK_JS, "timeout": 60000}))
        await asyncio.sleep(settle_s)

    async def js(self, function: str, *args) -> object:
        payload = self._page({"function": function})
        if args:
            # evaluate_script args are element uids; pass plain values by closure instead.
            payload["function"] = f"() => ({function})({', '.join(json.dumps(a) for a in args)})"
        text = await self.call("evaluate_script", payload)
        match = _JSON_BLOCK.search(text)
        if not match:
            return text
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return match.group(1)

    async def screenshot(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        await self.call("take_screenshot", self._page({"filePath": str(path.resolve()), "format": "png"}))
        return path

    async def orbit(self, dx: float, dy: float) -> None:
        await self.js(_DRAG_JS, dx, dy, 0)
        await asyncio.sleep(0.6)

    async def pan(self, dx: float, dy: float) -> None:
        await self.js(_DRAG_JS, dx, dy, 2)
        await asyncio.sleep(0.6)

    async def zoom(self, steps: int) -> None:
        """Positive steps zoom in, negative zoom out."""
        await self.js(_WHEEL_JS, steps)
        await asyncio.sleep(0.6)

    async def snapshot(self) -> str:
        return await self.call("take_snapshot", self._page())

    async def click(self, uid: str) -> str:
        return await self.call("click", self._page({"uid": uid}))

    async def camera(self) -> dict | None:
        return await self.js(
            "() => __wb.camera ? {pos: __wb.camera.position.toArray().map(v => +v.toFixed(1)),"
            " scenes: __wb.scenes.length} : null"
        )
