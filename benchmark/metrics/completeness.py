"""Metric: completeness.

Rewards worlds that populate every schema section with a non-trivial amount of
content, and that go beyond the bare minimum by including the optional-but-
expected ecological layers (interactions, natural events, long-term dynamics).
"""

from __future__ import annotations

from ..models import World
from ..results import MetricResult, ValidationReport
from ._common import clamp

NAME = "completeness"
WEIGHT = 0.10

#: (label, count, target) — target is the count considered "fully populated".
def _section_targets(world: World) -> list[tuple[str, int, int]]:
    return [
        ("regions", len(world.layout.regions), 3),
        ("terrain", len(world.terrain.features), 4),
        ("water", len(world.water.bodies), 3),
        ("biomes", len(world.biomes.zones), 4),
        ("flora", len(world.flora.species), 5),
        ("fauna", len(world.fauna.species), 5),
        ("interactions", len(world.interactions.edges), 4),
        ("biome_weather", len(world.weather.biome_weather), 3),
        ("seasons", len(world.seasons.cycle), 2),
        ("natural_events", len(world.natural_events.events), 2),
        ("dynamics", len(world.simulation.dynamics), 2),
    ]


def score(world: World, report: ValidationReport | None = None) -> MetricResult:
    """Score how fully every schema section is populated."""
    sections = _section_targets(world)
    fractions = [min(1.0, count / target) for _, count, target in sections]
    value = clamp(100.0 * sum(fractions) / len(fractions))
    sparse = [label for (label, count, target), f in zip(sections, fractions) if f < 0.5]
    detail = "all sections well populated" if not sparse else f"sparse: {', '.join(sparse)}"
    return MetricResult(name=NAME, score=value, weight=WEIGHT, detail=detail)
