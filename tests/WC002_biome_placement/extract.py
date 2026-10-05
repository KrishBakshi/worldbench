from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
if str(Path(__file__).resolve().parents[2]) not in sys.path:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from llm import ExtractedGraph, invoke_structured, load_prompt

from eval.capture.llm import extract_model_name  # noqa: E402

BIOME_LABELS = {
    "mountains": "Snow Mountains",
    "forest": "Snowy Conifer Forest",
    "highlands": "Highlands",
    "jungle": "Dense Jungle",
    "swamp": "Backwater Swamp",
    "grove": "Flowering Grove",
    "grassland": "Grassland Plateau",
    "delta": "Coastal Delta / Ocean",
    "desert": "Desert Basin",
    "volcano": "Volcano",
}

def extract_graph(js: str, model: str | None = None) -> ExtractedGraph:
    """Read the layout from the whole stripped source, not from classify's per-biome
    slices. Slices often quote only a shared nearest-centre loop and drop the table
    of centres it reads, which left the extractor guessing: on real worlds it
    returned no links at all (positions missing) or every pair (one loop tests all
    biomes). Checked against four worlds' real biome maps (2026-10-05 re-run),
    rule-relevant pairs right went from 46/76 to 61/76, and invented links from 32
    to 10."""
    biome_list = "\n".join(f"- {bid}: {label}" for bid, label in BIOME_LABELS.items())
    prompt = load_prompt("extract.md").replace("{biome_list}", biome_list)
    return invoke_structured(
        ExtractedGraph,
        prompt + "\n\nSOURCE:\n" + js,
        model=extract_model_name(model),
    )
