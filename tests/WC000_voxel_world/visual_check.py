"""VLM bug-hunt over the captured daytime views.

Views come from the shared capture stage (eval/capture/run.py): the daytime
overview, four orbit directions, and the navigator agent's per-biome frames.
This file used to drive Playwright itself; now every visual test judges the
same frames, captured once at a pinned daytime.

One call per view lists the entities, then hunts four defects:
  - floating_blocks: a block with empty space between it and what should hold it.
  - hollow_mass:     a solid-looking volume with holes into the void.
  - non_voxel:       terrain that is smooth/curved instead of chunky cubes.
  - water_void:      a water sheet running out over the void with no blocks
                     under or around it (a sea with no seabed).

Weather, particles, clouds, mist, the sun and UI are excluded by the prompt:
on opus-5 most of the 10 flagged views were clouds called non_voxel and
falling particles called floating_blocks, penalising a richer atmosphere.

Findings only subtract: vision is poor at confirming a positive, but a cited
visible defect is real signal. A first-pass flag is re-voted twice and kept
only on majority, since one sample flip-flops on borderline frames.

Scoring has a fixed max (MAX_SCORE) no matter how many views exist:
MAX_SCORE x clean_views / judged_views, counting only the per-view defects
(PER_VIEW_DEFECTS). The old score was one point per screenshot, so a world
whose legend could not be clicked had fewer chances to lose points.

`water_void` is a property of the world, not of a frame: one ocean sheet
over the void shows up in almost every view (6 of 15 on kimi-k-3), and
counting it per view cost that one defect two thirds of the test. It is
reported once, as "ocean_void" in `missing`, when at least OCEAN_VOID_VIEWS
orbit views agree. WC003 charges the delta biome for it; the island gate in
eval/score.py reads it for WC004.

    uv run python tests/WC000_voxel_world/visual_check.py [world.html] [out_dir]
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

from eval.capture.llm import JudgeUnavailable, invoke_structured, raise_if_mostly_failed  # noqa: E402
from eval.capture.run import ensure_capture, view_paths  # noqa: E402

MAX_SCORE = 20
DEFECTS = ("floating_blocks", "hollow_mass", "non_voxel", "water_void")
PER_VIEW_DEFECTS = ("floating_blocks", "hollow_mass", "non_voxel")
OCEAN_VOID_VIEWS = 2

BUG_HUNT_PROMPT = """This is one frame of a 3D world meant to be a Minecraft-like voxel floating
island in a black void. View: "{view}".

First list the distinct entities you see (terrain masses, cliffs, trees, rocks, water,
lava, buildings, animals) and how each looks built. Then hunt four defects, one entity
at a time. Assume defects are likely.

1. floating_blocks: a block with visible empty space between it and the blocks that
   should support or connect it. (The island itself floats by design.)
2. hollow_mass: a structure that should be a solid volume (mountain, cliff, trunk,
   terrain mass, island underside) with holes showing the void through it.
3. non_voxel: terrain or landforms that are smooth, curved, or a displaced surface
   rather than chunky axis-aligned cubes.
4. water_void: water that spreads out as a flat sheet beyond the land, over the black
   void, with no blocks beneath or around it holding it.

IGNORE entirely, never a defect: weather and particles (rain, snow, petals, ash,
sparks, dust), clouds, mist, fog, smoke, the sun and moon, and UI. Those float and
may be flat by design. Judge only terrain, water bodies, plants, animals and built
structures.

