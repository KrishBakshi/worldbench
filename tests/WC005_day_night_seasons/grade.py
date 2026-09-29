from __future__ import annotations

import functools
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))
from eval.evidence import in_source  # noqa: E402
from llm import CheckResult, CycleReport, VALID_AXES, load_templates

POINTS_TOTAL = 20
# Each item: half from code (verified quote, time update), half from what the
# pinned-time frames show (visual.py). Items with no visual verdict (motion
# that stills can't show) and runs with no usable frames score on code alone.
CODE_SHARE = 0.5
VISUAL_SHARE = 0.5

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
# A quote that builds the object rather than changing it.
_CONSTRUCTS = re.compile(r"\bnew\s+(?:THREE\.)?[A-Z]\w*\s*\(")

# Frame-loop reachability, on whitespace-free source (eval.evidence.normalize).
_LOOP_ROOT = re.compile(r"(?:requestAnimationFrame|setAnimationLoop)\((\w+)\)")
_LOOP_OPEN = re.compile(r"(?:requestAnimationFrame|setAnimationLoop)\((?:function\w*)?\([^()]*\)(?:=>)?$")
_FUNC_HEAD = re.compile(
    r"(?:function(\w+)\([^()]*\)"            # function name(...)
    r"|(\w+)=(?:async)?function\w*\([^()]*\)"  # name=function(...)
    r"|(\w+)=(?:async)?\(?[\w,]*\)?=>"          # name=(...)=>  /  name=x=>
    r"|(?<![.\w])(\w+)\([^()]*\))$"           # method name(...)
)
_NOT_FUNCS = {"if", "for", "while", "switch", "catch", "with", "function", "return"}
# Without whitespace, a keyword glues onto the word before it (`else if(` ->
# `elseif(`, `// animals` + `for(` -> `animalsfor(`): those are blocks, not functions.
_GLUED_KEYWORD = re.compile(r"(?:if|for|while|switch|catch|else)$")
_CALLED = re.compile(r"(\w+)\(")
LOOP_DEPTH = 4


def _open_brace_before(src: str, pos: int) -> int:
    """Index of the `{` that encloses src[pos], or -1."""
    depth = 0
    for i in range(pos - 1, -1, -1):
        c = src[i]
        if c == "}":
            depth += 1
        elif c == "{":
            if depth == 0:
                return i
            depth -= 1
    return -1


