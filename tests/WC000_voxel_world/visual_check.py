"""VLM bug-hunt over rendered screenshots: floating disconnected blocks and
hollow/gapped masses that a code-only judge can't see. This replaced an
earlier source-only check (bedrock_check.py, removed) that judged "grounded"
and "contiguous" per biome by reading the JS: it scored every real model
output 20/20 with zero discrimination, because the shell-fill pattern it
was checking for is a legitimate hollow-interior rendering optimization
present in essentially every reasonable voxel renderer — not a sign of an
actual bug. Only a rendered screenshot exposes the real defect (see this
file's own hollow_mass prompt-tightening history: even here, an LLM judge
first rationalized a visibly hollow island underside as "stylized... as
designed" before the prompt was fixed to report observation, not intent).

Two-phase per screenshot (same shape as WC002's extract-with-citations
pattern): first describe the scene
and its entities, then hunt specifically for two defect patterns, citing
evidence per entity:
  - floating_blocks: a block with visible empty space between it and the
    blocks that should support/connect it.
  - hollow_mass: a structure that should read as a solid grounded volume but
    has gaps/holes revealing empty space, or isn't solidified into blocks.

VLM findings can only subtract, never award points beyond the baseline —
vision is unreliable for confirming a *positive* ("this looks fine"), but a
confidently-cited visible defect is real signal. Score starts at max (one
point per screenshot) and loses a point per screenshot with a confirmed bug.

Screenshots, two sources (both validated in dry_runs/screenshots_all_models_textmatch/
across all 13 real model outputs before landing here):
  - 4 directional orbit-drags (left/right/top/bottom) — model-agnostic, no
    dependency on any UI, works even if a model has no biome-navigation
    feature at all.
  - Per-biome legend clicks — every model's biome-navigation UI differs in
    DOM/class structure, but every one converges on "clickable element
    containing the biome's visible display name -> flyTo-style camera
    animation" (see capture_biomes_textmatch.py's docstring). So instead of
    a per-model CSS selector, this matches by visible text (Playwright
    get_by_text), trying the canonical label then each keyword synonym in
    turn, and skips a biome cleanly (no guess-click) if none match — that
    skip is itself a signal (recorded in details, not silently dropped).

    uv run python tests/WC000_voxel_world/visual_check.py [world.html] [out_dir]
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from playwright.sync_api import Page, TimeoutError as PWTimeoutError, sync_playwright
from pydantic import BaseModel, Field

load_dotenv()

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))

VIEWPORT = {"width": 1280, "height": 900}
DRAG_FRACTION = 0.30
SIDE_DRAG_FRACTION = 0.04
DIRECTIONS = {
    "right": (0.5, 0.5, 0.5 + SIDE_DRAG_FRACTION, 0.5),
    "left": (0.5, 0.5, 0.5 - SIDE_DRAG_FRACTION, 0.5),
    "top": (0.5, 0.5 - DRAG_FRACTION / 2, 0.5, 0.5 + DRAG_FRACTION),
    "bottom": (0.5, 0.5 + DRAG_FRACTION / 2, 0.5, 0.5 - DRAG_FRACTION),
}

CLICK_TIMEOUT_MS = 2500
BIOME_SETTLE_MS = 3000

# Canonical biomes + keyword synonyms: tests/WC001_trying_all_the_biomes/biome_check.py
# ("volcano"/"forest" broadened after real misses on gemini-3-1-pro's "Volcanic
# Wasteland" and gemini-3-6-flash's "Snowy Forest" — see capture_biomes_textmatch.py).
BIOMES = [
    {"id": "overview", "label": "Whole Island", "keywords": ["overview", "orbit"]},
    {"id": "mountains", "label": "Snow Mountains", "keywords": ["mountain", "peak", "alpine", "snowcap"]},
    {"id": "forest", "label": "Snowy Conifer Forest", "keywords": ["conifer", "pine", "spruce", "taiga", "forest"]},
    {"id": "highlands", "label": "Highlands", "keywords": ["highland", "plateau", "upland"]},
    {"id": "jungle", "label": "Dense Jungle", "keywords": ["jungle", "rainforest", "tropical forest", "canopy"]},
    {"id": "swamp", "label": "Backwater Swamp", "keywords": ["swamp", "marsh", "bog", "wetland", "bayou"]},
    {"id": "grove", "label": "Flowering Grove", "keywords": ["grove", "orchard", "blossom", "flowering"]},
    {"id": "grassland", "label": "Grassland Plateau", "keywords": ["grassland", "prairie", "meadow", "savanna", "grass"]},
    {"id": "delta", "label": "Coastal Delta / Ocean", "keywords": ["estuary", "coast", "ocean", "shoreline", "delta"]},
    {"id": "desert", "label": "Desert Basin", "keywords": ["desert", "dune", "arid", "oasis"]},
    {"id": "volcano", "label": "Volcano", "keywords": ["volcan", "lava", "magma", "obsidian", "caldera"]},
]

DEFAULT_MODEL = os.environ.get("WC000_MODEL") or os.environ.get("WC002_MODEL")

DESCRIBE_PROMPT = """You are looking at a screenshot of a voxel-block 3D world (built entirely out
of cube-shaped blocks, like Minecraft). View: "{direction}".

