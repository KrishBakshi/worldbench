from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from llm import CheckResult, CycleReport, VALID_AXES, load_templates

POINTS_TOTAL = 10

_BARE_BIOME_TOKEN = re.compile(r"^(?:BIOMES\.)?\w+\.id,?$")
_WAYPOINT = re.compile(r"^\{\s*x\s*:\s*[-0-9.]+,\s*z\s*:\s*[-0-9.]+\s*\},?$")
_GEOM_ASSIGN = re.compile(
    r"\b(?:h|baseH|height|heightMap|top|side|wc|color|[rgb]|intensity|fog)\s*[+\-*/]?=",
    re.I,
)
_THREE = re.compile(
    r"new\s+(?:THREE\.)?\w*(?:Mesh|Geometry|Points|Group|InstancedMesh|DirectionalLight|AmbientLight|HemisphereLight|PointLight)"
    r"|BoxGeometry|SphereGeometry|PlaneGeometry|RingGeometry|CylinderGeometry|ConeGeometry|BufferGeometry"
    r"|PointsMaterial|MeshLambertMaterial|MeshBasicMaterial"
    r"|scene\.add|group\.add|\.color\.set|\.intensity\s*=",
    re.I,
)
_MOTION_MUTATION = re.compile(
    r"position\.(?:x|y|z)\s*[+\-]?="
    r"|\.position\.(?:x|y|z)\s*="
    r"|\.position\.set\s*\("
    r"|\.position\.copy\s*\("
    r"|attributes\.position"
    r"|velocit\w*\["
    r"|\.P\["
    r"|pos\[.*?\]\s*[+\-]="
    r"|positions\[.*?\]\s*[+\-]="
    r"|\.intensity\s*[+\-]?="
    r"|\.color\.set",
    re.I,
)
_CALL = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
_DART_THROW = re.compile(r"Math\.random\s*\(\s*\)\s*\*\s*GRID")
_CELL_WALK = re.compile(r"for\s*\([^;]*\bz\b")
_TIME_UPDATE = re.compile(
    r"\b(?:dt|delta|clock\.getDelta|\btime\b|\bnow\b|performance\.now"
    r"|requestAnimationFrame|animate\b|updateSun|updateSeasons|updateWeather"
    r"|DAY_LEN|SEASON_LEN|seasonProgress|seasonTime"
    r"|position\.(?:x|y|z)\s*[+\-]?="
    r"|\.position\.(?:x|y|z)\s*="
    r"|\.position\.set\s*\("
    r"|\.position\.copy\s*\("
    r"|\.visible\s*="
    r"|multiplyScalar"
    r"|%\s*4|%\s*1"
    r"|attributes\.position"
    r"|(?:pos|positions)\[.*?\]\s*[+\-]="
    r"|\.P\[|velocit|instanceMatrix\.needsUpdate|commit\s*\("
    r"|\.intensity\s*=)",
    re.I,
)
_LEGEND = re.compile(
    r"\b(?:label|weather)\s*:"
    r"|^\s*\w+\s*:\s*\{\s*id\s*:",
    re.I,
)
_HUD = re.compile(r"\b(?:textContent|innerHTML|innerText)\s*=")
_CYCLE_DECL = re.compile(
    r"\b(?:SEASONS|seasonNames|seasonColors|seasonProgress|seasonTime|DAY_LEN|SEASON_LEN)\b"
    r"|DirectionalLight|AmbientLight|HemisphereLight"
    r"|Spring|Summer|Autumn|Winter",
    re.I,
)
_WORLD_TINT = re.compile(
    r"intensity|\.color\.set|fog|tint|rainMul|snowMul|sandMul|background",
    re.I,
)
_MOON = re.compile(r"\bmoon\b|moonMesh|moonGeo|moonMat|createMoon|addMoon", re.I)
_STAR_OR_DOME = re.compile(
    r"starfield|stardust|twinkl|\bstars\b|starMesh|starPoints|starGeo|starMat"
    r"|createStars|addStars|nStars|numStars"
    r"|skydome|sky.?dome|skybox|skySphere|skyMesh"
    r"|atmosphere.?dome|\batmosphere\b|\bdome\b|new\s+(?:THREE\.)?Sky\b",
    re.I,
)
_WEATHER_POINTS = re.compile(
    r"\b(?:rain|snow|ash|sand|dust|blizzard|ember|spark|pollen)\b",
    re.I,
)
_BUILTIN_CALLS = {
    "Math",
    "console",
    "document",
    "window",
    "JSON",
    "Object",
    "Array",
    "Number",
    "String",
    "parseInt",
    "parseFloat",
    "isNaN",
    "isFinite",
    "if",
    "for",
    "while",
    "switch",
    "function",
    "catch",
    "return",
    "typeof",
    "pow",
    "sin",
    "cos",
    "tan",
    "floor",
    "ceil",
    "round",
    "abs",
    "min",
    "max",
    "sqrt",
    "random",
    "atan2",
    "log",
    "exp",
    "hypot",
    "sign",
    "trunc",
    "clamp",
    "lerp",
}

