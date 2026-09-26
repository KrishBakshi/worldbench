"""Visual pass for WC005: does the world visibly change with time of day and season?

Frames come from the shared capture, which pins the world's own clock
through the preview patch (eval/capture/preview.py): four time-of-day probes
(tod 0 / .25 / .5 / .75) and, when the world has seasons, four season frames
at day. The brightest probe is "day", the darkest is "night".

"Does X change?" is measured from pixels, not asked. On kimi-k-3 the VLM
said lighting was "identical across time frames" while mean brightness was
11.9 / 35.0 / 11.6 / 11.5, and said the seasons left the world unchanged
while autumn's land pixels were far warmer than spring's. A small model
comparing 8 frames in one call is not a reliable differ; a pixel diff is.
  night_dimming       night frame darker than day by MIN_DAY_NIGHT_GAP (capture's pinned)
  light_follows_sun   some time frame differs from day by >= LIGHT_CHANGE_DIFF
  dusk_dawn_tint      a twilight frame's land chromaticity shifts >= DUSK_CHROMA_SHIFT
  season_world_tint   a season frame's land chromaticity shifts >= SEASON_CHROMA_SHIFT
Thresholds are calibrated on one world (kimi-k-3) so far; re-check them on
more worlds before trusting small margins.
Object questions (sun, moon, stars, a visibly changing season) go to one VLM
call, which is what vision models are good at.

cloud_drift_wrap and season_modulates_weather cannot be seen in stills, so
they have no visual verdict (None) and grade.py scores them on code alone.
If the preview patch failed, the time frames are all the same moment and say
nothing about the model, so the whole visual pass is marked unavailable.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent))

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))

from eval.capture.llm import invoke_structured  # noqa: E402
from eval.capture.run import ensure_capture, view_paths  # noqa: E402
from harness.status import log  # noqa: E402

QUESTIONS = {
    "sun_orbit": "Is a sun (square or disc) visible, and is it in a different place (or gone) between the time frames?",
    "sky_or_fog_day_cycle": "Does fog or haze over the island change color or density between times of day? (The background void itself should stay black.)",
    "moon": "Is a moon visible in the darkest time frame?",
    "season_cycle": "Across the season frames, does the season visibly change (season HUD text or the world itself)?",
}
MEASURED = ("night_dimming", "light_follows_sun", "dusk_dawn_tint", "season_world_tint")
LIGHT_CHANGE_DIFF = 8.0       # mean |day - frame| per channel, 0-255
DUSK_CHROMA_SHIFT = 0.03      # change in r or b share of land pixels
SEASON_CHROMA_SHIFT = 0.015
_HUD_CROP = (0.2, 0.0, 1.0, 1.0)  # drop the left fifth, where legends usually sit
LEAK_QUESTION = "Are stars, a starfield, or a sky/atmosphere dome visible in any frame, especially the darkest?"
SEASON_ITEMS = ("season_cycle",)
CODE_ONLY = ("cloud_drift_wrap", "season_modulates_weather")

PROMPT = """These are frames of one voxel floating island, captured with its clock pinned.
Time frames: {time_frames} (tod: 0 = midnight, .25 = sunrise, .5 = noon, .75 = sunset
in the harness's intent; the world's own phase may be offset. Brightest = {day}, darkest = {night}).
Season frames: {season_frames}

