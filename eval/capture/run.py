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
  4. biomes    navigator.py, one agent episode per biome.

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
from eval.capture.navigator import frame_biome  # noqa: E402
from eval.capture.preview import build_preview  # noqa: E402
from harness.status import log  # noqa: E402

MANIFEST_VERSION = 1
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


def luma(path: Path) -> float:
    from PIL import Image, ImageStat

    return round(ImageStat.Stat(Image.open(path).convert("L")).mean[0], 2)


def pick_day_tod(lumas: dict[float, float]) -> tuple[float, float, bool]:
    """(day_tod, night_tod, pinned). pinned is False when no tod made a difference."""
    day = max(lumas, key=lumas.get)
    night = min(lumas, key=lumas.get)
    return day, night, (lumas[day] - lumas[night]) >= MIN_DAY_NIGHT_GAP


def _url(preview: Path, tod: float | None = None, season: int | None = None) -> str:
    params = []
    if tod is not None:
        params.append(f"wb_tod={tod}")
    if season is not None:
        params.append(f"wb_season={season}")
    return preview.resolve().as_uri() + (("?" + "&".join(params)) if params else "")


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
            log(f"      agent     {biome['id']}")
            out = views_dir / f"biome_{biome['id']}.png"
            try:
                outcome = await frame_biome(browser, day_url, biome, out, model)
            except Exception as exc:  # one broken episode must not lose the other nine
                outcome = {"status": "error", "reason": str(exc)[:300]}
            if out.is_file() and outcome.get("status") in ("found", "uncertain"):
                add_view(f"biome_{biome['id']}", out, "biome", biome=biome["id"], tod=day_tod)
                outcome["view"] = f"biome_{biome['id']}"
            manifest["biomes"][biome["id"]] = outcome
    return manifest


def capture(output_dir: Path, *, force: bool = False, model: str | None = None) -> dict:
    """Capture outputs/<model>/world.html once; reuse a manifest for the same world."""
    output_dir = Path(output_dir)
    world_html = output_dir / "world.html"
    existing = load_manifest(output_dir)
    if (
        not force
        and existing
        and existing.get("version") == MANIFEST_VERSION
        and existing.get("world_sha256") == world_sha(world_html)
    ):
        log("      capture   reuse manifest (same world.html)")
        return existing
    cap_dir = output_dir / "capture"
    cap_dir.mkdir(parents=True, exist_ok=True)
    manifest = asyncio.run(_capture(world_html, cap_dir, model))
    manifest_path(output_dir).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    found = sum(1 for b in manifest["biomes"].values() if b.get("status") == "found")
    log(f"      capture   {len(manifest['views'])} views, {found}/{len(BIOMES)} biomes framed")
    return manifest


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Capture views of outputs/<model>/world.html for the visual judges")
    parser.add_argument("output_dir")
    parser.add_argument("--force", action="store_true", help="recapture even if the manifest matches")
    parser.add_argument("--model", help="judge/agent model (default CAPTURE_MODEL or WC002_MODEL)")
    args = parser.parse_args(argv)
    manifest = capture(Path(args.output_dir), force=args.force, model=args.model)
    print(json.dumps({k: manifest[k] for k in ("time", "biomes")}, indent=2))


if __name__ == "__main__":
    main()