def _body(src: str, open_at: int) -> str:
    depth = 0
    for i in range(open_at, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[open_at + 1 : i]
    return src[open_at + 1 :]


@functools.lru_cache(maxsize=8)
def _per_frame_functions(src: str) -> frozenset[str]:
    """Names of the frame-loop callbacks and everything they call, LOOP_DEPTH deep."""
    heads = {}
    for m in re.finditer(r"\{", src):
        head = _FUNC_HEAD.search(src[max(0, m.start() - 160) : m.start()])
        name = head and next((g for g in head.groups() if g), None)
        if name and name not in _NOT_FUNCS and not _GLUED_KEYWORD.search(name) and name not in heads:
            heads[name] = m.start()
    frontier = set(_LOOP_ROOT.findall(src)) & set(heads)
    seen = set(frontier)
    for _ in range(LOOP_DEPTH):
        called = set()
        for name in frontier:
            called |= {c for c in _CALLED.findall(_body(src, heads[name])) if c in heads and c not in seen}
        seen |= called
        frontier = called
    return frozenset(seen)


def _runs_every_frame(quote: str, src: str) -> bool:
    """True only if the quote's line sits inside the frame loop: the function
    registered with requestAnimationFrame / setAnimationLoop, an anonymous
    callback passed to it, or a function those call (LOOP_DEPTH deep).
    Anything it can't establish is False, so the fallback is the strict rule."""
    code = re.sub(r"\s+", "", _code_only(quote))
    at = src.find(code) if code else -1
    if at < 0:
        return False
    per_frame = _per_frame_functions(src)
    pos = at
    while (open_at := _open_brace_before(src, pos)) >= 0:
        before = src[max(0, open_at - 160) : open_at]
        if _LOOP_OPEN.search(before):
            return True
        head = _FUNC_HEAD.search(before)
        name = head and next((g for g in head.groups() if g), None)
        if name and name not in _NOT_FUNCS and not _GLUED_KEYWORD.search(name) and name in per_frame:
            return True
        pos = open_at
    return False

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


def grade_report(
    report: CycleReport | dict,
    visual: dict | None = None,
    source_normalized: str | None = None,
) -> CheckResult:
    """visual: visual.judge_cycle() output (None = code-only regrade of an old run)."""
    templates = load_templates()
    card = _grade_one(templates, report, visual, source_normalized)
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
        "visual": card.get("visual"),
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
    if _is_hud_only(code):
        return "hud_only"
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


def _grade_entity(entity: dict, judgement, used_hashes: set[str], source_normalized: str | None = None) -> tuple[bool, str, dict]:
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
    if source_normalized is not None and not in_source(look, source_normalized):
        return False, "evidence_not_in_source", meta
    if requires_motion and source_normalized is not None and motion and not _empty_motion(motion) \
            and not in_source(motion, source_normalized):
        return False, "evidence_not_in_source", meta

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
        # One line may both show the entity and move it: an assignment inside
        # the frame loop (`light.intensity=0.1+0.5*dayFactor`) is the update.
        # It counts only when the line provably runs every frame and doesn't
        # construct the object; otherwise the old strict rule stands.
        if motion == look and (
            _CONSTRUCTS.search(_code_only(motion))
            or source_normalized is None
            or not _runs_every_frame(motion, source_normalized)
        ):
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
    if requires_motion and motion and motion != look:
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


def _grade_leak(item: dict, judgement, source_normalized: str | None = None) -> tuple[bool, str]:
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


def _grade_one(templates: dict, report, visual: dict | None = None, source_normalized: str | None = None) -> dict:
    if not isinstance(report, CycleReport):
        err = report.get("error", "no report") if isinstance(report, dict) else "no report"
        return {
            "score": 0.0,
            "max_score": POINTS_TOTAL,
            "passed": False,
            "earned": [],
            "lost": [{"id": "probe_failed", "label": "", "kind": "probe", "points": POINTS_TOTAL,
                      "why": "probe_failed", "look_evidence": err}],
        }

    entities = list(templates.get("entities", []))
    leak_items = list(templates.get("must_not_present", []))
    total_weight = sum(float(e.get("weight", 1)) for e in entities) or 1.0
    unit = POINTS_TOTAL / total_weight
    use_visual = bool(visual and visual.get("available"))
    seen_items = visual.get("items", {}) if use_visual else {}
    earned, lost = [], []
    used_hashes: set[str] = set()
    score = 0.0

    for entity in entities:
        judgement = report.entities.get(entity["id"])
        code_ok, why, meta = _grade_entity(entity, judgement, used_hashes, source_normalized)
        visual_ok = seen_items.get(entity["id"]) if use_visual else None
        points = round(unit * float(entity.get("weight", 1)), 2)
        if visual_ok is None:
            credit = float(code_ok)
        else:
            credit = CODE_SHARE * code_ok + VISUAL_SHARE * visual_ok
        got = round(points * credit, 2)
        score += got
        row = _item_row(entity, "entity", got >= points, points, why or ("not_visible" if visual_ok is False else ""), meta)
        row.update(earned=got, code=code_ok, visual=visual_ok,
                   seen=(visual or {}).get("seen", {}).get(entity["id"], ""))
        (earned if got >= points else lost).append(row)

    for item in leak_items:
        judgement = report.must_not_present.get(item["id"])
        code_leak, why = _grade_leak(item, judgement, source_normalized)
        visual_leak = bool(use_visual and visual.get("leak"))
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
                "look_evidence": "" if judgement is None else (judgement.evidence or ""),
            })

    return {
        "score": round(max(0.0, score), 2),
        "max_score": POINTS_TOTAL,
        "passed": not lost,
        "earned": earned,
        "lost": lost,
        "visual": {"available": use_visual, "why": (visual or {}).get("why", "not_run"), "time": (visual or {}).get("time")},
    }
