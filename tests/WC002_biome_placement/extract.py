from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from llm import ClassifiedBiomeJS, ExtractedGraph, invoke_structured, load_prompt

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

def extract_graph(classified: ClassifiedBiomeJS, model: str | None = None) -> ExtractedGraph:
    biome_list = "\n".join(f"- {bid}: {label}" for bid, label in BIOME_LABELS.items())
    prompt = load_prompt("extract.md").replace("{biome_list}", biome_list)
    return invoke_structured(
        ExtractedGraph,
        prompt + "\n\nBIOMES:\n" + classified.model_dump_json(),
        model,
    )
