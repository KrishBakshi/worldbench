"""Visual item judge: which of these things can be seen in this biome's frames?

Shared by WC003 (micro-contents) and WC004 (look). Each test brings its own
item list (requirements.json / templates.json) and its own weighting; this
only asks the vision model and returns per-item sightings.

The first question is always whether the frame shows the biome at all. The
navigator agent's own "found" is not trusted for this: on kimi-k-3 it saved
a frame of the volcano and green plains as "Backwater Swamp" at confidence
1.0. A biome frame that does not show the biome counts for nothing.
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
{extra}
ITEMS:
{items}

LEAKS:
{leaks}"""


class Sighting(BaseModel):
    id: str
    visible: bool
    seen: str = ""


class VisualReport(BaseModel):
    shows_biome: bool
    biome_visible: bool
    items: list[Sighting]
    leaks: list[Sighting] = Field(default_factory=list)
    extra: dict[str, bool] = Field(default_factory=dict)


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
) -> VisualReport:
    """images: {name: png}. extra_questions: {key: yes/no question} -> report.extra[key]."""
    extra = ""
    if extra_questions:
        extra = "5. Also answer these yes/no in `extra`:\n" + "\n".join(
            f"   - {k}: {q}" for k, q in extra_questions.items()
        ) + "\n"
    prompt = PROMPT.format(
        label=label,
        image_list=", ".join(images) or "(none)",
        items=_lines(items),
        leaks=_lines(leaks),
        extra=extra,
    )
    return invoke_structured(VisualReport, prompt, list(images.values()), model)


def biome_images(html_path: str | Path, manifest: dict, biome_id: str, *extra_views: str) -> dict[str, Path]:
    """The agent's biome frame (if any), the overview, and any named extra views."""
    cap_dir = Path(html_path).parent / "capture"
    views = manifest.get("views", {})
    names = [f"biome_{biome_id}", "overview", *extra_views]
    return {n: cap_dir / views[n]["path"] for n in names if n in views}


def dump(report: VisualReport | dict) -> dict:
    return report.model_dump() if isinstance(report, VisualReport) else report


def load(payload: dict) -> VisualReport | dict:
    if isinstance(payload, dict) and "error" in payload:
        return payload
    return VisualReport.model_validate(payload)


__all__ = ["VisualReport", "Sighting", "judge_biome", "biome_images", "dump", "load", "json"]
