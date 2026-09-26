from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from llm import BIOME_IDS, BiomeMicroReport, CheckResult, load_requirements

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))
from eval.capture.judge import VisualReport  # noqa: E402
from eval.evidence import in_source  # noqa: E402

POINTS_PER_BIOME = 10
MAX_SCORE = POINTS_PER_BIOME * len(BIOME_IDS)

# Each item's points split between what the code builds (quote checked
# against the source) and what the daytime frames show. Either half alone
# is partial credit: code that never renders, or a render the probe missed.
CODE_SHARE = 0.5
VISUAL_SHARE = 0.5

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
    visual: dict[str, VisualReport | dict] | None = None,
    source_normalized: str | None = None,
) -> CheckResult:
    """visual: per-biome VisualReport (None = code-only regrade of an old run).
    source_normalized: eval.evidence.normalize(js); None skips the quote check."""
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
        card = _grade_one(biome_id, req, report, (visual or {}).get(biome_id), source_normalized, visual is not None)
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


def _presence(judgement, source_normalized: str | None = None) -> tuple[bool, str]:
    if judgement is None:
        return False, "missing_judgement"
    if _not_in_scope(judgement):
        return False, "not_in_scope_evidence"
    if not judgement.found:
        return False, "not_found"
    reason = _reject_reason(judgement.evidence or "")
    if reason:
        return False, reason
    if source_normalized is not None and not in_source(judgement.evidence or "", source_normalized):
        return False, "evidence_not_in_source"
    return True, ""


def _weight(item: dict) -> float:
    return float(item.get("weight", 1))


def _failed(biome_id: str, why: str, detail: str = "") -> dict:
    return {
        "score": 0.0,
        "max_score": POINTS_PER_BIOME,
        "passed": False,
        "earned": [],
        "lost": [{"id": why, "label": "", "kind": "biome", "points": POINTS_PER_BIOME, "why": why, "evidence": detail}],
    }


def _grade_one(
    biome_id: str,
    req: dict,
    report,
    visual,
    source_normalized: str | None,
    use_visual: bool,
) -> dict:
    if not isinstance(report, BiomeMicroReport):
        err = report.get("error", "no report") if isinstance(report, dict) else "no report"
        return _failed(biome_id, "probe_failed", err)
    if use_visual and not isinstance(visual, VisualReport):
        err = visual.get("error", "no visual report") if isinstance(visual, dict) else "no visual report"
        return _failed(biome_id, "visual_failed", err)

    present_items = list(req.get("must_present", []))
    leak_items = list(req.get("must_not_present", []))
    total_weight = sum(_weight(i) for i in present_items) or 1.0
    unit = POINTS_PER_BIOME / total_weight
    seen = {s.id: s for s in visual.items} if use_visual else {}
    seen_leaks = {s.id: s for s in visual.leaks} if use_visual else {}
    code_share, visual_share = (CODE_SHARE, VISUAL_SHARE) if use_visual else (1.0, 0.0)

    earned, lost = [], []
    code_hits = 0
    score = 0.0
    for item in present_items:
        judgement = report.must_present.get(item["id"])
        code_ok, why = _presence(judgement, source_normalized)
        sighting = seen.get(item["id"])
        visual_ok = bool(sighting and sighting.visible)
        code_hits += code_ok
        points = round(unit * _weight(item), 2)
        got = round(points * (code_share * code_ok + visual_share * visual_ok), 2)
        score += got
        row = {
            "id": item["id"],
            "label": item.get("label", ""),
            "kind": "must_present",
            "points": points,
            "earned": got,
            "code": code_ok,
            "visual": visual_ok if use_visual else None,
            "seen": sighting.seen if sighting else "",
            "evidence": "" if judgement is None else (judgement.evidence or ""),
        }
        if got >= points:
            earned.append(row)
        else:
            # Partial credit rows stay in `lost` (with their `earned`) so the
            # scorecard shows which half was missing.
            row["why"] = why if not code_ok else "not_visible"
            lost.append(row)

    for item in leak_items:
        judgement = report.must_not_present.get(item["id"])
        code_leak, _ = _presence(judgement, source_normalized)
        sighting = seen_leaks.get(item["id"])
        visual_leak = bool(sighting and sighting.visible)
        if code_leak or visual_leak:
            points = round(unit * _weight(item), 2)
            score -= points
            lost.append({
                "id": item["id"],
                "label": item.get("label", ""),
                "kind": "must_not_present",
                "points": points,
                "why": "forbidden_present",
                "code": code_leak,
                "visual": visual_leak if use_visual else None,
                "seen": sighting.seen if sighting else "",
                "evidence": "" if judgement is None else (judgement.evidence or ""),
            })

    # Absent biome: nothing built for it in code and nothing seen in the frames.
    biome_seen = bool(use_visual and (visual.shows_biome or visual.biome_visible))
    if code_hits == 0 and not report.aliases and not biome_seen:
        return _failed(biome_id, "biome_absent", "no code evidence and not visible in any frame")

    card = {
        "score": round(max(0.0, score), 2),
        "max_score": POINTS_PER_BIOME,
        "passed": not lost,
        "earned": earned,
        "lost": lost,
    }
    if use_visual:
        card["shows_biome"] = visual.shows_biome
        card["biome_visible"] = visual.biome_visible
    # The ocean has to sit on a seabed. A sheet running out over the void
    # zeroes the delta biome (what the old island gate did from regex).
    if use_visual and biome_id == "delta" and visual.extra.get("ocean_over_void"):
        card.update(score=0.0, passed=False, ocean_over_void=True)
        card["lost"].append({"id": "ocean_over_void", "kind": "physics", "why": "ocean_over_void",
                             "points": POINTS_PER_BIOME, "evidence": "ocean sheet extends over the void with no blocks beneath"})
    return card
