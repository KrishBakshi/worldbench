"""Is each biome covered at all? Folded in from the old keyword-coverage test.

That test searched the stripped JS for biome keywords. Every scored model got
10/10, and a one-line file with no world (`const pine=1,canopy=2,...,lava=9`)
also scored 10/10: `grass` counts as grassland and `ocean` as delta the
moment those materials exist. That measured vocabulary, not a built biome.

A biome is covered when either source shows it:
  - source: the classify step marks it present AND the layout code it quotes
    is really in the source (eval/evidence.py), or
  - frames: the capture's blind check identified that biome's frame as that
    biome without being told which it was meant to be.
One LLM call alone used to decide this and missed opus-5's ocean (10 mentions
in the source, framed and judged in WC003). A keyword alone, or a quote the
judge invented, is still not coverage.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))

from eval.evidence import in_source, normalize  # noqa: E402
from llm import ClassifiedBiomeJS  # noqa: E402


def _source_why(block, src: str) -> str:
    if block is None or not block.present:
        return "not_present"
    quotes = [q for q in (block.placement_code, block.elevation_code) if q.strip()]
    if not quotes:
        return "no_layout_code"
    if not any(in_source(q, src) for q in quotes):
        return "layout_code_not_in_source"
    return ""


def biome_coverage(
    classified: ClassifiedBiomeJS,
    source: str,
    biome_ids,
    confirmed_frames: set[str] | None = None,
) -> dict[str, dict]:
    """{biome_id: {"covered": bool, "by": [...], "why": str}}"""
    src = normalize(source)
    frames = confirmed_frames or set()
    out: dict[str, dict] = {}
    for bid in biome_ids:
        why = _source_why(classified.biomes.get(bid), src)
        by = ([] if why else ["source"]) + (["frame"] if bid in frames else [])
        out[bid] = {"covered": bool(by), "by": by, "why": "" if by else f"{why}; frame not confirmed"}
    return out
