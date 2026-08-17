"""Is world.html a voxel (cube-grid) island, not box-art / a heightfield of stretched prisms?

A voxel world places **unit cubes on an integer lattice** (gx, gy, gz) × cell size.
Having BoxGeometry somewhere is not enough: random world-space cubes, fractional
cell offsets, and one tall prism per column are the usual misses.

    uv run python tests/WC000_voxel_world/voxel_check.py [world.html] [out_dir]
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CheckResult:
    passed: bool
    reason: str
    details: dict = field(default_factory=dict)


POINTS_PER_ITEM = 2

ITEMS = [
    {
        "id": "cube_primitive",
        "label": "Cube primitive (BoxGeometry / 8-corner cube faces), not only spheres/planes",
    },
    {
        "id": "bulk_placement",
        "label": "Bulk cube placement over the island (nested cell loop or InstancedMesh of boxes)",
    },
    {
        "id": "discrete_grid",
        "label": "Discrete grid / cell size (not continuous vertex displacement as the land)",
    },
    {
        "id": "stacked_columns",
        "label": "Y-loop of unit cubes for columns/cliffs — not one stretched prism per cell",
    },
    {
        "id": "cube_terrain",
        "label": "Land is cubes (plane water/sun is fine); ground is not only a displaced plane",
    },
    {
        "id": "grid_aligned",
        "label": "Cubes snap to the cell lattice — no fractional cells or dart-throw world coords",
    },
    {
        "id": "unit_voxels",
        "label": "One cell size for land/structure cubes — not scaled blobs or CELL×height×CELL columns",
    },
]

_CUBE = re.compile(
    r"BoxGeometry\s*\("
    r"|BoxBufferGeometry\s*\("
    r"|\[\s*-h\s*,\s*-h\s*,\s*-h\s*\]",
    re.I,
)
_CUBE_LAND = re.compile(
    r"BoxGeometry\s*\(\s*(?:BLOCK_SIZE|VOXEL|CELL|BS|1)\s*"
    r"(?:\s*\*\s*0\.9\d*)?\s*,\s*(?:BLOCK_SIZE|VOXEL|CELL|BS|1)"
    r"|\baddBlock\s*\(\s*(?:gx|x)\s*,\s*(?:gy|y)\s*,\s*(?:gz|z)",
    re.I,
)
_NESTED_FOR = re.compile(
    r"for\s*\([^)]+\)\s*\{?\s*for\s*\([^)]+\)",
    re.I | re.S,
)
_INSTANCED = re.compile(r"InstancedMesh\s*\(", re.I)
_PLACE = re.compile(
    r"\baddBlock\s*\(|\bplaceBlock\s*\(|\baddO\s*\(|\bpb\s*\(|voxelData\.push|"
    r"\bterra\.add\s*\(|\bsetMatrixAt\s*\(|\bqueue\s*\(",
    re.I,
)
_GRID = re.compile(
    r"\b(?:VOXEL|BLOCK_SIZE|BLOCKSIZE|GRID_SIZE|GRID_HALF|WORLD_SIZE|CELL_SIZE)\b"
    r"|\b(?:const|let|var)\s+(?:GRID|BS|VOXEL|CELL|NX|NZ|W|H)\s*="
    r"|\b(?:const|let|var)\s+N\s*=\s*\d{2,}"
    r"|heightMap\s*="
    r"|hGrid\s*="
    r"|cellH\s*="
    r"|Float32Array\s*\(\s*\w+\s*\*\s*\w+",
    re.I,
)
_STEP_XZ = re.compile(
    r"for\s*\([^)]*(?:x\s*\+=|z\s*\+=)",
    re.I,
)
# Real stacking: a for-y loop, and a cube placed at that y.
_Y_FOR = re.compile(r"for\s*\(\s*(?:(?:let|var|const)\s+)?(?:y|dy|iy)\b", re.I)
_Y_PLACE = re.compile(
    r"(?:addBlock|placeBlock|addO|addW|addL|fadd|queue|pb|terra\.add|"
    r"voxelData\.push|blocks\.push|waterBlocks\.push)\s*\(\s*"
    r"(?:wx\s*,\s*y\b|x\s*,\s*y\b|gx\s*,\s*(?:gy|y)\b|col\s*,\s*x\s*,\s*y\b"
    r"|x\s*,\s*y\b|[^\n]{0,40}\by\b)",
    re.I,
)
_PLANE_SEGMENTED = re.compile(
    r"PlaneGeometry\s*\([^)]*,\s*\d{2,}\s*,\s*\d{2,}\s*\)",
    re.I,
)
_SNAPPED = re.compile(
    r"\b(?:wx|wz|wy)\s*\(\s*[A-Za-z_]\w*\s*\)"
    r"|(?:\bg[xyz]\b|\bix\b|\biz\b)\s*\*\s*(?:CELL|VOXEL|BS|BLOCK)"
    r"|\(\s*(?:gx|x)\s*-\s*HALF",
    re.I,
)
# Off the lattice: fractional cells, random world-space cubes, y+0.5 placements.
_OFF_GRID = re.compile(
    r"\b(?:wx|wz)\s*\(\s*[^)]*?(?:"
    r"[xz]\s*\+\s*(?:dx|dz)\s*\*\s*0\."
    r"|[xz]\s*[+\-]\s*0\.\d"
    r")"
    r"|\b(?:add|fadd|pb|addBlock|queue)\s*\(\s*[^;]{0,200}?"
    r"(?:[xz]\s*\+\s*(?:dx|dz)\s*\*\s*0\.|[xz]\s*\+\s*\d*\.\d)"
    r"|\b(?:add|fadd|pb|addBlock|queue|terra\.add)\s*\(\s*[^;]{0,120}?"
    r"(?:[yYh]|baseY|th)\s*\+\s*0\.\d"
    r"|\b(?:add|fadd|addBlock|queue)\s*\(\s*(?:fx|fy|fz)\b"
    r"|\bb\s*\(\s*rnd\s*\(",
    re.I | re.S,
)
# Land/structure cubes that are not one cell: stretch API, scaled addBlock, patch 4×h×4.
_STRETCHED = re.compile(
    r"function addBlock\s*\([^)]*sX\s*=\s*1"
    r"|function queue\s*\([^)]*sy\s*=\s*1"
    r"|function b\s*\(\s*x\s*,\s*y\s*,\s*z\s*,\s*sx\s*,\s*sy\s*,\s*sz"
    r"|scale\.set\s*\(\s*sX\s*,\s*sY\s*,\s*sZ\s*\)"
    r"|dummy\.scale\.setScalar\s*\(\s*s\b"
    r"|\bpb\s*\(\s*land\b[^;]{0,120}CELL\s*,\s*\("
    r"|terra\.add\s*\([^;]{0,100},\s*1\s*,\s*hh\s*,\s*1"
    r"|addBlock\s*\([^)]*,\s*(?:[2-9]|0\.\d)[^)]*,\s*(?:[2-9]|1\.\d|0\.)"
    r"|b\s*\(\s*[^,]+,\s*[^,]+-\s*h\s*/\s*2\s*,[^,]+,\s*4\s*,\s*h\s*,\s*4"
    r"|queue\s*\([^)]*,\s*1\s*\+\s*Math\.random",
    re.I | re.S,
)


def strip_to_js(html_path: str) -> str:
    raw = Path(html_path).read_text(encoding="utf-8", errors="ignore")
    no_css = re.sub(r"<style\b[^>]*>.*?</style>", "", raw, flags=re.I | re.S)
    scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", no_css, flags=re.I | re.S)
    js = "\n\n".join(s.strip() for s in scripts if s.strip())
    return js or no_css


def _snippet(text: str, match: re.Match | None, width: int = 160) -> str:
    if match is None:
        return ""
    start = max(0, match.start() - 20)
    end = min(len(text), match.end() + width)
    return re.sub(r"\s+", " ", text[start:end]).strip()[:200]


def _hits(text: str) -> dict[str, tuple[bool, str, str]]:
    cube = _CUBE_LAND.search(text) or _CUBE.search(text)
    nested = _NESTED_FOR.search(text)
    instanced = _INSTANCED.search(text)
    place = _PLACE.search(text)
    grid = _GRID.search(text) or _STEP_XZ.search(text)
    y_for = _Y_FOR.search(text)
    y_place = _Y_PLACE.search(text)
    y_stack = y_for if (y_for and y_place) else None
    bulk = bool(nested and (instanced or place or cube))
    bulk_ev = nested or instanced or place
    cube_land = bool(cube and bulk)
    plane = _PLANE_SEGMENTED.search(text)
    if cube_land:
        terrain_ok, terrain_ev = True, cube or bulk_ev
    elif plane and not bulk:
        terrain_ok, terrain_ev = False, plane
    else:
        terrain_ok, terrain_ev = cube_land, cube

    off = _OFF_GRID.search(text)
    snapped = _SNAPPED.search(text)
    if off:
        aligned_ok, aligned_ev, aligned_why = False, off, "off_grid"
    elif snapped or grid:
        aligned_ok, aligned_ev, aligned_why = True, snapped or grid, ""
    else:
        aligned_ok, aligned_ev, aligned_why = False, snapped, "not_found"

    stretched = _STRETCHED.search(text)
    if stretched:
        unit_ok, unit_ev, unit_why = False, stretched, "stretched"
    else:
        unit_ok, unit_ev, unit_why = bool(cube), cube, "" if cube else "not_found"

    stack_why = "" if y_stack else "no_y_loop"

    return {
        "cube_primitive": (bool(cube), _snippet(text, cube), "" if cube else "not_found"),
        "bulk_placement": (bulk, _snippet(text, bulk_ev), "" if bulk else "not_found"),
        "discrete_grid": (bool(grid), _snippet(text, grid), "" if grid else "not_found"),
        "stacked_columns": (bool(y_stack), _snippet(text, y_stack), stack_why),
        "cube_terrain": (
            terrain_ok,
            _snippet(text, terrain_ev if terrain_ok else plane or cube),
            "" if terrain_ok else "not_found",
        ),
        "grid_aligned": (aligned_ok, _snippet(text, aligned_ev), aligned_why),
        "unit_voxels": (unit_ok, _snippet(text, unit_ev), unit_why),
    }


def check_voxel_world(html_path: str, out_dir: Path | None = None) -> CheckResult:
    text = strip_to_js(html_path)
    hits = _hits(text)

    found, missing = {}, {}
    earned, lost = [], []
    item_cards = {}
    for item in ITEMS:
        ok, evidence, why = hits[item["id"]]
        row = {
            "id": item["id"],
            "label": item["label"],
            "kind": "must_present",
            "points": POINTS_PER_ITEM,
            "evidence": evidence,
        }
        if ok:
            found[item["id"]] = evidence
            earned.append(row)
            item_cards[item["id"]] = {
                "score": POINTS_PER_ITEM,
                "max_score": POINTS_PER_ITEM,
                "passed": True,
                "earned": [row],
                "lost": [],
            }
        else:
            missing[item["id"]] = why or "not found"
            row = {**row, "why": why or "not_found"}
            lost.append(row)
            item_cards[item["id"]] = {
                "score": 0,
                "max_score": POINTS_PER_ITEM,
                "passed": False,
                "earned": [],
                "lost": [row],
            }

    score = POINTS_PER_ITEM * len(earned)
    max_score = POINTS_PER_ITEM * len(ITEMS)
    passed = not missing
    reason = (
        "Voxel island: cubes on a grid"
        if passed
        else f"Scored {score}/{max_score}; missing: {', '.join(missing)}"
    )
    scorecard = {
        "score": score,
        "max_score": max_score,
        "points_per_item": POINTS_PER_ITEM,
        "passed": passed,
        "reason": reason,
        "earned": earned,
        "lost": lost,
        "items": item_cards,
    }
    result = CheckResult(
        passed,
        reason,
        {
            "found": found,
            "missing": list(missing),
            "score": score,
            "max_score": max_score,
            "scorecard": scorecard,
        },
    )
    dest = Path(out_dir) if out_dir is not None else Path(html_path).parent
    dest.mkdir(parents=True, exist_ok=True)
    score_path = dest / "score.json"
    score_path.write_text(json.dumps(scorecard, indent=2) + "\n", encoding="utf-8")
    result.details["artifacts"] = {"score": score_path.name}
    return result


if __name__ == "__main__":
    html_path = sys.argv[1] if len(sys.argv) > 1 else "dry_runs/inputs/fable/world.html"
    out_dir = None
    if len(sys.argv) > 2:
        out_dir = Path(sys.argv[2]) / f"{Path(html_path).parent.name}__WC000_voxel_world"
        out_dir.mkdir(parents=True, exist_ok=True)
    result = check_voxel_world(html_path, out_dir=out_dir)
    dest = out_dir if out_dir is not None else Path(html_path).parent
    print(f"passed={result.passed} score={result.details['score']}/{result.details['max_score']}")
    print(result.reason)
    if result.details.get("missing"):
        print(result.details["missing"])
    print(f"{dest}/score.json")