Describe the scene, then list every distinct entity/structure you can see (terrain, trees,
rocks, water, buildings, lava, mountains, etc). For each entity, briefly describe how it looks
like it's built out of blocks.
"""

BUG_HUNT_PROMPT = """You previously described this voxel-block world screenshot as follows:

{description_json}

Now look at the same image again and hunt specifically for these two bugs, one entity at a
time. Be skeptical — assume bugs are likely and look closely before ruling them out.

1. floating_blocks: a block that has visible empty space between it and the blocks that should
   be supporting or connecting it — block, then a gap, then another block — so it looks like
   it's floating/detached rather than part of a connected structure. This is about individual
   disconnected blocks, not the whole island (the island itself is meant to float).

2. hollow_mass: a structure that should be a solid, grounded volume (a mountain, cliff, tree
   trunk, rock formation, building, island underside, terrain mass) but instead has gaps/holes
   in its surface that let you see through it into empty space or the void, or a structure/patch
   of terrain that just isn't solidified into blocks the way the rest of the terrain is.

   IMPORTANT: report purely what you observe, not what you guess the intent was. If you can see
   black void/empty space through a structure that reads as terrain or a landmass, that IS
   hollow_mass — full stop. Do not excuse it as "stylized," "wireframe," "open by design," "an
   artistic choice," or any other explanation for why it might be intentional. Whether a visible
   gap was intentional is a judgment call for someone else to make downstream — your job here is
   only to report whether void is visible through the structure, not to decide if that's okay.

