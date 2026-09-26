"""An LLM agent that finds and frames one biome at a time.

Replaces the old scripted legend click (visual_check.py's get_by_text on a
keyword list). That script could only say "clicked" or "not matched"; a label
our synonyms missed, a fly-to that landed on the wrong biome, or a world with
no legend all looked the same: no screenshot, which later read as "biome
absent". The agent looks at the frame, uses the legend when there is one,
orbits/pans/zooms when there isn't, and reports whether the saved view
really shows the biome, so a missing view carries a reason.

Token budget ("caveman mode"): one short episode per biome with a fresh
context, terse system prompt, one tool call per turn, only the newest frame
kept as an image (older frames become "[old frame dropped]"), the UI tree
filtered to clickable/text lines, and a hard step budget.
"""

from __future__ import annotations

import asyncio
import re
import sys
import uuid
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from eval.capture.browser import DevToolsBrowser  # noqa: E402
from eval.capture.llm import chat, image_part  # noqa: E402
from harness.status import log  # noqa: E402

MAX_STEPS = 8
AGENT_IMAGE_WIDTH = 640
UI_MAX_LINES = 50

SYSTEM = """Drive 3D voxel island viewer. Job: frame ONE biome, then save.
Caveman mode: no talk. One tool call per turn.
Legend/button naming biome exists -> click it first.
No legend -> orbit/pan/zoom until biome fills big part of frame.
Save when frame clearly shows the biome. shows_biome=false if you saved anyway but not sure.
Biome truly nowhere after looking around -> give_up with short reason.
Budget {steps} tool calls."""

_UI_LINE = re.compile(r"uid=\S+\s+(?:button|link|StaticText|listitem|generic|option|checkbox|radio)\b.*\"", re.I)


def _filter_ui(snapshot: str) -> str:
    lines = [ln.strip() for ln in snapshot.splitlines() if _UI_LINE.search(ln)]
    return "\n".join(lines[:UI_MAX_LINES]) or "(no clickable/text UI found)"


def _drop_old_images(messages: list) -> None:
    for msg in messages:
        if isinstance(msg, HumanMessage) and isinstance(msg.content, list):
            if any(part.get("type") == "image_url" for part in msg.content if isinstance(part, dict)):
                msg.content = [p for p in msg.content if not (isinstance(p, dict) and p.get("type") == "image_url")]
                msg.content.append({"type": "text", "text": "[old frame dropped]"})


async def frame_biome(
    browser: DevToolsBrowser,
    day_url: str,
    biome: dict,
    out_path: Path,
    model: str | None = None,
) -> dict:
    """One episode: reload the daytime preview, navigate, save or give up."""
    await browser.open(day_url)
    scratch = out_path.with_suffix(".agent.png")
    outcome: dict = {"status": "not_found", "reason": "budget exhausted", "steps": 0, "actions": []}

    @tool
    async def ui() -> str:
        """List clickable buttons / text on the page (legend entries) with their uid."""
        return _filter_ui(await browser.snapshot())

    @tool
    async def click(uid: str) -> str:
        """Click a UI element by uid (from ui)."""
        await browser.click(uid)
        return "clicked; camera may be flying, frame follows"

    @tool
    async def orbit(dx: int, dy: int) -> str:
        """Rotate camera by dragging dx, dy pixels (e.g. 300, 0 = spin; 0, -150 = look from higher)."""
        await browser.orbit(dx, dy)
        return "ok"

    @tool
    async def pan(dx: int, dy: int) -> str:
        """Slide camera sideways by dx, dy pixels."""
        await browser.pan(dx, dy)
        return "ok"

    @tool
    async def zoom(steps: int) -> str:
        """Zoom: positive = in, negative = out. 1-5 steps."""
        await browser.zoom(max(-8, min(8, steps)))
        return "ok"

    @tool
    def save(shows_biome: bool, confidence: float, note: str) -> str:
        """Keep current frame as this biome's view. confidence 0..1 that frame shows the biome. note: what is visible, <=15 words."""
        outcome.update(status="found" if shows_biome else "uncertain", confidence=confidence, note=note, reason="")
        return "saved"

    @tool
    def give_up(reason: str) -> str:
        """Biome not findable. reason <=15 words."""
        outcome.update(status="not_found", reason=reason)
        return "done"

    tools = {t.name: t for t in (ui, click, orbit, pan, zoom, save, give_up)}
    llm = chat(model, temperature=0).bind_tools(list(tools.values()))

    await browser.screenshot(scratch)
    messages: list = [
        SystemMessage(SYSTEM.format(steps=MAX_STEPS)),
        HumanMessage(content=[
            {"type": "text", "text": f"Biome: {biome['label']} (aka {', '.join(biome['keywords'])}).\nUI:\n{_filter_ui(await browser.snapshot())}\nFrame:"},
            image_part(scratch, AGENT_IMAGE_WIDTH),
        ]),
    ]

    for step in range(1, MAX_STEPS + 1):
        outcome["steps"] = step
        ai: AIMessage = await llm.ainvoke(messages)
        messages.append(ai)
        calls = ai.tool_calls[:1]
        if not calls:
            messages.append(HumanMessage("Call a tool."))
            continue
        call = calls[0]
        name, args = call["name"], call.get("args") or {}
        outcome["actions"].append({"tool": name, "args": args})
        log(f"        {biome['id']:<10} {step}. {name} {args if name not in ('save', 'give_up') else ''}")
        if name not in tools:
            result = f"ERROR: unknown tool {name}"
        else:
            try:
                result = await tools[name].ainvoke(args)
            except Exception as exc:  # bad uid, bad args: tell the agent, don't crash the capture
                result = f"ERROR: {exc}"[:300]
        messages.append(ToolMessage(content=str(result), tool_call_id=call.get("id") or str(uuid.uuid4())))
        # Gemini rejects extra tool calls in a turn we answered only once.
        ai.tool_calls = calls

        if name in ("save", "give_up"):
            break
        if name in ("click", "orbit", "pan", "zoom"):
            if name == "click":
                await asyncio.sleep(3)
            await browser.screenshot(scratch)
            _drop_old_images(messages)
            messages.append(HumanMessage(content=[{"type": "text", "text": "Frame:"}, image_part(scratch, AGENT_IMAGE_WIDTH)]))

    if outcome["status"] in ("found", "uncertain"):
        await browser.screenshot(out_path)
    scratch.unlink(missing_ok=True)
    return outcome
