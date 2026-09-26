"""Per-biome visual pass for WC003: which required micro-contents can be seen.

Frames come from the shared capture (daytime, agent-framed biome view plus
the overview). The delta biome also gets the underside/side orbit views and
one extra question: does the ocean run out over the void with nothing under
it? That is where "ocean spread as a void without bedrock" is charged.
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
from llm import load_requirements  # noqa: E402

LABELS = {b["id"]: b["label"] for b in BIOMES}
OCEAN_QUESTION = {
    "ocean_over_void": (
        "Does ocean water extend out beyond the island as a flat sheet over the black void, "
        "with no blocks (sand/stone/bedrock) beneath or around it holding it? "
        "Water visibly pouring off an edge as a waterfall does NOT count."
    )
}


def judge_all(html_path: str, biome_ids: tuple[str, ...], model: str | None = None) -> dict[str, VisualReport | dict]:
    manifest = ensure_capture(html_path, model)
    out: dict[str, VisualReport | dict] = {}
    for i, biome_id in enumerate(biome_ids, 1):
        req = load_requirements(biome_id)
        extra_views = ("direction_bottom", "direction_left") if biome_id == "delta" else ()
        images = biome_images(html_path, manifest, biome_id, *extra_views)
        log(f"      {i}/{len(biome_ids)}  {biome_id}  (vlm, {len(images)} frames)")
        try:
            out[biome_id] = judge_biome(
                LABELS[biome_id],
                images,
                req.get("must_present", []),
                req.get("must_not_present", []),
                OCEAN_QUESTION if biome_id == "delta" else None,
                model,
            )
        except Exception as exc:
            log(f"      {i}/{len(biome_ids)}  {biome_id}  error: {exc}")
            out[biome_id] = {"error": str(exc)[:500]}
    return out
