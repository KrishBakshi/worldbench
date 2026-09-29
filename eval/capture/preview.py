"""A preview copy of world.html whose clock can be pinned from the URL.

Every visual judge needs a daytime frame: a biome captured at night is dark
and reads as "missing". Worlds each keep time their own way (hours, an angle,
a 0..1 phase, a frame counter), so one LLM call reads the source and patches
the world's own clock to obey window.__WB_TIME, which hook.js fills from
?wb_tod=&wb_season=. One patch then serves every time variant: noon for the
content judges, night and the four seasons for WC005.

The patch is only allowed to *override values the world already computes*.
Guards: every new_str must read __WB_TIME, each edit adds at most
MAX_ADDED_CHARS, at most MAX_EDITS edits, and every old_str must match the
source exactly once. A patcher that invented its own lighting would hand
WC005 a day/night cycle the model never wrote.

Which pinned value is really "day" is not taken on trust either: capture.py
renders several tod values and keeps the brightest (see pick_day_tod).
"""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic import BaseModel, Field

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from eval.capture.llm import JudgeUnavailable, invoke_structured  # noqa: E402
from harness.status import log  # noqa: E402

MAX_EDITS = 6
MAX_ADDED_CHARS = 600
MAX_ATTEMPTS = 3

PATCH_PROMPT = """You are patching a Three.js world (one HTML file) so a test harness can pin its
time of day and season from outside.

Before any page script runs, the harness may set:
  window.__WB_TIME = { tod: <number 0..1 or null>, season: <0|1|2|3 or null> }
tod: 0 = midnight, 0.25 = sunrise, 0.5 = noon, 0.75 = sunset.
season: 0 = spring, 1 = summer, 2 = autumn, 3 = winter.
When window.__WB_TIME is undefined the world must behave exactly as before.

Find where the world computes its own time of day and season (a clock, an angle,
an hour, a phase, a frame counter, a season index or year fraction). Add the
smallest edits so that, whenever window.__WB_TIME.tod / .season is not null,
the world's OWN value is replaced by the pinned value every frame, converted to
the world's own units (hours 0-24, radians, its own phase offset: read the code
so "noon" in its units really is when its sun is highest).

Hard rules:
- Only override the time/season value the world already has. Do NOT add
  lights, colors, fog, sun meshes, or any behaviour the world did not have.
- Every new_str must contain the text __WB_TIME. Keep edits tiny.
- old_str must be copied verbatim from SOURCE and appear exactly once.
  Include enough surrounding characters to make it unique.
- At most {max_edits} edits.
- If the world has no day/night cycle, set cycle_found false and add no tod
  edit. Same for seasons with season_found.

SOURCE:
{source}
"""


class Edit(BaseModel):
    old_str: str
    new_str: str


class PreviewPatch(BaseModel):
    cycle_found: bool = Field(description="the world has its own time-of-day cycle")
    season_found: bool = Field(description="the world has its own season cycle")
    clock_summary: str = Field(description="one line: which variables hold time/season and their units")
    edits: list[Edit]


def apply_edits(source: str, edits: list[Edit]) -> tuple[str, list[str]]:
    """Apply every edit or none. Returns (patched, errors)."""
    errors: list[str] = []
    if len(edits) > MAX_EDITS:
        errors.append(f"{len(edits)} edits, max {MAX_EDITS}")
    patched = source
    for i, edit in enumerate(edits, 1):
        count = patched.count(edit.old_str)
        if not edit.old_str:
            errors.append(f"edit {i}: empty old_str")
        elif count == 0:
            errors.append(f"edit {i}: old_str not found")
        elif count > 1:
            errors.append(f"edit {i}: old_str matches {count} times, add context")
        if "__WB_TIME" not in edit.new_str:
            errors.append(f"edit {i}: new_str does not read __WB_TIME")
        if len(edit.new_str) - len(edit.old_str) > MAX_ADDED_CHARS:
            errors.append(f"edit {i}: adds {len(edit.new_str) - len(edit.old_str)} chars, max {MAX_ADDED_CHARS}")
        if count == 1:
            patched = patched.replace(edit.old_str, edit.new_str, 1)
    return (source, errors) if errors else (patched, [])


def build_preview(world_html: Path, out_path: Path, model: str | None = None) -> dict:
    """Write out_path and return a record for the capture manifest."""
    source = Path(world_html).read_text(encoding="utf-8", errors="ignore")
    prompt = PATCH_PROMPT.replace("{max_edits}", str(MAX_EDITS)).replace("{source}", source)
    feedback = ""
    record: dict = {"ok": False, "attempts": 0}
    for attempt in range(1, MAX_ATTEMPTS + 1):
        record["attempts"] = attempt
        log(f"      preview   (llm) patch clock, attempt {attempt}")
        try:
            patch = invoke_structured(PreviewPatch, prompt + feedback, model=model)
        except JudgeUnavailable:
            raise
        except Exception as exc:  # a failed call is retried like a bad patch
            feedback = f"\n\nYour previous reply failed to parse: {exc}. Return valid JSON."
            record["error"] = str(exc)
            continue
        patched, errors = apply_edits(source, patch.edits)
        record.update(
            cycle_found=patch.cycle_found,
            season_found=patch.season_found,
            clock_summary=patch.clock_summary,
            edits=[e.model_dump() for e in patch.edits],
            errors=errors,
        )
        if not errors:
            Path(out_path).write_text(patched, encoding="utf-8")
            record["ok"] = True
            log(f"      preview   {len(patch.edits)} edit(s)  {patch.clock_summary}")
            return record
        log(f"      preview   rejected: {'; '.join(errors)}")
        feedback = "\n\nYour previous edits were rejected:\n- " + "\n- ".join(errors) + "\nFix them."
    # No usable patch: the preview is the unmodified world. Capture still runs;
    # pick_day_tod then finds no brightness difference and says so.
    Path(out_path).write_text(source, encoding="utf-8")
    return record
