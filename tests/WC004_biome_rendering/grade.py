from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from llm import BIOME_IDS, BiomeRenderReport, CheckResult, VALID_AXES, load_templates

POINTS_PER_BIOME = 10

_BARE_BIOME_TOKEN = re.compile(r"^(?:BIOMES\.)?\w+\.id,?$")
_WAYPOINT = re.compile(r"^\{\s*x\s*:\s*[-0-9.]+,\s*z\s*:\s*[-0-9.]+\s*\},?$")
_GEOM_ASSIGN = re.compile(
    r"\b(?:h|baseH|height|heightMap|top|side|wc|color|[rgb])\s*[+\-*/]?=",
    re.I,
)
_THREE = re.compile(
    r"new\s+(?:THREE\.)?\w*(?:Mesh|Geometry|Points|Group|InstancedMesh)"
    r"|BoxGeometry|PlaneGeometry|RingGeometry|CylinderGeometry|ConeGeometry|BufferGeometry"
    r"|PointsMaterial|MeshLambertMaterial|MeshBasicMaterial"
    r"|scene\.add|group\.add",
    re.I,
)
_MOTION_MUTATION = re.compile(
    r"position\.(?:x|y|z)\s*[+\-]?="
    r"|\.position\.(?:x|y|z)\s*="
    r"|\.position\.set\s*\("
    r"|attributes\.position"
    r"|velocit\w*\["
    r"|\.P\["
    r"|pos\[.*?\]\s*[+\-]="
    r"|positions\[.*?\]\s*[+\-]=",
    re.I,
)
_CALL = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
_DART_THROW = re.compile(r"Math\.random\s*\(\s*\)\s*\*\s*GRID")
_CELL_WALK = re.compile(r"for\s*\([^;]*\bz\b")
_TIME_UPDATE = re.compile(
    r"\b(?:dt|delta|clock\.getDelta|\btime\b|\bnow\b|performance\.now"
    r"|requestAnimationFrame|animate\b|updateSystem|updateWeather|forEach\s*\("
    r"|position\.(?:x|y|z)\s*[+\-]?="
    r"|\.position\.(?:x|y|z)\s*="
    r"|attributes\.position"
    r"|(?:pos|positions)\[.*?\]\s*[+\-]="
    r"|\.P\[|velocit|instanceMatrix\.needsUpdate|commit\s*\()",
    re.I,
)
_LEGEND = re.compile(
    r"\b(?:label|weather)\s*:"
    r"|^\s*\w+\s*:\s*\{\s*id\s*:",
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
}

_AXIS_ALIASES = {
    "fall": "falling",
    "down": "falling",
    "downward": "falling",
    "horizontal": "blowing",
    "wind": "blowing",
    "sideways": "blowing",
    "up": "rising",
    "upward": "rising",
    "static": "n/a",
    "none": "n/a",
    "na": "n/a",
    "flow": "flowing",
    "walk": "grounded",
    "idle": "grounded",
    "pulse": "pulsing",
    "glow": "pulsing",
    "hang": "still",
    "drift": "falling",
}