Answer each question true/false from what you SEE, with <= 15 words on what you saw.
{questions}
- stars_or_atmosphere_dome: {leak}"""


def _land(path: Path):
    from PIL import Image

    im = Image.open(path).convert("RGB")
    w, h = im.size
    return im.crop((int(_HUD_CROP[0] * w), int(_HUD_CROP[1] * h), int(_HUD_CROP[2] * w), int(_HUD_CROP[3] * h)))


def chroma(path: Path) -> tuple[float, float]:
    """(r share, b share) of non-void pixels: color independent of brightness."""
    px = [c for c in _land(path).resize((256, 200)).get_flattened_data() if sum(c) > 30]
    total = sum(sum(c) for c in px) or 1
    return sum(c[0] for c in px) / total, sum(c[2] for c in px) / total


def frame_diff(a: Path, b: Path) -> float:
    from PIL import ImageChops, ImageStat

    return sum(ImageStat.Stat(ImageChops.difference(_land(a), _land(b))).mean) / 3


def _shift(a: tuple[float, float], b: tuple[float, float]) -> float:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def measure(times: dict[str, Path], seasons: dict[str, Path], time: dict) -> tuple[dict[str, bool], dict]:
    day = times.get(f"tod_{time.get('day_tod', 0):.2f}")
    night = times.get(f"tod_{time.get('night_tod', 0):.2f}")
    numbers: dict = {}
    if not day:
        return {k: False for k in MEASURED}, numbers
    diffs = {k: round(frame_diff(day, p), 2) for k, p in times.items() if p != day}
    day_c = chroma(day)
    twilight = {k: round(_shift(day_c, chroma(p)), 4) for k, p in times.items() if p not in (day, night)}
    numbers.update(diff_vs_day=diffs, twilight_chroma_shift=twilight)
    out = {
        "night_dimming": bool(time.get("pinned")),
        "light_follows_sun": any(d >= LIGHT_CHANGE_DIFF for d in diffs.values()),
        "dusk_dawn_tint": any(s >= DUSK_CHROMA_SHIFT for s in twilight.values()),
        "season_world_tint": False,
    }
    if len(seasons) >= 2:
        cs = {k: chroma(p) for k, p in seasons.items()}
        first = next(iter(cs.values()))
        shifts = {k: round(_shift(first, c), 4) for k, c in cs.items()}
        numbers["season_chroma_shift"] = shifts
        out["season_world_tint"] = any(s >= SEASON_CHROMA_SHIFT for s in shifts.values())
    return out, numbers


class Answer(BaseModel):
    id: str
    yes: bool
    seen: str = ""


class CycleVisual(BaseModel):
    answers: list[Answer]


def judge_cycle(html_path: str, model: str | None = None) -> dict:
    """{available, why, items: {id: bool|None}, seen: {id: str}, leak: bool, time: {...}}"""
    manifest = ensure_capture(html_path, model)
    preview = manifest.get("preview", {})
    time = manifest.get("time", {})
    if not preview.get("ok"):
        return {"available": False, "why": "preview_patch_failed", "items": {}, "seen": {}, "leak": False, "time": time}

    times = view_paths(html_path, manifest, "time")
    seasons = view_paths(html_path, manifest, "season")
    ask = {k: q for k, q in QUESTIONS.items() if seasons or k not in SEASON_ITEMS}
    prompt = PROMPT.format(
        time_frames=", ".join(times),
        season_frames=", ".join(seasons) or "(none: the world has no season cycle the patch could pin)",
        day=f"tod_{time.get('day_tod', 0):.2f}",
        night=f"tod_{time.get('night_tod', 0):.2f}",
        questions="\n".join(f"- {k}: {q}" for k, q in ask.items()),
        leak=LEAK_QUESTION,
    )
    log(f"      judge     (vlm) {len(times) + len(seasons)} frames")
    report = invoke_structured(CycleVisual, prompt, [*times.values(), *seasons.values()], model)
    by_id = {a.id: a for a in report.answers}

    items: dict[str, bool | None] = {k: (bool(by_id[k].yes) if k in by_id else False) for k in ask}
    for k in SEASON_ITEMS:
        items.setdefault(k, False)  # no season frames: the world had no season clock to pin
    for k in CODE_ONLY:
        items[k] = None
    measured, numbers = measure(times, seasons, time)
    items.update(measured)
    leak = by_id.get("stars_or_atmosphere_dome")
    return {
        "available": True,
        "why": "",
        "items": items,
        "seen": {k: a.seen for k, a in by_id.items()},
        "measured": numbers,
        "leak": bool(leak and leak.yes),
        "time": time,
    }
