"""Does the raw world.html text mention every one of the 10 canonical
biomes by at least one keyword synonym?

Regex/keyword pass over the file, not DOM inspection — the legend text in
these worlds is populated client-side by script, so the static HTML has
to be searched for the biome data/names the script embeds, not the empty
#legend element itself.

    uv run python tests/WC001_trying_all_the_biomes/biome_check.py [world.html] [out_dir]
"""

from __future__ import annotations

import json
import re
import sys
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

POINTS_PER_BIOME = 1


def _keyword_pattern(keywords: list[str]) -> re.Pattern:
    alt = "|".join(re.escape(k) for k in keywords)
    return re.compile(rf"\b(?:{alt})\w*", re.IGNORECASE)


def has_all_biomes(
    html_path: str,
    biomes: list[dict] | None = None,
    out_dir: Path | None = None,
) -> CheckResult:
    biomes = biomes or BIOMES
    text = Path(html_path).read_text(encoding="utf-8", errors="ignore")

    found: dict[str, list[str]] = {}
    missing: list[str] = []
    biome_cards = {}
    earned, lost = [], []

    for biome in biomes:
        pattern = _keyword_pattern(biome["keywords"])
        matches = sorted(set(m.group(0).lower() for m in pattern.finditer(text)))
        row = {
            "id": biome["id"],
            "label": biome["label"],
            "kind": "must_present",
            "points": POINTS_PER_BIOME,
            "keywords": biome["keywords"],
            "matched": matches,
        }
        if matches:
            found[biome["id"]] = matches
            earned.append(row)
            biome_cards[biome["id"]] = {
                "score": POINTS_PER_BIOME,
                "max_score": POINTS_PER_BIOME,
                "passed": True,
                "earned": [row],
                "lost": [],
            }
        else:
            missing.append(biome["id"])
            row = {**row, "why": "no_keyword_match"}
            lost.append(row)
            biome_cards[biome["id"]] = {
                "score": 0,
                "max_score": POINTS_PER_BIOME,
                "passed": False,
                "earned": [],
                "lost": [row],
            }

    score = len(found)
    max_score = len(biomes)
    passed = not missing
    reason = (
        "All biomes present"
        if passed
        else f"Missing {len(missing)}/{len(biomes)} biomes: {', '.join(missing)}"
    )
    scorecard = {
        "score": score,
        "max_score": max_score,
        "points_per_biome": POINTS_PER_BIOME,
        "passed": passed,
        "reason": reason,
        "earned": earned,
        "lost": lost,
        "biomes": biome_cards,
    }
    result = CheckResult(
        passed=passed,
        reason=reason,
        details={
            "found": found,
            "missing": missing,
            "score": score,
            "max_score": max_score,
            "scorecard": scorecard,
        },
    )
    dest = Path(out_dir) if out_dir is not None else Path(html_path).parent
    dest.mkdir(parents=True, exist_ok=True)
    score_path = dest / "score.json"
    score_path.write_text(json.dumps(scorecard, indent=2) + "\n", encoding="utf-8")
    result.details["artifacts"] = {"score": score_path.name}
    return result


if __name__ == "__main__":
    html_path = sys.argv[1] if len(sys.argv) > 1 else "dry_runs/inputs/deepseek-v4-pro/world.html"
    out_dir = None
    if len(sys.argv) > 2:
        out_dir = Path(sys.argv[2]) / f"{Path(html_path).parent.name}__WC001_trying_all_the_biomes"
        out_dir.mkdir(parents=True, exist_ok=True)
    result = has_all_biomes(html_path, out_dir=out_dir)
    dest = out_dir if out_dir is not None else Path(html_path).parent
    print(f"passed={result.passed} score={result.details['score']}/{result.details['max_score']}")
    print(result.reason)
    if result.details.get("missing"):
        print(result.details["missing"])
    print(f"{dest}/score.json")
