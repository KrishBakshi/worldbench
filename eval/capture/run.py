"""Capture stage: one set of views per world, shared by every visual test.

    uv run python -m eval.capture.run outputs/<model>            # capture if stale
    uv run python -m eval.capture.run outputs/<model> --force    # recapture

Writes outputs/<model>/capture/:
  preview.html     world.html with its clock patched to obey ?wb_tod=&wb_season=
  views/*.png      every captured frame
  manifest.json    what each frame is, per-biome navigation outcome, and the
                   preview/time-of-day record. Tests read only this.

Order:
  1. preview   LLM patches the world's clock (preview.py).
  2. time      render tod 0 / .25 / .5 / .75 and keep the brightest as "day"
               (pick_day_tod). This is how a wrong patch or an unmapped
               phase offset is caught instead of trusted.
  3. fixed     overview + four orbit directions at day (the bug-hunt and the
               ocean-underside judgement use these), four seasons at day.
  4. biomes    navigator.py, one agent episode per biome, then two motion
               bursts from where the agent left the camera (capture_bursts):
               "near" (the agent's framing) and "far" (zoomed out), each
               BURST_FRAMES frames BURST_GAP_S apart, plus an overlay marking
               changed pixels. Still frames cannot show motion; WC004 judges
               motion from these. Bursts use the daytime preview on purpose:
               at night most moving things (rain, fauna, rivers) are not
               visible at all. Kept deliberately small: one zoom-out, no
               pivots, no waiting for weather cycles.

Deterministic steps run before the agent so a view is only ever an LLM's
choice when it has to be. The manifest records the world's sha256; a later
run with the same world.html reuses it (tests re-grade without recapturing).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from eval.capture.browser import DevToolsBrowser  # noqa: E402
from eval.capture.llm import JudgeUnavailable  # noqa: E402
from eval.capture.navigator import frame_biome  # noqa: E402
from eval.capture.preview import build_preview  # noqa: E402
from harness.status import log  # noqa: E402

MANIFEST_VERSION = 3  # 2: motion bursts; 3: biome frames taken with the HUD hidden
BURST_FRAMES = 3
BURST_GAP_S = 2.0
ZOOM_OUT_STEPS = -3
# A pixel counts as changed when its grey level moves by more than this.
CHANGE_THRESHOLD = 24
TOD_PROBES = (0.0, 0.25, 0.5, 0.75)
SEASONS = ("spring", "summer", "autumn", "winter")
# A day frame must be at least this much brighter than the darkest probe for
# the preview to count as pinning time at all (mean 0-255 luma).
MIN_DAY_NIGHT_GAP = 4.0

DIRECTIONS = {
    "right": (300, 0),
    "left": (-300, 0),
    "top": (0, 220),
    "bottom": (0, -260),
}

BIOMES = [
    {"id": "mountains", "label": "Snow Mountains", "keywords": ["mountain", "peak", "alpine", "snowcap"]},
    {"id": "forest", "label": "Snowy Conifer Forest", "keywords": ["conifer", "pine", "spruce", "taiga", "snow forest"]},
    {"id": "highlands", "label": "Highlands", "keywords": ["highland", "plateau", "upland"]},
    {"id": "jungle", "label": "Dense Jungle", "keywords": ["jungle", "rainforest", "canopy"]},
    {"id": "swamp", "label": "Backwater Swamp", "keywords": ["swamp", "marsh", "bog", "wetland"]},
    {"id": "grove", "label": "Flowering Grove", "keywords": ["grove", "orchard", "blossom"]},
    {"id": "grassland", "label": "Grassland Plateau", "keywords": ["grassland", "prairie", "meadow", "plains"]},
    {"id": "delta", "label": "Coastal Delta / Ocean", "keywords": ["coast", "ocean", "delta", "beach", "estuary"]},
    {"id": "desert", "label": "Desert Basin", "keywords": ["desert", "dune", "arid"]},
    {"id": "volcano", "label": "Volcano", "keywords": ["volcano", "lava", "caldera"]},
]


def manifest_path(output_dir: Path) -> Path:
    return Path(output_dir) / "capture" / "manifest.json"


def load_manifest(output_dir: Path) -> dict | None:
    path = manifest_path(output_dir)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def world_sha(world_html: Path) -> str:
    return hashlib.sha256(Path(world_html).read_bytes()).hexdigest()


# Brightness is measured on lit scene pixels only. The black void and a dark
# HUD panel are most of every frame and never change with time of day, so a
# whole-frame mean squeezed opus-5's day/night range into 7.8-13.8.
LUMA_VOID_MAX = 12       # grey level at or below which a pixel counts as void
LUMA_HUD_CROP = 0.2      # left share of the frame dropped (legends sit there)


def luma(path: Path) -> float:
    from PIL import Image

    img = Image.open(path).convert("L")
    w, h = img.size
    img = img.crop((int(LUMA_HUD_CROP * w), 0, w, h)).resize((320, 250))
    lit = [v for v in img.get_flattened_data() if v > LUMA_VOID_MAX]
    return round(sum(lit) / len(lit), 2) if lit else 0.0


def pick_day_tod(lumas: dict[float, float]) -> tuple[float, float, bool]:
    """(day_tod, night_tod, pinned). pinned is False when no tod made a difference."""
    day = max(lumas, key=lumas.get)
    night = min(lumas, key=lumas.get)
    return day, night, (lumas[day] - lumas[night]) >= MIN_DAY_NIGHT_GAP


def _changed_mask(a: Path, b: Path):
    from PIL import Image, ImageChops

    diff = ImageChops.difference(Image.open(a).convert("L"), Image.open(b).convert("L"))
    return diff.point(lambda v: 255 if v > CHANGE_THRESHOLD else 0)


def motion_overlay(frames: list[Path], out: Path) -> float:
    """Write the first frame dimmed with changed pixels in red; return the changed share."""
    from PIL import Image, ImageChops

    mask = None
    for a, b in zip(frames, frames[1:]):
        m = _changed_mask(a, b)
        mask = m if mask is None else ImageChops.lighter(mask, m)
    base = Image.open(frames[0]).convert("RGB")
    if mask is None:
        base.save(out)
        return 0.0
    dim = base.point(lambda v: v // 2)
    red = Image.new("RGB", base.size, (255, 40, 40))
    Image.composite(red, dim, mask).save(out)
    hist = mask.histogram()
    return round(hist[255] / sum(hist), 5)


async def capture_bursts(browser: DevToolsBrowser, views_dir: Path, view_id: str, first: Path) -> dict:
    """Near burst from the current camera, then zoom out once and a far burst."""
    out: dict = {"bursts": {}, "overlays": {}, "motion_fraction": {}}
    for label in ("near", "far"):
        if label == "far":
            await browser.zoom(ZOOM_OUT_STEPS)
            await asyncio.sleep(1.0)
        frames = [first] if label == "near" else []
        while len(frames) < BURST_FRAMES + (1 if label == "near" else 0):
            if frames:
                await asyncio.sleep(BURST_GAP_S)
            frames.append(await browser.screenshot(views_dir / f"{view_id}_{label}_{len(frames)}.png"))
        overlay = views_dir / f"{view_id}_{label}_motion.png"
        out["bursts"][label] = frames
        out["overlays"][label] = overlay
        out["motion_fraction"][label] = motion_overlay(frames, overlay)
    return out


def _url(preview: Path, tod: float | None = None, season: int | None = None) -> str:
    params = []
    if tod is not None:
        params.append(f"wb_tod={tod}")
    if season is not None:
        params.append(f"wb_season={season}")
    return preview.resolve().as_uri() + (("?" + "&".join(params)) if params else "")


async def _frame_one(browser, day_url, biome, views_dir, cap_dir, manifest, day_tod, model) -> None:
    """One agent episode + motion bursts; writes manifest["biomes"][id] and the view."""
    log(f"      agent     {biome['id']}")
    out = views_dir / f"biome_{biome['id']}.png"
    view_id = f"biome_{biome['id']}"
    manifest["views"].pop(view_id, None)
    try:
        outcome = await frame_biome(browser, day_url, biome, out, model)
    except JudgeUnavailable:
        raise  # not one broken episode: no episode can succeed, so stop the capture
    except Exception as exc:  # one broken episode must not lose the other nine
        outcome = {"status": "error", "reason": str(exc)[:300]}
    if out.is_file() and outcome.get("status") in ("found", "uncertain"):
        log(f"      burst     {view_id}  near + far, {BURST_FRAMES} x {BURST_GAP_S}s")
        try:
            # The saved frame is retaken with the HUD hidden: every judge of a
            # biome frame (and the blind check) sees terrain, never the label.
            await browser.hide_hud(True)
            await browser.screenshot(out)
            b = await capture_bursts(browser, views_dir, view_id, out)
            await browser.hide_hud(False)
            rel = lambda p: str(p.relative_to(cap_dir))  # noqa: E731
            extra = {
                "bursts": {k: [rel(p) for p in v] for k, v in b["bursts"].items()},
                "overlays": {k: rel(p) for k, p in b["overlays"].items()},
                "motion_fraction": b["motion_fraction"],
                "burst_gap_s": BURST_GAP_S,
            }
        except Exception as exc:  # no burst is a missing motion view, not a lost biome
            extra = {"burst_error": str(exc)[:300]}
        manifest["views"][view_id] = {"path": str(out.relative_to(cap_dir)), "kind": "biome",
                                      "biome": biome["id"], "tod": day_tod, **extra}
        outcome["view"] = view_id
    manifest["biomes"][biome["id"]] = outcome


async def _redo_biomes(cap_dir: Path, manifest: dict, ids: list[str], model: str | None) -> None:
    """Re-run only the named biome episodes on the existing preview."""
    preview = cap_dir / "preview.html"
    day_tod = manifest.get("time", {}).get("day_tod", 0.5)
    day_url = _url(preview, day_tod)
    async with DevToolsBrowser() as browser:
        for biome in BIOMES:
            if biome["id"] in ids:
                await _frame_one(browser, day_url, biome, cap_dir / "views", cap_dir, manifest, day_tod, model)


IDENTIFY_PROMPT = """Each image is one frame of a voxel floating island, zoomed toward one region.
For each frame, say which ONE of these biomes it mainly shows, or "none" if it shows
none of them clearly (only sky/void, only UI, or a mix with no main biome):
{options}

