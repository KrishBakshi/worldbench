from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from llm import BIOME_IDS, BiomeRenderReport, CheckResult, VALID_AXES, load_templates

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))
from eval.capture.judge import VisualReport  # noqa: E402
from eval.evidence import in_source  # noqa: E402

POINTS_PER_BIOME = 10

# Credit per entity:
#   still entity:  look = half code look (verified quote), half visual look
#   moving entity: half look (as above) + half motion, where motion is half
#                  code (time update on the right axis) and half the capture's
#                  motion bursts (VLM on near/far frames + changed-pixel overlay)
# Without a visual / motion report (regrading an old run), code carries it.
LOOK_CODE, LOOK_VISUAL = 0.5, 0.5
MOTION_SHARE = 0.5
MOTION_CODE, MOTION_VISUAL = 0.5, 0.5
# A VLM "it moves" only counts if at least this share of a burst's pixels
# changed; a model can read motion into three identical frames.
MIN_MOTION_FRACTION = 0.001
# Expected axes where "present and on the right axis" is enough; nothing has
# to visibly travel (hanging mist, idle fauna).
_NO_TRAVEL_AXES = {"still", "n/a", "grounded"}
# Only these kinds get a frames verdict on motion (see visual.py); others,
# mainly fauna, are scored on code motion alone.
VISUAL_MOTION_KINDS = frozenset({"weather", "water", "terrain"})

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
    visual: dict[str, VisualReport | dict] | None = None,
    source_normalized: str | None = None,
    motion: dict | None = None,
) -> CheckResult:
    """visual: per-biome VisualReport (None = code-only regrade of an old run).
    motion: per-biome visual.MotionReport (or an unavailable/error dict); None = code-only motion.
    source_normalized: eval.evidence.normalize(js); None skips the quote check."""
    found, missing = {}, {}
    item_hits, item_misses = {}, {}
    biome_scores = {}
    biomes = {}
    total = 0.0
    selected = biome_ids or BIOME_IDS
    max_score = POINTS_PER_BIOME * len(selected)

    for biome_id in selected:
        templates = load_templates(biome_id)
        card = _grade_one(
            biome_id, templates, reports.get(biome_id), (visual or {}).get(biome_id),
            source_normalized, visual is not None,
            (motion or {}).get(biome_id), motion is not None,
        )
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
        "All biomes have correct entity look and motion"
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
    if _has_world_call(code) or _PLACE_EXEC.search(code) or _THREE.search(code) or _MOTION_MUTATION.search(code):
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
        or _PLACE_EXEC.search(code)
        or _has_world_call(code)
        or _MOTION_MUTATION.search(code)
    )