Report what you SEE, not the likely intent. Void visible through terrain IS hollow_mass;
do not excuse it as stylized. If a defect is absent for an entity, say so plainly."""


@dataclass
class CheckResult:
    passed: bool
    reason: str
    details: dict = field(default_factory=dict)


class EntityBugFinding(BaseModel):
    entity: str
    floating_blocks: bool
    hollow_mass: bool
    non_voxel: bool
    water_void: bool
    evidence: str = Field(description="what you see, <= 30 words")


class BugReport(BaseModel):
    overview: str = Field(description="one line: what the frame shows")
    entity_findings: list[EntityBugFinding]
    any_floating_blocks: bool
    any_hollow_mass: bool
    any_non_voxel: bool
    any_water_void: bool


def _flags(report: BugReport) -> dict[str, bool]:
    return {d: bool(getattr(report, f"any_{d}")) for d in DEFECTS}


def judge_view(path: Path, view_id: str, model: str | None = None) -> dict:
    # Describe and hunt are one call (the describe step used to be its own
    # call, doubling the cost of every view against a 500/day quota).
    hunt = BUG_HUNT_PROMPT.format(view=view_id)
    votes = [invoke_structured(BugReport, hunt, [path], model)]
    if any(_flags(votes[0]).values()):
        votes += [invoke_structured(BugReport, hunt, [path], model, temperature=0.8) for _ in range(2)]
    tally = {d: sum(1 for v in votes if _flags(v)[d]) for d in DEFECTS}
    majority = len(votes) // 2 + 1
    confirmed = sorted(d for d, n in tally.items() if n >= majority)
    return {
        "description": votes[0].overview,
        "votes": [v.model_dump() for v in votes],
        "tally": {**tally, "of": len(votes)},
        "defects": confirmed,
    }


def check_visual_bughunt(html_path: str, out_dir: Path | None = None, model: str | None = None) -> CheckResult:
    from harness.status import log

    manifest = ensure_capture(html_path, model)
    views = view_paths(html_path, manifest, "overview", "direction", "biome")
    dest = Path(out_dir) if out_dir is not None else Path(html_path).parent
    dest.mkdir(parents=True, exist_ok=True)

    per_view: dict[str, dict] = {}
    for view_id, path in views.items():
        log(f"      judge     (vlm) {view_id}")
        try:
            per_view[view_id] = judge_view(path, view_id, model)
        except JudgeUnavailable:
            raise
        except Exception as exc:  # a failed call is not a defect; leave it out of the ratio
            per_view[view_id] = {"error": str(exc)[:300], "defects": None}
        per_view[view_id]["screenshot"] = str(path)

    raise_if_mostly_failed(per_view, "visual bug-hunt")
    judged = {k: v for k, v in per_view.items() if v.get("defects") is not None}
    view_defects = {k: [d for d in v["defects"] if d in PER_VIEW_DEFECTS] for k, v in judged.items()}
    buggy = sorted(k for k, d in view_defects.items() if d)
    score = round(MAX_SCORE * (len(judged) - len(buggy)) / len(judged), 2) if judged else 0.0
    void_views = sorted(k for k, v in judged.items() if k.startswith(("overview", "direction")) and "water_void" in v["defects"])
    ocean_void = len(void_views) >= OCEAN_VOID_VIEWS
    missing = buggy + (["ocean_void"] if ocean_void else [])
    passed = not buggy
    reason = (
        f"Scored {score}/{MAX_SCORE}: no visual defects across {len(judged)} views"
        if passed
        else f"Scored {score}/{MAX_SCORE}: defects in {', '.join(f'{k} ({'/'.join(view_defects[k])})' for k in buggy)}"
    )
    if ocean_void:
        reason += f"; ocean spreads over the void ({', '.join(void_views)})"
    report_path = dest / "visual_bughunt_report.json"
    report_path.write_text(json.dumps(per_view, indent=2), encoding="utf-8")
    return CheckResult(passed, reason, {
        "score": score,
        "max_score": MAX_SCORE,
        "missing": missing,
        "ocean_void": ocean_void,
        "ocean_void_views": void_views,
        "views_judged": len(judged),
        "views_failed": sorted(set(per_view) - set(judged)),
        "biome_capture": manifest.get("biomes", {}),
        "artifacts": {"report": report_path.name},
    })


if __name__ == "__main__":
    from harness.status import log

    html_path = sys.argv[1] if len(sys.argv) > 1 else "outputs/opus-5/world.html"
    out_dir = Path(sys.argv[2]) / f"{Path(html_path).parent.name}__WC000_voxel_world" if len(sys.argv) > 2 else None
    log(f"WC000  visual  {html_path}")
    result = check_visual_bughunt(html_path, out_dir)
    print(f"passed={result.passed} score={result.details['score']}/{result.details['max_score']}")
    print(result.reason)