Answer for every frame by its name ({names})."""


def identify_biome_frames(cap_dir: Path, manifest: dict, model: str | None = None) -> None:
    """Blind check that each agent frame shows its biome: one call, shuffled, neutral names.

    The navigator's own "found" is not trusted (it saved kimi-k-3's volcano as
    the swamp at confidence 1.0), and asking a judge "does this show the swamp?"
    got yes on all 30 frames across three models. Here the judge is never told
    which biome a frame was meant to be; a frame counts only if its answer
    matches. Result: manifest["biomes"][id]["confirmed"] / ["identified_as"].
    """
    import random

    from pydantic import BaseModel

    from eval.capture.llm import invoke_structured

    class FrameLabel(BaseModel):
        frame: str
        biome: str

    class FrameLabels(BaseModel):
        labels: list[FrameLabel]

    views = manifest.get("views", {})
    framed = [b["id"] for b in BIOMES if f"biome_{b['id']}" in views]
    if not framed:
        return
    order = framed[:]
    random.Random(manifest.get("world_sha256", "")).shuffle(order)
    names = {f"frame_{i + 1}": bid for i, bid in enumerate(order)}
    images = {n: cap_dir / views[f"biome_{bid}"]["path"] for n, bid in names.items()}
    options = "\n".join(f"- {b['id']}: {b['label']}" for b in BIOMES)
    log(f"      identify  (vlm) {len(images)} biome frames, blind")
    try:

        result = invoke_structured(
            FrameLabels, IDENTIFY_PROMPT.format(options=options, names=", ".join(images)), list(images.values()), model
        )
        answers = {x.frame: x.biome.strip().lower() for x in result.labels}
    except JudgeUnavailable:
        raise
    except Exception as exc:
        log(f"      identify  error: {exc}")
        manifest["identify_error"] = str(exc)[:300]
        return
    for name, bid in names.items():
        said = answers.get(name, "none")
        manifest["biomes"][bid]["identified_as"] = said
        manifest["biomes"][bid]["confirmed"] = said == bid
    manifest["identified"] = True
    ok = sum(1 for bid in framed if manifest["biomes"][bid]["confirmed"])
    log(f"      identify  {ok}/{len(framed)} frames confirmed")


def confirmed_biome_view(manifest: dict, biome_id: str) -> str | None:
    """The biome's view id if the blind check confirmed it, else None."""
    b = manifest.get("biomes", {}).get(biome_id, {})
    view = f"biome_{biome_id}"
    if view in manifest.get("views", {}) and b.get("confirmed"):
        return view
    return None