def _reject_reason(evidence: str, *, allow_config: bool = False) -> str | None:
    """Reject evidence that is a hint, not code: comments, bare tokens, lone
    waypoints, legend or HUD rows."""
    # Only hints are rejected here (comments, bare tokens, lone waypoints,
    # legend/HUD rows). Checks on *how* code is written (config_table,
    # no_constructor, dart_throw) were removed: they were keyed to helper
    # names like addBlock/pb/terra.add and rejected data-driven worlds
    # wholesale (opus-5: 45 of its WC004 losses were no_constructor on
    # entries like `{t:'deer',n:9,...}` consumed by a generic builder).
    # Whether something is really built is what the frames judge; the quote
    # must still be in the source (eval/evidence.py).
    code = _code_only(evidence)
    if not code:
        return "comment_only"
    compact = re.sub(r"\s+", " ", code).strip()
    if _BARE_BIOME_TOKEN.match(compact):
        return "bare_token"
    if _WAYPOINT.match(compact):
        return "waypoint_only"
    low = compact.lower()
    if "label:" in low and ("weather:" in low or "color:" in low) and not _has_world_call(code):
        return "legend_or_enum"
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
    source_normalized: str | None = None,
) -> dict:
    """Code verdict for one entity: {look_ok, look_why, motion_ok, motion_why, meta}.

    motion_ok is None for an entity that does not need to move.
    """
    meta = {
        "llm_looks_ok": None if judgement is None else judgement.looks_ok,
        "llm_moves_ok": None if judgement is None else judgement.moves_ok,
        "llm_axis": None if judgement is None else judgement.axis,
        "look_evidence": "" if judgement is None else (judgement.look_evidence or ""),
        "motion_evidence": "" if judgement is None else (judgement.motion_evidence or ""),
    }
    requires_motion = bool(entity.get("requires_motion"))
    verdict = {"look_ok": False, "look_why": "", "motion_ok": False if requires_motion else None, "motion_why": "", "meta": meta}
    if judgement is None:
        verdict.update(look_why="missing_judgement", motion_why="missing_judgement")
        return verdict

    look = (judgement.look_evidence or "").strip()
    motion = (judgement.motion_evidence or "").strip()
    expected_axis = entity.get("expected_axis", "n/a")

    def look_reason() -> str:
        if _not_in_scope(look):
            return "not_in_scope_evidence"
        if not judgement.looks_ok:
            return "look_mismatch"
        reason = _reject_reason(look, allow_config=requires_motion)
        if reason:
            return reason
        if source_normalized is not None and not in_source(look, source_normalized):
            return "evidence_not_in_source"
        if not requires_motion and judgement.axis and not _axes_compatible(expected_axis, judgement.axis):
            return "wrong_axis"
        if _evidence_hash(look) in used_hashes:
            return "duplicate_evidence"
        return ""

    def motion_reason() -> str:
        if not judgement.moves_ok or _empty_motion(motion):
            return "no_motion"
        if motion == look:
            return "spawn_only_no_update"
        reason = _reject_reason(motion, allow_config=False)
        if reason:
            return reason
        if source_normalized is not None and not in_source(motion, source_normalized):
            return "evidence_not_in_source"
        if not _TIME_UPDATE.search(_code_only(motion)):
            return "no_time_update"
        if not _axes_compatible(expected_axis, judgement.axis):
            return "wrong_axis"
        if _evidence_hash(motion) in used_hashes:
            return "duplicate_evidence"
        return ""

    why = look_reason()
    verdict.update(look_ok=not why, look_why=why)
    if not why:
        used_hashes.add(_evidence_hash(look))
    if requires_motion:
        why = motion_reason()
        verdict.update(motion_ok=not why, motion_why=why)
        if not why:
            used_hashes.add(_evidence_hash(motion))
    return verdict


def _grade_leak(judgement, source_normalized: str | None = None) -> tuple[bool, str]:
    if judgement is None:
        return False, "missing_judgement"
    if _not_in_scope(judgement.evidence or ""):
        return False, ""
    if not judgement.found:
        return False, ""
    reason = _reject_reason(judgement.evidence or "")
    if reason:
        return False, reason
    if source_normalized is not None and not in_source(judgement.evidence or "", source_normalized):
        return False, "evidence_not_in_source"
    return True, "forbidden_present"


def _failed(why: str, detail: str) -> dict:
    return {
        "score": 0.0,
        "max_score": POINTS_PER_BIOME,
        "passed": False,
        "earned": [],
        "lost": [{"id": why, "label": "", "kind": "biome", "points": POINTS_PER_BIOME, "why": why, "look_evidence": detail}],
    }


def _visual_motion_ok(entity: dict, sighting, fractions: dict) -> bool:
    if sighting is None or "not visible" in (sighting.seen or "").lower():
        return False
    expected = _normalize_axis(entity.get("expected_axis", "n/a"))
    if not _axes_compatible(expected, sighting.axis):
        return False
    if expected in _NO_TRAVEL_AXES:
        return True
    return bool(sighting.moving) and max(fractions.values(), default=0.0) >= MIN_MOTION_FRACTION