_AXIS_ALIASES = {
    "orbit": "cyclic",
    "orbiting": "cyclic",
    "loop": "cyclic",
    "day": "cyclic",
    "season": "cyclic",
    "wrap": "cyclic",
    "pulse": "pulsing",
    "glow": "pulsing",
    "static": "n/a",
    "none": "n/a",
    "na": "n/a",
}


def grade_report(report: CycleReport | dict) -> CheckResult:
    templates = load_templates()
    card = _grade_one(templates, report)
    score = card["score"]
    max_score = card["max_score"]
    passed = card["passed"]
    reason = (
        "Day/night and seasons cycle correctly"
        if passed
        else f"Scored {score}/{max_score}; failed items: {', '.join(r['id'] for r in card['lost'])}"
    )
    scorecard = {
        "score": score,
        "max_score": max_score,
        "points_total": POINTS_TOTAL,
        "passed": passed,
        "reason": reason,
        "earned": card["earned"],
        "lost": card["lost"],
    }
    return CheckResult(
        passed,
        reason,
        {
            "score": score,
            "max_score": max_score,
            "scorecard": scorecard,
            "item_hits": [r["id"] for r in card["earned"]],
            "item_misses": [r["id"] for r in card["lost"]],
        },
    )


def _code_only(evidence: str) -> str:
    lines = []
    for raw in evidence.splitlines():
        line = raw.strip()
        if not line or line.startswith("//") or line.startswith("/*") or line.startswith("*"):
            continue
        if "//" in line:
            line = line[: line.index("//")].rstrip()
            if not line:
                continue
        lines.append(line)
    return "\n".join(lines)


def _evidence_hash(code: str) -> str:
    normalized = re.sub(r"\s+", " ", _code_only(code)).strip()
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _has_world_call(code: str) -> bool:
    for match in _CALL.finditer(code):
        if match.group(1) not in _BUILTIN_CALLS:
            return True
    return False


def _is_hud_only(code: str) -> bool:
    if not _HUD.search(code):
        return False
    return not _WORLD_TINT.search(code) and not _MOTION_MUTATION.search(code)


def _is_config_table(code: str) -> bool:
    if _has_world_call(code):
        return False
    if not re.search(r"\bcount\s*:", code, re.I):
        return False
    return bool(re.search(r"\b(color|spread|h|biome|speed|kind)\s*:", code, re.I))


def _is_implementing(code: str) -> bool:
    return bool(
        _THREE.search(code)
        or _GEOM_ASSIGN.search(code)
        or _has_world_call(code)
        or _MOTION_MUTATION.search(code)
        or _CYCLE_DECL.search(code)
    )


def _reject_reason(evidence: str, *, allow_config: bool = False) -> str | None:
    code = _code_only(evidence)
    if not code:
        return "comment_only"
    compact = re.sub(r"\s+", " ", code).strip()
    if _BARE_BIOME_TOKEN.match(compact):
        return "bare_token"
    if _WAYPOINT.match(compact):
        return "waypoint_only"
    if _LEGEND.search(compact):
        return "legend_or_enum"
    if _is_hud_only(code):
        return "hud_only"
    if _DART_THROW.search(code) and not _CELL_WALK.search(code):
        return "dart_throw"
    if _is_config_table(code):
        if allow_config:
            return None
        return "config_table"
    if not _is_implementing(code):
        return "no_constructor"
    return None


def _normalize_axis(axis: str) -> str:
    key = (axis or "n/a").strip().lower().replace("-", "_").replace(" ", "_")
    if key in VALID_AXES:
        return key
    return _AXIS_ALIASES.get(key, key)


def _axes_compatible(expected: str, reported: str) -> bool:
    exp = _normalize_axis(expected)
    rep = _normalize_axis(reported)
    if exp == rep:
        return True
    if exp == "cyclic" and rep in {"cyclic", "pulsing"}:
        return True
    if exp == "n/a":
        return rep in {"n/a", "still", ""}
    if exp == "still" and rep in {"n/a", "still"}:
        return True
    return False


def _not_in_scope(text: str) -> bool:
    low = (text or "").strip().lower()
    return "not in " in low and "scope" in low


def _empty_motion(text: str) -> bool:
    return not (text or "").strip() or _not_in_scope(text)


