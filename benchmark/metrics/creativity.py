"""Metric: creativity.

A deliberately heuristic score. There is no reference world to compare against,
so creativity is approximated by proxies for richness and imagination: the
variety of biome types employed, the density of authored prose descriptions,
the presence of dynamic systems (natural events and long-term dynamics), and
descriptive-tag variety. It is the lowest-weighted metric precisely because it
is the softest signal.
"""

from __future__ import annotations

from ..models import World
from ..results import MetricResult, ValidationReport
from ._common import clamp

NAME = "creativity"
WEIGHT = 0.05


def _description_density(world: World) -> float:
    """Fraction of describable entities that carry non-trivial prose."""
    described = total = 0
    groups = [
        world.layout.regions,
        world.terrain.features,
        world.water.bodies,
        world.biomes.zones,
        world.flora.species,
        world.fauna.species,
    ]
    for group in groups:
        for entity in group:
            total += 1
            text = getattr(entity, "description", "") or ""
            if len(text.strip()) >= 20:
                described += 1
    return 0.0 if total == 0 else described / total


def score(world: World, report: ValidationReport | None = None) -> MetricResult:
    """Score imaginative richness via richness/prose/dynamics proxies."""
    biome_variety = clamp(100.0 * min(1.0, len({z.type for z in world.biomes.zones}) / 8))
    prose = clamp(100.0 * _description_density(world))
    dynamics = clamp(
        100.0
        * min(1.0, (len(world.natural_events.events) + len(world.simulation.dynamics)) / 4)
    )
    tags = clamp(100.0 * min(1.0, len(set(world.metadata.tags)) / 5))

    value = clamp(0.30 * biome_variety + 0.30 * prose + 0.25 * dynamics + 0.15 * tags)
    detail = (
        f"biome variety {biome_variety:.0f}, prose {prose:.0f}, "
        f"dynamics {dynamics:.0f}, tags {tags:.0f}"
    )
    return MetricResult(name=NAME, score=value, weight=WEIGHT, detail=detail)