def _grade_one(
    biome_id: str,
    templates: dict,
    report,
    visual=None,
    source_normalized: str | None = None,
    use_visual: bool = False,
    motion=None,
    use_motion: bool = False,
) -> dict:
    if not isinstance(report, BiomeRenderReport):
        err = report.get("error", "no report") if isinstance(report, dict) else "no report"
        return _failed("probe_failed", err)
    if use_visual and not isinstance(visual, VisualReport):
        err = visual.get("error", "no visual report") if isinstance(visual, dict) else "no visual report"
        return _failed("visual_failed", err)

    entities = list(templates.get("entities", []))
    leak_items = list(templates.get("must_not_present", []))
    total_weight = sum(float(e.get("weight", 1)) for e in entities) or 1.0
    unit = POINTS_PER_BIOME / total_weight
    seen = {x.id: x for x in visual.items} if use_visual else {}
    seen_leaks = {x.id: x for x in visual.leaks} if use_visual else {}
    look_code, look_visual = (LOOK_CODE, LOOK_VISUAL) if use_visual else (1.0, 0.0)
    motion_code, motion_visual = (MOTION_CODE, MOTION_VISUAL) if use_motion else (1.0, 0.0)
    # An unavailable/errored motion report leaves every sighting missing, so the
    # visual half of motion is lost, like the look half for an unframed biome.
    # That report is a plain {"error": ...} dict, and a dict *has* `.items` (the
    # method): checking hasattr alone iterated the method and crashed all of
    # WC004 on the first world with an unframed biome.
    moved = (
        {x.id: x for x in motion.items}
        if use_motion and not isinstance(motion, dict) and hasattr(motion, "items")
        else {}
    )
    fractions = dict(getattr(motion, "motion_fraction", {}) or {}) if use_motion else {}

    earned, lost = [], []
    used_hashes: set[str] = set()
    score = 0.0
    any_code = False
    for entity in entities:
        v = _grade_entity(entity, report.entities.get(entity["id"]), used_hashes, source_normalized)
        sighting = seen.get(entity["id"])
        visual_ok = bool(sighting and sighting.visible)
        look_credit = look_code * v["look_ok"] + look_visual * visual_ok
        motion_seen = None
        if v["motion_ok"] is None:
            credit = look_credit
        else:
            if use_motion and entity.get("kind") in VISUAL_MOTION_KINDS:
                motion_seen = _visual_motion_ok(entity, moved.get(entity["id"]), fractions)
                motion_credit = motion_code * v["motion_ok"] + motion_visual * motion_seen
            else:
                motion_seen = None
                motion_credit = float(v["motion_ok"])
            credit = (1 - MOTION_SHARE) * look_credit + MOTION_SHARE * motion_credit
        any_code = any_code or v["look_ok"]
        points = round(unit * float(entity.get("weight", 1)), 2)
        got = round(points * credit, 2)
        score += got
        row = {
            "id": entity["id"],
            "label": entity.get("label", ""),
            "kind": "entity",
            "points": points,
            "earned": got,
            "code_look": v["look_ok"],
            "visual_look": visual_ok if use_visual else None,
            "code_motion": v["motion_ok"],
            "visual_motion": motion_seen,
            "motion_seen": moved[entity["id"]].seen if entity["id"] in moved else "",
            "motion_axis_seen": moved[entity["id"]].axis if entity["id"] in moved else "",
            "seen": sighting.seen if sighting else "",
            **v["meta"],
        }
        if got >= points:
            earned.append(row)
        else:
            row["why"] = (
                v["look_why"] or v["motion_why"]
                or ("not_visible" if use_visual and not visual_ok else "")
                or ("motion_not_seen" if motion_seen is False else "")
            )
            lost.append(row)

    for item in leak_items:
        judgement = report.must_not_present.get(item["id"])
        code_leak, why = _grade_leak(judgement, source_normalized)
        sighting = seen_leaks.get(item["id"])
        visual_leak = bool(sighting and sighting.visible)
        if code_leak or visual_leak:
            points = round(unit * float(item.get("weight", 1)), 2)
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
                "look_evidence": "" if judgement is None else (judgement.evidence or ""),
            })

    biome_seen = bool(use_visual and (visual.shows_biome or visual.biome_visible))
    if not any_code and not report.aliases and not biome_seen:
        return _failed("biome_absent", "no code evidence and not visible in any frame")

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
    return card
