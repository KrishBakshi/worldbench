"""LLM-as-judge over the source: is this a voxel island in a void, with a real sea?

Replaces voxel_check.py, a regex check that could not tell whether the box
geometry was right: 43 of its 83 pattern branches matched exactly one
model's file, and renaming variables (which changes nothing about the world)
moved scores by up to 14/38. A judge that reads the code does not depend on
what the helpers are called.

The judge returns a probability per item plus a verbatim quote. Points are
probability-weighted, and a quote that is not in the source (eval/evidence.py)
earns nothing, so the judge cannot talk a world into points.

`water_bed` / `water_physics` below 0.5 are reported in `missing` but no
longer drive the island gate in eval/score.py: the frames decide that
(visual_check.py's ocean_void).

    uv run python tests/WC000_voxel_world/voxel_judge.py [world.html] [out_dir]
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, Field

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))

from eval.capture.llm import invoke_structured  # noqa: E402
from eval.evidence import in_source, normalize, strip_to_js  # noqa: E402

PASS_PROBABILITY = 0.5

# 20 points. Island physics outweighs the lattice, as it did in the regex version.
ITEMS = [
    {"id": "cube_primitive", "points": 1, "label": "Terrain is built from cube primitives (BoxGeometry or 8-corner cube faces), not only spheres/planes"},
    {"id": "bulk_placement", "points": 1, "label": "Cubes are placed in bulk over the island (cell loops, InstancedMesh of boxes, merged cube buffers)"},
    {"id": "discrete_grid", "points": 1, "label": "Land sits on a discrete cell grid, not continuous vertex displacement of a plane"},
    {"id": "stacked_columns", "points": 1, "label": "Columns and cliffs are stacks of unit cubes, not one stretched prism per cell"},
    {"id": "cube_terrain", "points": 1, "label": "The ground itself is cubes (a sun or UI may use planes)"},
    {"id": "grid_aligned", "points": 1, "label": "Land cubes snap to integer cell positions; no fractional offsets or random world-space cubes"},
    {"id": "unit_voxels", "points": 1, "label": "One cell size for land/structure cubes, not scaled blobs"},
    {"id": "contained_water", "points": 2, "label": "An ocean or river is actually built"},
    {"id": "water_physics", "points": 3, "label": "Every water body is supported: resting on blocks or walled by a solid rim, or visibly falling (waterfalls off edges). Static water is fine; this is about support, not simulation"},
    {"id": "water_bed", "points": 5, "label": "Still water sits on solid terrestrial blocks (sand/stone/dirt/bedrock) beneath it, not a flat sheet over the void"},
    {"id": "grounded_props", "points": 3, "label": "Flora, fauna and structures are placed on the island's own cells, not thrown at random world coordinates"},
]
MAX_SCORE = sum(item["points"] for item in ITEMS)

PROMPT = """You judge the source of a Three.js world that was asked to be a Minecraft-like
voxel floating island in a black void, with an ocean that has a solid seabed and
pours off the island's edges.

For each item, read the code and return:
- probability: 0..1 that the built world satisfies the item (judge what the code
  BUILDS, not comments, UI labels, or variable names).
- evidence: ONE line (or a few consecutive lines) copied character-for-character
  from SOURCE. It is checked against the source: stitching pieces of different
  lines together, or paraphrasing, scores zero. Empty if none.
- reason: <= 20 words.

Be skeptical: a flat water plane at sea level with no blocks under it is a sheet
over the void (low water_bed). A heightfield built from one tall box per cell is
not stacked columns.

ITEMS:
{items}

SOURCE:
{source}
"""


@dataclass
class CheckResult:
    passed: bool
    reason: str
    details: dict = field(default_factory=dict)


class ItemVerdict(BaseModel):
    id: str
    probability: float = Field(ge=0, le=1)
    evidence: str = ""
    reason: str = ""


class VoxelVerdict(BaseModel):
    items: list[ItemVerdict]


def grade(verdict: VoxelVerdict, source: str) -> dict:
    by_id = {v.id: v for v in verdict.items}
    src = normalize(source)
    rows, earned_total = [], 0.0
    missing: list[str] = []
    for item in ITEMS:
        v = by_id.get(item["id"])
        prob = v.probability if v else 0.0
        quoted = bool(v and v.evidence)
        verified = quoted and in_source(v.evidence, src)
        # Probability only turns into points when the quote backing it is real.
        earned = round(item["points"] * prob, 2) if verified else 0.0
        earned_total += earned
        passed = verified and prob >= PASS_PROBABILITY
        if not passed:
            missing.append(item["id"])
        rows.append({
            "id": item["id"],
            "label": item["label"],
            "points": item["points"],
            "probability": prob,
            "evidence_verified": verified,
            "earned": earned,
            "passed": passed,
            "why": "" if passed else ("unverified_evidence" if quoted and not verified and prob >= PASS_PROBABILITY else "low_probability"),
            "evidence": v.evidence if v else "",
            "reason": v.reason if v else "no verdict",
        })
    score = round(earned_total, 2)
    return {"score": score, "max_score": MAX_SCORE, "items": rows, "missing": missing}


def check_voxel_judge(html_path: str, out_dir: Path | None = None, model: str | None = None) -> CheckResult:
    source = strip_to_js(html_path)
    items = "\n".join(f"- {i['id']}: {i['label']}" for i in ITEMS)
    verdict = invoke_structured(VoxelVerdict, PROMPT.replace("{items}", items).replace("{source}", source), model=model)
    card = grade(verdict, source)
    passed = not card["missing"]
    reason = (
        f"Scored {card['score']}/{MAX_SCORE}: voxel island with a seabed"
        if passed
        else f"Scored {card['score']}/{MAX_SCORE}; below {PASS_PROBABILITY}: {', '.join(card['missing'])}"
    )
    dest = Path(out_dir) if out_dir is not None else Path(html_path).parent
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "voxel_judge.json").write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    return CheckResult(passed, reason, {
        "score": card["score"],
        "max_score": MAX_SCORE,
        "missing": card["missing"],
        "scorecard": card,
        "artifacts": {"report": "voxel_judge.json"},
    })


if __name__ == "__main__":
    from harness.status import log

    html_path = sys.argv[1] if len(sys.argv) > 1 else "inputs/opus-5/world.html"
    out_dir = Path(sys.argv[2]) / f"{Path(html_path).parent.name}__WC000_voxel_world" if len(sys.argv) > 2 else None
    log(f"WC000  voxel judge  {html_path}")
    result = check_voxel_judge(html_path, out_dir)
    print(f"passed={result.passed} score={result.details['score']}/{result.details['max_score']}")
    print(result.reason)