async def _capture(world_html: Path, cap_dir: Path, model: str | None) -> dict:
    views_dir = cap_dir / "views"
    views_dir.mkdir(parents=True, exist_ok=True)
    preview = cap_dir / "preview.html"
    manifest: dict = {
        "version": MANIFEST_VERSION,
        "world_sha256": world_sha(world_html),
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "views": {},
        "biomes": {},
    }

    def add_view(view_id: str, path: Path, kind: str, **extra) -> None:
        manifest["views"][view_id] = {"path": str(path.relative_to(cap_dir)), "kind": kind, **extra}

    manifest["preview"] = await asyncio.to_thread(build_preview, world_html, preview, model)

    async with DevToolsBrowser() as browser:
        # 2. time of day
        lumas: dict[float, float] = {}
        for tod in TOD_PROBES:
            log(f"      time      tod={tod}")
            await browser.open(_url(preview, tod))
            path = await browser.screenshot(views_dir / f"tod_{tod:.2f}.png")
            lumas[tod] = luma(path)
            add_view(f"tod_{tod:.2f}", path, "time", tod=tod, luma=lumas[tod])
        day_tod, night_tod, pinned = pick_day_tod(lumas)
        manifest["time"] = {"lumas": {str(k): v for k, v in lumas.items()}, "day_tod": day_tod, "night_tod": night_tod, "pinned": pinned}
        log(f"      time      day={day_tod} night={night_tod} pinned={pinned}  lumas={lumas}")
        day_url = _url(preview, day_tod)

        # 3. fixed views
        manifest["views"]["overview"] = {**manifest["views"][f"tod_{day_tod:.2f}"], "kind": "overview"}
        for name, (dx, dy) in DIRECTIONS.items():
            log(f"      view      direction_{name}")
            await browser.open(day_url)
            await browser.orbit(dx, dy)
            add_view(f"direction_{name}", await browser.screenshot(views_dir / f"direction_{name}.png"), "direction", tod=day_tod)
        if manifest["preview"].get("season_found"):
            for i, season in enumerate(SEASONS):
                log(f"      view      season_{season}")
                await browser.open(_url(preview, day_tod, i))
                add_view(f"season_{season}", await browser.screenshot(views_dir / f"season_{season}.png"), "season", tod=day_tod, season=i)

        # 4. biomes
        for biome in BIOMES:
            await _frame_one(browser, day_url, biome, views_dir, cap_dir, manifest, day_tod, model)
    return manifest