def grade_reports(
    reports: dict[str, BiomeRenderReport | dict],
    biome_ids: tuple[str, ...] | None = None,
) -> CheckResult:
    found, missing = {}, {}
    item_hits, item_misses = {}, {}
    biome_scores = {}
    biomes = {}
    total = 0.0
    selected = biome_ids or BIOME_IDS
    max_score = POINTS_PER_BIOME * len(selected)

    for biome_id in selected:
        templates = load_templates(biome_id)
        report = reports.get(biome_id)
        card = _grade_one(biome_id, templates, report)
        biome_scores[biome_id] = card["score"]
        total += card["score"]
        hits = [row["id"] for row in card["earned"]]
        misses = [row["id"] for row in card["lost"]]
        ok = not card["lost"]
        why = "ok" if ok else f"failed items: {', '.join(misses)}"
        (found if ok else missing)[biome_id] = why
        if hits:
            item_hits[biome_id] = hits
        if misses:
            item_misses[biome_id] = misses
        biomes[biome_id] = card

    score = round(total, 2)
    passed = not missing
    reason = (
        "All biomes have correct entity rendering"
        if passed
        else f"Scored {score}/{max_score}; incomplete biomes: {', '.join(missing)}"
    )
    scorecard = {
        "score": score,
        "max_score": max_score,
        "points_per_biome": POINTS_PER_BIOME,
        "passed": passed,
        "reason": reason,
        "biomes": biomes,
    }
    return CheckResult(
        passed,
        reason,
        {
            "found": found,
            "missing": missing,
            "item_hits": item_hits,
            "item_misses": item_misses,
            "biome_scores": biome_scores,
            "score": score,
            "max_score": max_score,
            "scorecard": scorecard,
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


def _is_config_table(code: str) -> bool:
    if _has_world_call(code):
        return False
    if re.search(r"\bbiome\s*:", code, re.I) and re.search(r"\b(?:count|color|spread|speed)\s*:", code, re.I):
        return True
    if not re.search(r"\bcount\s*:", code, re.I):
        return False
    return bool(re.search(r"\b(color|spread|h|biome|speed|kind|size|height)\s*:", code, re.I))


def _is_implementing(code: str) -> bool:
    return bool(
        _THREE.search(code)
        or _GEOM_ASSIGN.search(code)
        or _has_world_call(code)
        or _MOTION_MUTATION.search(code)
    )


def _reject_reason(evidence: str, *, allow_config: bool = False) -> str | None:
    """Reject keyword / hint evidence. Accept any style of world mutation."""
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
    if exp == "n/a":
        return rep in {"n/a", "still", ""}
    if exp == "still" and rep in {"n/a", "still", ""}:
        return True
    if exp == "falling" and rep == "flowing":
        return True
    if exp == "flowing" and rep in {"falling", "pulsing"}:
        return True
    if exp == "rising" and rep == "pulsing":
        return True
    return False


def _not_in_scope(text: str) -> bool:
    low = (text or "").strip().lower()
    return "not in " in low and "scope" in low


def _empty_motion(text: str) -> bool:
    return not (text or "").strip() or _not_in_scope(text)


def _grade_entity(
    entity: dict,
    judgement,
    used_hashes: set[str],
) -> tuple[bool, str, dict]:
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


def _grade_leak(judgement) -> tuple[bool, str]:
    if judgement is None:
        return False, "missing_judgement"
    if _not_in_scope(judgement.evidence or ""):
        return False, ""
    if not judgement.found:
        return False, ""
    reason = _reject_reason(judgement.evidence or "")
    if reason:
        return False, reason
    return True, "forbidden_present"


def _item_row(
    item: dict,
    kind: str,
    hit: bool,
    points: float,
    why: str,
    meta: dict,
) -> dict:
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


def _grade_one(biome_id: str, templates: dict, report) -> dict:
    if not isinstance(report, BiomeRenderReport):
        err = report.get("error", "no report") if isinstance(report, dict) else "no report"
        return {
            "score": 0.0,
            "max_score": POINTS_PER_BIOME,
            "passed": False,
            "earned": [],
            "lost": [
                {
                    "id": "probe_failed",
                    "label": "",
                    "kind": "probe",
                    "points": POINTS_PER_BIOME,
                    "why": "probe_failed",
                    "look_evidence": err,
                }
            ],
        }

    entities = list(templates.get("entities", []))
    leak_items = list(templates.get("must_not_present", []))
    n_entities = len(entities)
    points = round(POINTS_PER_BIOME / n_entities, 2) if n_entities else 0.0
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
        leak, why = _grade_leak(judgement)
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

    raw = POINTS_PER_BIOME * (entity_hits - leak_count) / n_entities if n_entities else 0.0
    biome_score = round(max(0.0, raw), 2)
    return {
        "score": biome_score,
        "max_score": POINTS_PER_BIOME,
        "passed": not lost,
        "earned": earned,
        "lost": lost,
    }