For each entity from the description, report whether either bug is present, citing exactly
what you see. If you don't see the bug for an entity, say so plainly rather than guessing.
"""


@dataclass
class CheckResult:
    passed: bool
    reason: str
    details: dict = field(default_factory=dict)


class EntityDescription(BaseModel):
    name: str = Field(description="Entity name, e.g. 'pine trees', 'volcano', 'stone bridge'.")
    block_composition: str = Field(description="How this entity appears to be built out of blocks.")


class SceneDescription(BaseModel):
    overview: str
    entities: list[EntityDescription]


class EntityBugFinding(BaseModel):
    entity: str
    floating_blocks_present: bool
    floating_blocks_evidence: str
    hollow_mass_present: bool
    hollow_mass_evidence: str


class BugReport(BaseModel):
    entity_findings: list[EntityBugFinding]
    any_floating_blocks: bool
    any_hollow_mass: bool


def _try_click_by_text(page: Page, candidate: str) -> bool:
    try:
        locator = page.get_by_text(re.compile(re.escape(candidate), re.I)).first
        locator.click(timeout=CLICK_TIMEOUT_MS)
        return True
    except (PWTimeoutError, Exception):
        return False


def _capture_directional_screenshots(page: Page, world_html: Path, shots_dir: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for direction_name, (sx, sy, ex, ey) in DIRECTIONS.items():
        page.goto(world_html.as_uri())
        page.wait_for_timeout(1000)

        start_x, start_y = sx * VIEWPORT["width"], sy * VIEWPORT["height"]
        end_x, end_y = ex * VIEWPORT["width"], ey * VIEWPORT["height"]
        page.mouse.move(start_x, start_y)
        page.mouse.down()
        page.mouse.move(end_x, end_y, steps=15)
        page.mouse.up()
        page.wait_for_timeout(500)

        out_path = shots_dir / f"direction_{direction_name}.png"
        page.screenshot(path=str(out_path))
        paths[f"direction_{direction_name}"] = out_path
    return paths


def _capture_biome_screenshots(page: Page, world_html: Path, shots_dir: Path) -> tuple[dict[str, Path], list[str]]:
    """One navigation, then click straight through every biome in sequence —
    no reload between clicks. Each click's flyTo starts from wherever the
    camera already is (the previous biome), rather than resetting to the
    default view each time."""
    paths: dict[str, Path] = {}
    not_found: list[str] = []

    page.goto(world_html.as_uri())
    page.wait_for_timeout(1200)

    for biome in BIOMES:
        candidates = [biome["label"], *biome["keywords"]]
        clicked = any(_try_click_by_text(page, c) for c in candidates)
        if not clicked:
            not_found.append(biome["id"])
            continue

        page.wait_for_timeout(BIOME_SETTLE_MS)
        out_path = shots_dir / f"biome_{biome['id']}.png"
        page.screenshot(path=str(out_path))
        paths[f"biome_{biome['id']}"] = out_path
    return paths, not_found


def _capture_all_screenshots(html_path: str, out_dir: Path) -> tuple[dict[str, Path], list[str]]:
    world_html = Path(html_path).resolve()
    shots_dir = out_dir / "visual_screenshots"
    shots_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(viewport=VIEWPORT)
        paths = _capture_directional_screenshots(page, world_html, shots_dir)
        biome_paths, not_found = _capture_biome_screenshots(page, world_html, shots_dir)
        paths.update(biome_paths)
        browser.close()
    return paths, not_found


def _image_to_data_url(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def _describe_scene(llm: ChatGoogleGenerativeAI, image_path: Path, direction: str) -> SceneDescription:
    message = HumanMessage(
        content=[
            {"type": "text", "text": DESCRIBE_PROMPT.format(direction=direction)},
            {"type": "image_url", "image_url": _image_to_data_url(image_path)},
        ]
    )
    return llm.with_structured_output(SceneDescription).invoke([message])


def _hunt_bugs(llm: ChatGoogleGenerativeAI, image_path: Path, description: SceneDescription) -> BugReport:
    message = HumanMessage(
        content=[
            {
                "type": "text",
                "text": BUG_HUNT_PROMPT.format(description_json=description.model_dump_json(indent=2)),
            },
            {"type": "image_url", "image_url": _image_to_data_url(image_path)},
        ]
    )
    return llm.with_structured_output(BugReport).invoke([message])


def check_visual_bughunt(html_path: str, out_dir: Path | None = None, model: str | None = None) -> CheckResult:
    from harness.status import log

    dest = Path(out_dir) if out_dir is not None else Path(html_path).parent
    dest.mkdir(parents=True, exist_ok=True)

    log("      capture   (playwright, 4 directions + biome legend clicks)")
    screenshots, biomes_not_found = _capture_all_screenshots(html_path, dest)

    llm = ChatGoogleGenerativeAI(model=DEFAULT_MODEL, google_api_key=os.environ.get("GOOGLE_API_KEY"))

    per_view: dict[str, dict] = {}
    buggy_views: list[str] = []
    for view_name, path in screenshots.items():
        log(f"      judge     (llm) {view_name}")
        description = _describe_scene(llm, path, view_name)
        first_pass = _hunt_bugs(llm, path, description)
        votes = [first_pass]

        # A single LLM sample flip-flops on borderline cases (confirmed: same
        # image, same prompt, "hollow void" vs "solid with dark walls" on
        # different calls). Only re-vote views the first pass already
        # flagged — a false "no bug" left unconfirmed is cheaper to tolerate
        # than a false "bug" that silently costs a model points (VLM
        # findings can only subtract, so a wrong subtraction is the failure
        # mode worth guarding against).
        if first_pass.any_floating_blocks or first_pass.any_hollow_mass:
            log(f"      revote    (llm) {view_name} (flagged on first pass, confirming)")
            votes.append(_hunt_bugs(llm, path, description))
            votes.append(_hunt_bugs(llm, path, description))

        floating_votes = sum(1 for v in votes if v.any_floating_blocks)
        hollow_votes = sum(1 for v in votes if v.any_hollow_mass)
        majority = (len(votes) // 2) + 1
        has_bug = floating_votes >= majority or hollow_votes >= majority

        per_view[view_name] = {
            "description": description.model_dump(),
            "bugs": first_pass.model_dump(),
            "votes": [v.model_dump() for v in votes],
            "vote_tally": {"floating_blocks": floating_votes, "hollow_mass": hollow_votes, "of": len(votes)},
            "final_verdict": has_bug,
            "screenshot": str(path.relative_to(dest)),
        }
        if has_bug:
            buggy_views.append(view_name)

    # Biome legend misses are a capture-coverage signal, not a rendering defect
    # (see capture_biomes_textmatch.py — a miss can be a genuinely narrow
    # keyword list, not proof the biome is absent), so they're recorded but
    # don't subtract from score the way a confirmed visual bug does.
    max_score = len(screenshots)
    score = max_score - len(buggy_views)
    passed = not buggy_views
    reason = (
        f"Scored {score}/{max_score}: no visual defects found across {max_score} views"
        if passed
        else f"Scored {score}/{max_score}: defects found in {', '.join(buggy_views)}"
    )
    if biomes_not_found:
        reason += f" (biome legend not matched: {', '.join(biomes_not_found)})"

    report_path = dest / "visual_bughunt_report.json"
    report_path.write_text(json.dumps(per_view, indent=2), encoding="utf-8")

    return CheckResult(
        passed=passed,
        reason=reason,
        details={
            "score": score,
            "max_score": max_score,
            "missing": buggy_views,
            "biomes_not_found": biomes_not_found,
            "views": per_view,
            "artifacts": {"report": report_path.name},
        },
    )


if __name__ == "__main__":
    from harness.status import log

    html_path = sys.argv[1] if len(sys.argv) > 1 else "dry_runs/inputs/fable/world.html"
    out_dir = None
    if len(sys.argv) > 2:
        out_dir = Path(sys.argv[2]) / f"{Path(html_path).parent.name}__WC000_voxel_world"
        out_dir.mkdir(parents=True, exist_ok=True)

    log(f"WC000  visual  {html_path}")
    result = check_visual_bughunt(html_path, out_dir=out_dir)
    dest = out_dir if out_dir is not None else Path(html_path).parent
    print(f"passed={result.passed} score={result.details['score']}/{result.details['max_score']}", flush=True)
    print(result.reason, flush=True)
    if result.details.get("missing"):
        print(result.details["missing"], flush=True)
    print(f"{dest}/visual_bughunt_report.json", flush=True)
