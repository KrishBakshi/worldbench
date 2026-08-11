"""Does the raw world.html text mention every one of the 10 canonical
biomes by at least one keyword synonym?

Regex/keyword pass over the file, not DOM inspection — the legend text in
these worlds is populated client-side by script, so the static HTML has
to be searched for the biome data/names the script embeds, not the empty
#legend element itself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CheckResult:
    passed: bool
    reason: str
    details: dict = field(default_factory=dict)


# Canonical biomes: worldbench-web/components/about/BiomeGraph.tsx (a
# spoiler file never shown to the model). Keywords are synonyms a model
# might use instead of the exact label (e.g. "rainforest" for jungle).
BIOMES: list[dict] = [
    {"id": "mountains", "label": "Snow Mountains", "keywords": ["mountain", "peak", "alpine", "snowcap"]},
    {"id": "forest", "label": "Snowy Conifer Forest", "keywords": ["conifer", "pine", "spruce", "taiga"]},
    {"id": "highlands", "label": "Highlands", "keywords": ["highland", "plateau", "upland"]},
    {"id": "jungle", "label": "Dense Jungle", "keywords": ["jungle", "rainforest", "tropical forest", "canopy"]},
    {"id": "swamp", "label": "Backwater Swamp", "keywords": ["swamp", "marsh", "bog", "wetland", "bayou"]},
    {"id": "grove", "label": "Flowering Grove", "keywords": ["grove", "orchard", "blossom", "flowering"]},
    {"id": "grassland", "label": "Grassland Plateau", "keywords": ["grassland", "prairie", "meadow", "savanna"]},
    {"id": "delta", "label": "Coastal Delta / Ocean", "keywords": ["estuary", "coast", "ocean", "shoreline"]},
    {"id": "desert", "label": "Desert Basin", "keywords": ["desert", "dune", "arid", "oasis"]},
    {"id": "volcano", "label": "Volcano", "keywords": ["volcano", "lava", "magma", "obsidian", "caldera"]},
]


def _keyword_pattern(keywords: list[str]) -> re.Pattern:
    alt = "|".join(re.escape(k) for k in keywords)
    return re.compile(rf"\b(?:{alt})\w*", re.IGNORECASE)


def has_all_biomes(html_path: str, biomes: list[dict] | None = None) -> CheckResult:
    biomes = biomes or BIOMES
    text = Path(html_path).read_text(encoding="utf-8", errors="ignore")

    found: dict[str, list[str]] = {}
    missing: list[str] = []
    for biome in biomes:
        pattern = _keyword_pattern(biome["keywords"])
        matches = sorted(set(m.group(0).lower() for m in pattern.finditer(text)))
        if matches:
            found[biome["id"]] = matches
        else:
            missing.append(biome["id"])

    score = len(found)
    max_score = len(biomes)
    passed = not missing
    reason = (
        "All biomes present"
        if passed
        else f"Missing {len(missing)}/{len(biomes)} biomes: {', '.join(missing)}"
    )
    return CheckResult(
        passed=passed,
        reason=reason,
        details={"found": found, "missing": missing, "score": score, "max_score": max_score},
    )

if __name__ == "__main__":
    print(has_all_biomes("/Users/krish/Workspace/worldbench/dry_runs/inputs/deepseek-v4-pro/world.html"))