def _grade_entity(entity: dict, judgement, used_hashes: set[str]) -> tuple[bool, str, dict]:
    meta = {
        "llm_looks_ok": None if judgement is None else judgement.looks_ok,
        "llm_moves_ok": None if judgement is None else judgement.moves_ok,
        "llm_axis": None if judgement is None else judgement.axis,
        "look_evidence": "" if judgement is None else (judgement.look_evidence or ""),
        "motion_evidence": "" if judgement is None else (judgement.motion_evidence or ""),
    }
    if judgement is None:
        return False, "missing_judgement", meta

    look = (judgement.look_evidence or "").strip()
    motion = (judgement.motion_evidence or "").strip()
    requires_motion = bool(entity.get("requires_motion"))
    expected_axis = entity.get("expected_axis", "n/a")

    if _not_in_scope(look):
        return False, "not_in_scope_evidence", meta
    if not judgement.looks_ok:
        return False, "look_mismatch", meta

    look_reason = _reject_reason(look, allow_config=requires_motion)
    if look_reason:
        return False, look_reason, meta

    if entity.get("id") == "moon":
        look_code = _code_only(look)
        if _STAR_OR_DOME.search(look_code) and not _MOON.search(look_code):
            return False, "stars_are_not_moon", meta
        if not _MOON.search(look_code):
            return False, "not_a_moon_mesh", meta

    if requires_motion:
        if not judgement.moves_ok:
            return False, "no_motion", meta
        if _empty_motion(motion):
            return False, "no_motion", meta
        if motion == look:
            return False, "spawn_only_no_update", meta
        motion_reason = _reject_reason(motion, allow_config=False)
        if motion_reason:
            return False, motion_reason, meta
        if not _TIME_UPDATE.search(_code_only(motion)):
            return False, "no_time_update", meta
        if not _axes_compatible(expected_axis, judgement.axis):
            return False, "wrong_axis", meta
    elif judgement.axis and not _axes_compatible(expected_axis, judgement.axis):
        return False, "wrong_axis", meta

    look_hash = _evidence_hash(look)
    if look_hash in used_hashes:
        return False, "duplicate_evidence", meta
    used_hashes.add(look_hash)
    if requires_motion and motion:
        motion_hash = _evidence_hash(motion)
        if motion_hash in used_hashes:
            return False, "duplicate_evidence", meta
        used_hashes.add(motion_hash)

    return True, "", meta


def _is_star_or_dome_evidence(evidence: str) -> bool:
    code = _code_only(evidence)
    if not code:
        return False
    if _STAR_OR_DOME.search(code):
        return True
    if _WEATHER_POINTS.search(code):
        return False
    return False


def _grade_leak(item: dict, judgement) -> tuple[bool, str]:
    if judgement is None:
        return False, "missing_judgement"
    if _not_in_scope(judgement.evidence or ""):
        return False, ""
    if not judgement.found:
        return False, ""
    reason = _reject_reason(judgement.evidence or "")
    if reason:
        return False, reason
    if item.get("id") == "stars_or_atmosphere_dome" and not _is_star_or_dome_evidence(
        judgement.evidence or ""
    ):
        return False, "not_star_or_dome"
    return True, "forbidden_present"


def _item_row(item: dict, kind: str, hit: bool, points: float, why: str, meta: dict) -> dict:
    row = {
        "id": item["id"],
        "label": item.get("label", ""),
        "kind": kind,
        "points": points,
        **meta,
    }
    if not hit:
        row["why"] = why
    return row


def _grade_one(templates: dict, report) -> dict:
    if not isinstance(report, CycleReport):
        err = report.get("error", "no report") if isinstance(report, dict) else "no report"
        return {
            "score": 0.0,
            "max_score": POINTS_TOTAL,
            "passed": False,
            "earned": [],
            "lost": [
                {
                    "id": "probe_failed",
                    "label": "",
                    "kind": "probe",
                    "points": POINTS_TOTAL,
                    "why": "probe_failed",
                    "look_evidence": err,
                }
            ],
        }

    entities = list(templates.get("entities", []))
    leak_items = list(templates.get("must_not_present", []))
    n_entities = len(entities)
    points = round(POINTS_TOTAL / n_entities, 2) if n_entities else 0.0
    earned, lost = [], []
    entity_hits = 0
    leak_count = 0
    used_hashes: set[str] = set()

    for entity in entities:
        judgement = report.entities.get(entity["id"])
        hit, why, meta = _grade_entity(entity, judgement, used_hashes)
        if hit:
            entity_hits += 1
            earned.append(_item_row(entity, "entity", True, points, why, meta))
        else:
            lost.append(_item_row(entity, "entity", False, points, why, meta))

    for item in leak_items:
        judgement = report.must_not_present.get(item["id"])
        leak, why = _grade_leak(item, judgement)
        if leak:
            leak_count += 1
            lost.append(
                {
                    "id": item["id"],
                    "label": item.get("label", ""),
                    "kind": "must_not_present",
                    "points": points,
                    "why": why,
                    "look_evidence": "" if judgement is None else (judgement.evidence or ""),
                }
            )

    raw = POINTS_TOTAL * (entity_hits - leak_count) / n_entities if n_entities else 0.0
    score = round(max(0.0, raw), 2)
    return {
        "score": score,
        "max_score": POINTS_TOTAL,
        "passed": not lost,
        "earned": earned,
        "lost": lost,
    }
