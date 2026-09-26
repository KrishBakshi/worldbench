"""Is each biome covered at all? Folded in from the old WC001.

WC001 searched the stripped JS for biome keywords. Every scored model got
10/10, and a one-line file with no world (`const pine=1,canopy=2,...,lava=9`)
also scored 10/10: `grass` counts as grassland and `ocean` as delta the
moment those materials exist. That measured vocabulary, not a built biome.

Here a biome is covered when the classify step (an LLM that already reads
the source for placement) marks it present AND the layout code it quotes for
that biome is really in the source (eval/evidence.py). A keyword alone, or a
quote the judge invented, is not coverage.
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


def biome_coverage(classified: ClassifiedBiomeJS, source: str, biome_ids) -> dict[str, dict]:
    """{biome_id: {"covered": bool, "why": str}}"""
    src = normalize(source)
    out: dict[str, dict] = {}
    for bid in biome_ids:
        block = classified.biomes.get(bid)
        if block is None or not block.present:
            out[bid] = {"covered": False, "why": "not_present"}
            continue
        quotes = [q for q in (block.placement_code, block.elevation_code) if q.strip()]
        if not quotes:
            out[bid] = {"covered": False, "why": "no_layout_code"}
        elif not any(in_source(q, src) for q in quotes):
            out[bid] = {"covered": False, "why": "layout_code_not_in_source"}
        else:
            out[bid] = {"covered": True, "why": ""}
    return out
