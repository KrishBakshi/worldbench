"""Per-biome visual pass for WC004: does each entity look and move as it should?

Look: same shared frames and judge as WC003 (eval/capture/judge.py), fed
this test's templates.json, where `looks_like` is what the judge checks.

Motion: the capture takes two bursts of each biome from the daytime preview,
"near" (the navigator's framing) and "far" (zoomed out), frames a couple of
seconds apart with the camera still, plus an overlay marking changed pixels
in red. judge_motion() asks the VLM, per moving entity, whether it moves
between frames and on which axis. grade.py only believes a "moving" answer
when the burst's pixels really changed.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))

from pydantic import BaseModel  # noqa: E402

from eval.capture.judge import VisualReport, biome_images, judge_biome  # noqa: E402
from eval.capture.llm import invoke_structured  # noqa: E402
from eval.capture.run import BIOMES, ensure_capture  # noqa: E402
from harness.status import log  # noqa: E402
from llm import load_templates  # noqa: E402

LABELS = {b["id"]: b["label"] for b in BIOMES}


def judge_all(html_path: str, biome_ids: tuple[str, ...], model: str | None = None) -> dict[str, VisualReport | dict]:
    manifest = ensure_capture(html_path, model)
    out: dict[str, VisualReport | dict] = {}
    for i, biome_id in enumerate(biome_ids, 1):
        templates = load_templates(biome_id)
        images = biome_images(html_path, manifest, biome_id)
        log(f"      {i}/{len(biome_ids)}  {biome_id}  (vlm, {len(images)} frames)")
        try:
            out[biome_id] = judge_biome(
                LABELS[biome_id],
                images,
                templates.get("entities", []),
                templates.get("must_not_present", []),
                model=model,
            )
        except Exception as exc:
            log(f"      {i}/{len(biome_ids)}  {biome_id}  error: {exc}")
            out[biome_id] = {"error": str(exc)[:500]}
    return out


MOTION_PROMPT = """Frames of one voxel floating island, biome under test: {label}.
The camera does not move within a burst; frames are {gap}s apart.
- near_*: zoomed in on {label}, in time order.
- far_*: zoomed out, in time order.
- *_motion: the first frame of that burst, dimmed, with every pixel that changed
  during the burst painted RED. Red marks where something changed:
  small scattered red specks are usually moving particles (rain, snow, ash);
  large flat red patches over terrain are usually light, cloud-shadow or fog
  changes, NOT an entity moving. Judge motion from the frames, using red only
  as a hint where to look.

For every ENTITY, judge only what you can see in {label}:
- moving: does it visibly move or change between frames?
- axis: how it moves, one of: falling, blowing, rising, flowing, pulsing, still, grounded.
  still = present but hanging in place (mist, fog). grounded = walks/idles on the ground.
- seen: <= 15 words.
If an entity is not visible at all, moving=false, axis="still", seen="not visible".

ENTITIES:
{entities}"""


class MotionSighting(BaseModel):
    id: str
    moving: bool
    axis: str = "still"
    seen: str = ""


class MotionReport(BaseModel):
    items: list[MotionSighting]
    motion_fraction: dict[str, float] = {}


def judge_motion(html_path: str, biome_ids: tuple[str, ...], model: str | None = None) -> dict[str, MotionReport | dict]:
    manifest = ensure_capture(html_path, model)
    cap_dir = Path(html_path).parent / "capture"
    out: dict[str, MotionReport | dict] = {}
    for i, biome_id in enumerate(biome_ids, 1):
        moving = [e for e in load_templates(biome_id).get("entities", []) if e.get("requires_motion")]
        view = manifest.get("views", {}).get(f"biome_{biome_id}") or {}
        if not moving:
            continue
        if not view.get("bursts"):
            out[biome_id] = {"unavailable": "no motion burst for this biome (not framed, or burst failed)"}
            continue
        images: dict[str, Path] = {}
        for label, frames in view["bursts"].items():
            for n, rel in enumerate(frames):
                images[f"{label}_{n}"] = cap_dir / rel
            images[f"{label}_motion"] = cap_dir / view["overlays"][label]
        entities = "\n".join(f"- {e['id']}: {e.get('looks_like') or e.get('label','')} (expected: {e.get('expected_axis')})" for e in moving)
        log(f"      {i}/{len(biome_ids)}  {biome_id}  motion (vlm, {len(images)} frames)")
        try:
            report = invoke_structured(
                MotionReport,
                MOTION_PROMPT.format(label=LABELS[biome_id], gap=view.get("burst_gap_s", "?"), entities=entities),
                list(images.values()),
                model,
            )
            report.motion_fraction = dict(view.get("motion_fraction") or {})
            out[biome_id] = report
        except Exception as exc:
            log(f"      {i}/{len(biome_ids)}  {biome_id}  motion error: {exc}")
            out[biome_id] = {"error": str(exc)[:500]}
    return out


def dump_motion(report) -> dict:
    return report.model_dump() if isinstance(report, MotionReport) else report


def load_motion(payload: dict):
    if isinstance(payload, dict) and ("error" in payload or "unavailable" in payload):
        return payload
    return MotionReport.model_validate(payload)
