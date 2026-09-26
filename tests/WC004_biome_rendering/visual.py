"""Per-biome visual pass for WC004: does each entity LOOK like what it should?

Same shared frames and judge as WC003 (eval/capture/judge.py), fed this
test's templates.json, where each entity's `looks_like` is the description
the judge checks against. Motion is not judged here: a still frame cannot
show which way rain falls, so motion stays with the code probe.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))

from eval.capture.judge import VisualReport, biome_images, judge_biome  # noqa: E402
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
