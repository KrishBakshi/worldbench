"""Per-biome visual pass for WC004: does each entity look and move as it should?

One VLM call per biome (eval/capture/judge.py) judges both:
  - look: every entity against its `looks_like`, on the blind-confirmed biome
    frame and the overview;
  - motion: the capture's near/far bursts of that frame (a couple of seconds
    apart, camera still) plus overlays marking changed pixels in red.

Motion is only judged from frames for entities big enough to see move
(VISUAL_MOTION_KINDS: weather, water, and terrain such as lava/glow). Fauna
and other small movers were "not visible" in most bursts (off-screen or a few
pixels), and a VLM also invented motion for them ("bird perched or
hovering"), so their motion is scored on code alone (grade.py).

grade.py only believes a "moving" answer when the burst's pixels changed.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent))

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))

from eval.capture.judge import (  # noqa: E402
    MotionSighting,
    VisualReport,
    biome_images,
    burst_images,
    confirm,
    judge_biome,
)
from eval.capture.run import BIOMES, ensure_capture  # noqa: E402
from harness.status import log  # noqa: E402
from llm import load_templates  # noqa: E402

LABELS = {b["id"]: b["label"] for b in BIOMES}
VISUAL_MOTION_KINDS = frozenset({"weather", "water", "terrain"})


class MotionReport(BaseModel):
    items: list[MotionSighting]
    motion_fraction: dict[str, float] = {}


def visual_motion_entities(templates: dict) -> list[dict]:
    return [
        e for e in templates.get("entities", [])
        if e.get("requires_motion") and e.get("kind") in VISUAL_MOTION_KINDS
    ]


def judge_all(
    html_path: str, biome_ids: tuple[str, ...], model: str | None = None
) -> tuple[dict[str, VisualReport | dict], dict[str, MotionReport | dict]]:
    """(look reports, motion reports), from one call per biome."""
    manifest = ensure_capture(html_path, model)
    looks: dict[str, VisualReport | dict] = {}
    motions: dict[str, MotionReport | dict] = {}
    for i, biome_id in enumerate(biome_ids, 1):
        templates = load_templates(biome_id)
        images = biome_images(html_path, manifest, biome_id)
        movers = visual_motion_entities(templates)
        bursts, gap = burst_images(html_path, manifest, biome_id)
        log(f"      {i}/{len(biome_ids)}  {biome_id}  (vlm, {len(images) + len(bursts)} frames)")
        try:
            report = judge_biome(
                LABELS[biome_id],
                images,
                templates.get("entities", []),
                templates.get("must_not_present", []),
                model=model,
                motion_items=movers or None,
                bursts=bursts or None,
                burst_gap=gap,
            )
            looks[biome_id] = confirm(report, manifest, biome_id)
        except Exception as exc:
            log(f"      {i}/{len(biome_ids)}  {biome_id}  error: {exc}")
            looks[biome_id] = {"error": str(exc)[:500]}
            motions[biome_id] = {"error": str(exc)[:500]}
            continue
        if not movers:
            continue
        if not bursts:
            motions[biome_id] = {"unavailable": "no confirmed biome frame with a motion burst"}
            continue
        view = manifest["views"].get(f"biome_{biome_id}", {})
        motions[biome_id] = MotionReport(items=report.motion, motion_fraction=dict(view.get("motion_fraction") or {}))
    return looks, motions


def dump_motion(report) -> dict:
    return report.model_dump() if isinstance(report, MotionReport) else report


def load_motion(payload: dict):
    if isinstance(payload, dict) and ("error" in payload or "unavailable" in payload):
        return payload
    return MotionReport.model_validate(payload)
