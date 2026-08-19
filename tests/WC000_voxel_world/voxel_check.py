"""Is world.html a voxel (cube-grid) island, not box-art / a heightfield of stretched prisms?

A voxel world places **unit cubes on an integer lattice** (gx, gy, gz) × cell size.
Having BoxGeometry somewhere is not enough: random world-space cubes, fractional
cell offsets, and one tall prism per column are the usual misses.

The island is a finite mass in a void. Fluids stay up if they are held (a sheet
or a solid bed) or they fall (a waterfall off the rim). A held slab is a
barrier, not a seafloor: still water must sit on sand, stone, dirt, or bedrock.
Flora/fauna sit on that mass.

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


# Lattice items: did they draw cubes. Island-physics items: is it a mass in a
# void with a real sea — those carry the score.
LATTICE_POINTS = 2
ITEMS = [
    {
        "id": "cube_primitive",
        "points": LATTICE_POINTS,
        "label": "Cube primitive (BoxGeometry / 8-corner cube faces), not only spheres/planes",
    },
    {
        "id": "bulk_placement",
        "points": LATTICE_POINTS,
        "label": "Bulk cube placement over the island (nested cell loop or InstancedMesh of boxes)",
    },
    {
        "id": "discrete_grid",
        "points": LATTICE_POINTS,
        "label": "Discrete grid / cell size (not continuous vertex displacement as the land)",
    },
    {
        "id": "stacked_columns",
        "points": LATTICE_POINTS,
        "label": "Y-loop of unit cubes for columns/cliffs, not one stretched prism per cell",
    },
    {
        "id": "cube_terrain",
        "points": LATTICE_POINTS,
        "label": "Land is cubes (sun may be a plane); ground is not only a displaced plane",
    },
    {
        "id": "grid_aligned",
        "points": LATTICE_POINTS,
        "label": "Cubes snap to the cell lattice, no fractional cells or dart-throw world coords",
    },
    {
        "id": "unit_voxels",
        "points": LATTICE_POINTS,
        "label": "One cell size for land/structure cubes, not scaled blobs or CELL x height x CELL columns",
    },
    {
        "id": "contained_water",
        "points": 4,
        "label": "Ocean/river exists on the island (cell cubes or a held sheet)",
    },
    {
        "id": "water_physics",
        "points": 6,
        "label": "In a void, water is held (bed or sheet) or it falls; it does not hover unsupported",
    },
    {
        "id": "water_bed",
        "points": 10,
        "label": "Still water sits on solid ground (sand, stone, dirt, bedrock), not only a tray in the void",
    },
    {
        "id": "grounded_props",
        "points": 4,
        "label": "Flora/fauna/particles sit on the island mass, not thrown into empty space",
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
# A wide thin volume can hold water in a void (a tray), same as a bed of cubes.
_SLAB_CALL = re.compile(
    r"\bslab\s*\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)",
    re.I,
)
_NUMERIC_BOX = re.compile(
    r"BoxGeometry\s*\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)",
    re.I,
)
_WATER_PLANE = re.compile(
    r"(?:ocean|water|sea|lagoon|WAT)\w*.{0,120}PlaneGeometry"
    r"|PlaneGeometry.{0,80}(?:ocean|water|sea|lagoon)",
    re.I | re.S,
)
# Water that actually gets built — not a legend label alone.
_WATER_EXISTS = re.compile(
    r"\b(?:WK|WAT|waterBlocks|addW|WATER_LEVEL|OCEAN_LEVEL|waterfallGroup|fallSpots|fallSites)\b"
    r"|waterfalls\.push"
    r"|buildWaterfalls?\s*\("
    r"|function\s+\w*Water\w*\s*\("
    r"|instanceData\s*\[\s*['\"]water"
    r"|addBlock\s*\([^;]{0,80}['\"]water"
    r"|['\"]waterfall['\"]"
    r"|surface\s*=\s*['\"]ocean['\"]"
    r"|===\s*['\"]ocean['\"]"
    r"|biome\s*===\s*B\.OCEAN"
    r"|topColor\s*=\s*C\.ocean"
    r"|s\.water"
    r"|PALETTE\.ocean"
    r"|materials\s*\[\s*['\"]water",
    re.I,
)
# Fluid vs ground — words, not helper APIs.
_WATER_WORD = re.compile(
    r"\b(?:water|ocean|sea|lagoon|swampWater|swampW)\b"
    r"|\b(?:addW|waterBlocks|WATER_LEVEL|OCEAN_LEVEL|WAT|WK|waterCol|waterY|waterTop)\b",
    re.I,
)
_SOLID_WORD = re.compile(
    r"\b(?:sand|stone|dirt|rock|bedrock|gravel|clay|basalt|ash)\b",
    re.I,
)
_PLACE_CALL = re.compile(
    r"\b(?:addBlock|placeBlock|addO|addW|addL|fadd|queue|pb|terra\.add|add)\s*\("
    r"|(?:blocks|waterBlocks|voxelData)\.push\s*\(",
    re.I,
)
# Water y locked to land y (basin). Array form is the bed; waterline form needs a solid place.
_BASIN_LOCK = re.compile(
    r"(?:WAT|water|WK)\s*\[[^\]]{0,16}\]\s*<=\s*(?:H|height)\s*\["
    r"|(?:H|height)\s*\[[^\]]{0,16}\]\s*=\s*(?:WAT|water)\s*\[[^\]]{0,16}\]\s*-\s*1"
    r"|(?:wt|waterTop|waterY)\s*-\s*(?:s\.h|\bh\b|height|cellH)\b"
    r"|(?:s\.h|cellH)\s*<\s*(?:wt|waterTop|waterY)\b",
    re.I,
)
_WATERLINE_LOCK = re.compile(
    r"\b(?:h|height|cellH|groundH)\s*<=?\s*(?:WY|SEA|WATER_LEVEL|OCEAN_LEVEL|wl|waterY|wt)\b",
    re.I,
)
# Two place calls, same cell: fluid at y, a different cube at y-1 (not a second water add).
_STACKED_PLACE = re.compile(
    r"(?:addBlock|placeBlock|addO|addW|queue|pb|terra\.add|add)\s*\(\s*"
    r"(?:x|wx|gx)\s*,\s*(?:h|y|wy|WATER_LEVEL|SEA|WY|wt)\s*,"
    r".{0,220}?"
    r"(?:addBlock|placeBlock|addO|queue|pb|terra\.add|add)\s*\(\s*"
    r"(?:x|wx|gx)\s*,\s*(?:h|y|wy)\s*-\s*1\s*,",
    re.I | re.S,
)
_FOR_OPEN = re.compile(r"\bfor\s*\(", re.I)


def _for_header_end(text: str, open_paren: int) -> int:
    """Index of the `)` that closes `for (` at open_paren, skipping nested parens."""
    depth = 0
    for i in range(open_paren, min(len(text), open_paren + 200)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _column_seafloor(text: str) -> re.Match | None:
    """A y-loop that places both fluid and a terrestrial solid (same column)."""
    for match in _FOR_OPEN.finditer(text):
        end = _for_header_end(text, match.end() - 1)
        if end < 0:
            continue
        header = text[match.end() : end]
        if not re.search(r"\by\b", header):
            continue
        rest = text[end + 1 : end + 12]
        brace = rest.find("{")
        if brace < 0:
            continue
        brace_idx = end + 1 + brace
        pre = text[max(0, match.start() - 420) : match.start()]
        body = _brace_body(text, brace_idx)
        chunk = _without_comments(pre + "\n" + body)
        if _WATER_WORD.search(chunk) and _SOLID_WORD.search(chunk) and _PLACE_CALL.search(body):
            return match
    return None
# No tray: water must pour — a y-column placing water, or a waterfall identifier plus a loop.
_WATER_FALL = re.compile(
    r"function\s+\w*waterfall\w*"
    r"|waterfallGroup"
    r"|waterfalls\.push"
    r"|fallSpots"
    r"|fallSites"
    r"|\bfalls\.push"
    r"|['\"]waterfall['\"]"
    r"|waterfall\w*.{0,120}for\s*\("
    r"|for\s*\([^)]*\by\b[^)]*(?:y--|y\s*-=|>=\s*[-~])[^)]*\)\s*\{[^}]{0,280}"
    r"(?:addW|addBlock|queue|waterBlocks|waterfall)",
    re.I | re.S,
)
# Dart into world space with no land lookup is decoration in the void.
_DART = re.compile(
    r"Math\.random\s*\(\s*\)\s*\*\s*(?:GRID|WORLD_SIZE|NX|NZ)\b"
    r"|Math\.floor\s*\(\s*Math\.random\s*\(\s*\)\s*\*\s*(?:GRID|NX|NZ)",
    re.I,
)
_LAND_GUARD = re.compile(
    r"biomeMap|heightMap|cellH|getHeight|BIO\s*\[|H\s*\[|inb\s*\("
    r"|biome\s*===|surface\s*!==|hGrid",
    re.I,
)
_VOID_POSITION = re.compile(
    r"position\.set\s*\(\s*Math\.random",
    re.I,
)


def strip_to_js(html_path: str) -> str:
    raw = Path(html_path).read_text(encoding="utf-8", errors="ignore")
    no_css = re.sub(r"<style\b[^>]*>.*?</style>", "", raw, flags=re.I | re.S)
    scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", no_css, flags=re.I | re.S)
    js = "\n\n".join(s.strip() for s in scripts if s.strip())
    return js or no_css


def _without_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"//[^\n]*", " ", text)


def _brace_body(text: str, open_idx: int, limit: int = 900) -> str:
    """Body after `{` at open_idx, brace-matched, capped so one loop stays local."""
    if open_idx >= len(text) or text[open_idx] != "{":
        return ""
    depth = 0
    for i in range(open_idx, min(len(text), open_idx + limit)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1 : i]
    return text[open_idx + 1 : min(len(text), open_idx + limit)]


def _block_with_solid_place(text: str, match: re.Match) -> bool:
    """Height lock only counts if this branch also places a non-water solid."""
    start = match.start()
    window = text[start : min(len(text), start + 500)]
    cut = re.search(r"\bcontinue\b|\breturn\b", window)
    if cut:
        window = window[: cut.start()]
    if not _PLACE_CALL.search(window):
        return False
    return bool(_SOLID_WORD.search(window))


def _find_seafloor(text: str) -> re.Match | None:
    """Still water sits on ground: basin lock, waterline+solid, column fill, or y / y-1 places."""
    code = _without_comments(text)
    basin = _BASIN_LOCK.search(code)
    if basin:
        return basin
    waterline = _WATERLINE_LOCK.search(code)
    if waterline and _block_with_solid_place(code, waterline):
        return waterline
    stacked = _STACKED_PLACE.search(code)
    if stacked and _WATER_WORD.search(stacked.group(0)):
        return stacked
    return _column_seafloor(code)


def _is_sheet(a: float, b: float, c: float) -> bool:
    """Two large axes + one thin axis = a tray that can hold water, not a sun cube."""
    dims = sorted((a, b, c))
    return dims[0] <= 8 and dims[1] >= 12 and dims[2] >= 16


def _held_sheet(text: str) -> re.Match | None:
    """A water tray in the void: slab() sheet, or a water-named plane / box."""
    for match in _SLAB_CALL.finditer(text):
        if _is_sheet(float(match.group(1)), float(match.group(2)), float(match.group(3))):
            return match
    for match in _NUMERIC_BOX.finditer(text):
        if not _is_sheet(float(match.group(1)), float(match.group(2)), float(match.group(3))):
            continue
        window = text[max(0, match.start() - 100) : match.end() + 120]
        if re.search(r"water|ocean|sea|lagoon", window, re.I):
            return match
    return _WATER_PLANE.search(text)


def _ungrounded_dart(text: str) -> re.Match | None:
    """Random world coords with no height/biome lookup land in empty space."""
    void = _VOID_POSITION.search(text)
    if void:
        return void
    for match in _DART.finditer(text):
        window = text[match.end() : match.end() + 280]
        if not _LAND_GUARD.search(window):
            return match
    return None


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

    sheet = _held_sheet(text)
    falling = _WATER_FALL.search(text)
    water = _WATER_EXISTS.search(text) or sheet or falling
    seafloor = _find_seafloor(text)
    if water:
        contained_ok, contained_ev, contained_why = True, water, ""
        hold = sheet or seafloor or falling
        if hold:
            physics_ok, physics_ev, physics_why = True, hold, ""
        else:
            physics_ok, physics_ev, physics_why = False, water, "unsupported_fluid"
        if seafloor:
            floor_ok, floor_ev, floor_why = True, seafloor, ""
        else:
            floor_ok, floor_ev, floor_why = False, sheet or water, "no_seafloor"
    else:
        contained_ok, contained_ev, contained_why = False, None, "not_found"
        physics_ok, physics_ev, physics_why = False, None, "not_found"
        floor_ok, floor_ev, floor_why = False, None, "not_found"

    dart = _ungrounded_dart(text)
    if dart:
        grounded_ok, grounded_ev, grounded_why = False, dart, "dart_throw"
    elif nested:
        grounded_ok, grounded_ev, grounded_why = True, nested, ""
    else:
        grounded_ok, grounded_ev, grounded_why = False, None, "not_found"

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
        "contained_water": (contained_ok, _snippet(text, contained_ev), contained_why),
        "water_physics": (physics_ok, _snippet(text, physics_ev), physics_why),
        "water_bed": (floor_ok, _snippet(text, floor_ev), floor_why),
        "grounded_props": (grounded_ok, _snippet(text, grounded_ev), grounded_why),
    }


def check_voxel_world(html_path: str, out_dir: Path | None = None) -> CheckResult:
    text = strip_to_js(html_path)
    hits = _hits(text)

    found, missing = {}, {}
    earned, lost = [], []
    item_cards = {}
    for item in ITEMS:
        ok, evidence, why = hits[item["id"]]
        points = int(item["points"])
        row = {
            "id": item["id"],
            "label": item["label"],
            "kind": "must_present",
            "points": points,
            "evidence": evidence,
        }
        if ok:
            found[item["id"]] = evidence
            earned.append(row)
            item_cards[item["id"]] = {
                "score": points,
                "max_score": points,
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
                "max_score": points,
                "passed": False,
                "earned": [],
                "lost": [row],
            }

    score = sum(int(row["points"]) for row in earned)
    max_score = sum(int(item["points"]) for item in ITEMS)
    passed = not missing
    reason = (
        "Voxel island: cubes on a grid"
        if passed
        else f"Scored {score}/{max_score}; missing: {', '.join(missing)}"
    )
    scorecard = {
        "score": score,
        "max_score": max_score,
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
    _ROOT = Path(__file__).resolve().parents[2]
    if str(_ROOT) not in sys.path:
        sys.path.append(str(_ROOT))
    from harness.status import log

    log(f"WC000  checking  {html_path}")
    result = check_voxel_world(html_path, out_dir=out_dir)
    dest = out_dir if out_dir is not None else Path(html_path).parent
    print(f"passed={result.passed} score={result.details['score']}/{result.details['max_score']}", flush=True)
    print(result.reason, flush=True)
    if result.details.get("missing"):
        print(result.details["missing"], flush=True)
    print(f"{dest}/score.json", flush=True)
