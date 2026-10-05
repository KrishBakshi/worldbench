"""Visual item judge: which of these things can be seen in this biome's frames?

Shared by WC003 (micro-contents) and WC004 (look). Each test brings its own
item list (requirements.json / templates.json) and its own weighting; this
only asks the vision model and returns per-item sightings.

Which frame shows which biome is decided before this, blind, by the capture
(run.identify_biome_frames): only a confirmed biome frame is passed in, and
callers overwrite `shows_biome` with that blind result. Asked directly
("does this show the swamp?") the judge said yes on all 30 frames across
three models, including kimi-k-3's volcano saved as the swamp.

With `motion_items` + `bursts`, the same call also judges motion from the
burst frames (WC004), instead of a second call per biome.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from eval.capture.llm import invoke_structured

PROMPT = """You are judging frames of a Minecraft-like voxel floating island.
Biome under test: {label}.

Images: {image_list}

1. shows_biome: does the biome frame (the one named biome_*) clearly show {label}?
   If there is no biome frame, judge whether {label} is visible in the overview.
2. biome_visible: is {label} visible anywhere in any image?
3. For every ITEM, visible = true only if you can SEE it in the images in or at
   {label}. Describe what you see in <= 15 words. Do not infer from the biome name:
   a snowy biome does not imply visible snowfall.
4. For every LEAK (things that must NOT be in {label}), visible = true if you see it
   there.
{extra}{motion}
ITEMS:
{items}

LEAKS:
{leaks}"""

MOTION_SECTION = """
MOTION: burst frames (near_*, far_*) are {gap}s apart with the camera still; *_motion
images are the first burst frame dimmed with every changed pixel painted RED (small
scattered red specks are usually moving particles; large flat red patches over
terrain are usually light, shadow or fog changes, NOT an entity moving). For every
MOTION ITEM report in `motion`: moving (visibly moves between frames?), axis (one of
falling, blowing, rising, flowing, pulsing, still, grounded), seen (<= 15 words; "not
visible" if you cannot see it).
MOTION ITEMS:
{motion_items}
"""


class Sighting(BaseModel):
    id: str
    visible: bool
    seen: str = ""


class MotionSighting(BaseModel):
    id: str
    moving: bool
    axis: str = "still"
    seen: str = ""


class VisualReport(BaseModel):
    shows_biome: bool
    biome_visible: bool
    items: list[Sighting]
    leaks: list[Sighting] = Field(default_factory=list)
    extra: dict[str, bool] = Field(default_factory=dict)
    motion: list[MotionSighting] = Field(default_factory=list)


def _lines(entries: list[dict]) -> str:
    out = []
    for e in entries:
        desc = e.get("looks_like") or e.get("label", "")
        out.append(f"- {e['id']}: {desc}")
    return "\n".join(out) or "(none)"


def judge_biome(
    label: str,
    images: dict[str, Path],
    items: list[dict],
    leaks: list[dict],
    extra_questions: dict[str, str] | None = None,
    model: str | None = None,
    motion_items: list[dict] | None = None,
    bursts: dict[str, Path] | None = None,
    burst_gap: float | str = "?",
) -> VisualReport:
    """images: {name: png}. extra_questions: {key: yes/no question} -> report.extra[key].
    motion_items + bursts: also judge motion from the burst frames -> report.motion."""
    extra = ""
    if extra_questions:
        extra = "5. Also answer these yes/no in `extra`:\n" + "\n".join(
            f"   - {k}: {q}" for k, q in extra_questions.items()
        ) + "\n"
    motion = ""
    all_images = dict(images)
    if motion_items and bursts:
        motion = MOTION_SECTION.format(
            gap=burst_gap,
            motion_items="\n".join(
                f"- {e['id']}: {e.get('looks_like') or e.get('label', '')} (expected: {e.get('expected_axis')})"
                for e in motion_items
            ),
        )
        all_images.update(bursts)
    prompt = PROMPT.format(
        label=label,
        image_list=", ".join(all_images) or "(none)",
        items=_lines(items),
        leaks=_lines(leaks),
        extra=extra,
        motion=motion,
    )
    return invoke_structured(VisualReport, prompt, list(all_images.values()), model)


def biome_images(html_path: str | Path, manifest: dict, biome_id: str, *extra_views: str) -> dict[str, Path]:
    """The biome frame (only if the blind check confirmed it), the overview, and extra views."""
    from eval.capture.run import confirmed_biome_view

    cap_dir = Path(html_path).parent / "capture"
    views = manifest.get("views", {})
    names = [n for n in (confirmed_biome_view(manifest, biome_id), "overview", *extra_views) if n]
    return {n: cap_dir / views[n]["path"] for n in names if n in views}


def burst_images(html_path: str | Path, manifest: dict, biome_id: str) -> tuple[dict[str, Path], float | str]:
    """Near/far burst frames + overlays for a confirmed biome frame ({} if none)."""
    from eval.capture.run import confirmed_biome_view

    view_id = confirmed_biome_view(manifest, biome_id)
    view = manifest.get("views", {}).get(view_id or "", {})
    if not view.get("bursts"):
        return {}, "?"
    cap_dir = Path(html_path).parent / "capture"
    out: dict[str, Path] = {}
    for label, frames in view["bursts"].items():
        for n, rel in enumerate(frames):
            out[f"{label}_{n}"] = cap_dir / rel
        out[f"{label}_motion"] = cap_dir / view["overlays"][label]
    return out, view.get("burst_gap_s", "?")


def confirm(report: VisualReport | dict, manifest: dict, biome_id: str) -> VisualReport | dict:
    """Overwrite the judge's own shows_biome with the capture's blind result."""
    from eval.capture.run import confirmed_biome_view

    if isinstance(report, VisualReport):
        report.shows_biome = confirmed_biome_view(manifest, biome_id) is not None
    return report


def dump(report: VisualReport | dict) -> dict:
    return report.model_dump() if isinstance(report, VisualReport) else report


def load(payload: dict) -> VisualReport | dict:
    if isinstance(payload, dict) and "error" in payload:
        return payload
    return VisualReport.model_validate(payload)


__all__ = [
    "VisualReport", "Sighting", "MotionSighting", "judge_biome", "biome_images", "burst_images",
    "confirm", "dump", "load", "json",
]
