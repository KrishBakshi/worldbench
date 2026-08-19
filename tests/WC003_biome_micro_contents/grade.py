from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from llm import BIOME_IDS, BiomeMicroReport, CheckResult, load_requirements

POINTS_PER_BIOME = 10
MAX_SCORE = POINTS_PER_BIOME * len(BIOME_IDS)

_BARE_BIOME_TOKEN = re.compile(r"^(?:BIOMES\.)?\w+\.id,?$")
_WAYPOINT = re.compile(r"^\{\s*x\s*:\s*[-0-9.]+,\s*z\s*:\s*[-0-9.]+\s*\},?$")
_GEOM_ASSIGN = re.compile(
    r"\b(?:h|baseH|height|heightMap|top|side|wc|color)\s*[+\-*/]?=(?!=)",
    re.I,
)
_THREE = re.compile(
    r"new\s+(?:THREE\.)?\w*(?:Mesh|Geometry|Points|Group|InstancedMesh)"
    r"|BoxGeometry|PlaneGeometry|RingGeometry|CylinderGeometry|ConeGeometry|BufferGeometry"
    r"|PointsMaterial|MeshLambertMaterial|MeshBasicMaterial"
    r"|scene\.add",
    re.I,
)
_PLACE_EXEC = re.compile(
    r"scene\.add|group\.add|setMatrixAt|InstancedMesh"
    r"|\b(?:addBlock|placeBlock|addO|addW|addL|fadd|queue|pb|terra\.add)\s*\("
    r"|(?:voxelData|blocks|waterBlocks|animals|fallSpots)\.push\s*\("
    r"|\.add\s*\(",
    re.I,
)
_DART_THROW = re.compile(r"Math\.random\s*\(\s*\)\s*\*\s*GRID")
_CELL_WALK = re.compile(r"for\s*\([^;]*\bz\b")
_CALL = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
_BUILTIN_CALLS = {
    "Math", "console", "document", "window", "JSON", "Object", "Array", "Number",
    "String", "parseInt", "parseFloat", "isNaN", "isFinite", "if", "for", "while",
    "switch", "function", "catch", "return", "typeof", "pow", "sin", "cos", "tan",
    "floor", "ceil", "round", "abs", "min", "max", "sqrt", "random", "atan2",
    "log", "exp", "hypot", "sign", "trunc",
}


def grade_reports(
    reports: dict[str, BiomeMicroReport | dict],
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
        req = load_requirements(biome_id)
        report = reports.get(biome_id)
        card = _grade_one(biome_id, req, report)
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
        "All biomes have correct micro-contents"
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


def _has_world_call(code: str) -> bool:
    for match in _CALL.finditer(code):
        if match.group(1) not in _BUILTIN_CALLS:
            return True
    return False


def _is_config_table(code: str) -> bool:
    if _has_world_call(code) or _PLACE_EXEC.search(code) or _THREE.search(code):
        return False
    if not re.search(r"\bcount\s*:", code, re.I):
        return False
    return bool(re.search(r"\b(color|spread|h|biome)\s*:", code, re.I))


def _is_implementing(code: str) -> bool:
    return bool(
        _THREE.search(code)
        or _GEOM_ASSIGN.search(code)
        or _PLACE_EXEC.search(code)
        or _has_world_call(code)
    )


def _reject_reason(evidence: str) -> str | None:
    """Reject keyword / hint evidence. Placement must mutate the world."""
    code = _code_only(evidence)
    if not code:
        return "comment_only"
    compact = re.sub(r"\s+", " ", code).strip()
    if _BARE_BIOME_TOKEN.match(compact):
        return "bare_token"
    if _WAYPOINT.match(compact):
        return "waypoint_only"
    low = compact.lower()
    if "label:" in low and ("weather:" in low or "color:" in low):
        return "legend_or_enum"
    if _DART_THROW.search(code) and not _CELL_WALK.search(code):
        return "dart_throw"
    if _is_config_table(code):
        return "config_table"
    if not _is_implementing(code):
        return "no_constructor"
    return None


def _not_in_scope(judgement) -> bool:
    if judgement is None:
        return False
    evidence = (judgement.evidence or "").strip().lower()
    return "not in " in evidence and "scope" in evidence


def _presence(judgement) -> tuple[bool, str]:
    if judgement is None:
        return False, "missing_judgement"
    if _not_in_scope(judgement):
        return False, "not_in_scope_evidence"
    if not judgement.found:
        return False, "not_found"
    reason = _reject_reason(judgement.evidence or "")
    if reason:
        return False, reason
    return True, ""


def _item_row(item: dict, kind: str, judgement, hit: bool, points: float, why: str) -> dict:
    row = {
        "id": item["id"],
        "label": item.get("label", ""),
        "kind": kind,
        "points": points,
        "llm_found": None if judgement is None else bool(judgement.found),
        "evidence": "" if judgement is None else (judgement.evidence or ""),
    }
    if not hit:
        row["why"] = why
    return row


def _grade_one(biome_id: str, req: dict, report) -> dict:
    if not isinstance(report, BiomeMicroReport):
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
                    "llm_found": None,
                    "evidence": err,
                }
            ],
        }

    present_items = list(req.get("must_present", []))
    leak_items = list(req.get("must_not_present", []))
    n_present = len(present_items)
    points = round(POINTS_PER_BIOME / n_present, 2) if n_present else 0.0
    earned, lost = [], []
    present_hits = 0
    leak_count = 0

    for item in present_items:
        judgement = report.must_present.get(item["id"])
        implemented, why = _presence(judgement)
        if implemented:
            present_hits += 1
            earned.append(_item_row(item, "must_present", judgement, True, points, why))
        else:
            lost.append(_item_row(item, "must_present", judgement, False, points, why))

    for item in leak_items:
        judgement = report.must_not_present.get(item["id"])
        implemented, why = _presence(judgement)
        if implemented:
            leak_count += 1
            lost.append(
                _item_row(item, "must_not_present", judgement, False, points, "forbidden_present")
            )

    raw = POINTS_PER_BIOME * (present_hits - leak_count) / n_present if n_present else 0.0
    biome_score = round(max(0.0, raw), 2)
    return {
        "score": biome_score,
        "max_score": POINTS_PER_BIOME,
        "passed": not lost,
        "earned": earned,
        "lost": lost,
    }