def capture(output_dir: Path, *, force: bool = False, model: str | None = None) -> dict:
    """Capture outputs/<model>/world.html once; reuse a manifest for the same world."""
    output_dir = Path(output_dir)
    world_html = output_dir / "world.html"
    existing = load_manifest(output_dir)
    cap_dir = output_dir / "capture"
    if (
        not force
        and existing
        and existing.get("version") == MANIFEST_VERSION
        and existing.get("world_sha256") == world_sha(world_html)
    ):
        manifest = existing
        # A reused capture must not carry failed episodes forward (a quota
        # error on grok-4-6 would otherwise stick to that world forever).
        errored = [bid for bid, b in manifest.get("biomes", {}).items() if b.get("status") == "error"]
        if errored:
            log(f"      capture   redo failed episodes: {', '.join(errored)}")
            asyncio.run(_redo_biomes(cap_dir, manifest, errored, model))
            manifest.pop("identified", None)
        else:
            log("      capture   reuse manifest (same world.html)")
    else:
        cap_dir.mkdir(parents=True, exist_ok=True)
        manifest = asyncio.run(_capture(world_html, cap_dir, model))
    if not manifest.get("identified"):
        identify_biome_frames(cap_dir, manifest, model)
    manifest_path(output_dir).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    found = sum(1 for b in manifest["biomes"].values() if b.get("status") == "found")
    log(f"      capture   {len(manifest['views'])} views, {found}/{len(BIOMES)} biomes framed")
    return manifest


def ensure_capture(html_path: str | Path, model: str | None = None) -> dict:
    """For a test given outputs/<model>/world.html: the manifest, capturing first if needed."""
    return capture(Path(html_path).parent, model=model)


def view_paths(html_path: str | Path, manifest: dict, *kinds: str) -> dict[str, Path]:
    """{view_id: absolute png path} for every view of the given kinds."""
    cap_dir = Path(html_path).parent / "capture"
    return {
        view_id: cap_dir / view["path"]
        for view_id, view in manifest.get("views", {}).items()
        if not kinds or view.get("kind") in kinds
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Capture views of outputs/<model>/world.html for the visual judges")
    parser.add_argument("output_dir")
    parser.add_argument("--force", action="store_true", help="recapture even if the manifest matches")
    parser.add_argument("--model", help="use this model for every judge/agent call (default: roles in eval/judge.yaml)")
    args = parser.parse_args(argv)
    manifest = capture(Path(args.output_dir), force=args.force, model=args.model)
    print(json.dumps({k: manifest[k] for k in ("time", "biomes")}, indent=2))


if __name__ == "__main__":
    main()
