"""Metric: ecological correctness.

The heart of WorldBench. Scores whether flora and fauna are placed in biomes
that can actually sustain them (per the knowledge base), whether the biome's
climate admits each species, and whether diets are trophically sensible.
"""

from __future__ import annotations

from ..models import TrophicRole, World
from ..results import MetricResult, ValidationReport
from ..knowledge import load_knowledge
from ._common import ratio_score

NAME = "ecological_correctness"
WEIGHT = 0.20

_HERBIVOROUS = {TrophicRole.HERBIVORE, TrophicRole.OMNIVORE}
_PREDATORY = {TrophicRole.CARNIVORE, TrophicRole.OMNIVORE, TrophicRole.APEX_PREDATOR}


def score(world: World, report: ValidationReport | None = None) -> MetricResult:
    """Score the ecological realism of species placement and diet."""
    kg = load_knowledge()
    biomes = {z.id: z for z in world.biomes.zones}
    checks = 0
    passed = 0
    problems: list[str] = []

    # Flora placement + climate.
    for f in world.flora.species:
        for bid in f.biome_ids:
            biome = biomes.get(bid)
            if biome is None:
                continue
            checks += 1
            if kg.supports_flora(biome.type.value, f.category.value):
                passed += 1
            else:
                problems.append(f"{f.id} cannot grow in {biome.type.value}")
            checks += 1
            if kg.allows_temperature(biome.type.value, biome.temperature.value):
                passed += 1
            else:
                problems.append(f"{biome.id} climate rejects itself")

    # Fauna placement.
    for a in world.fauna.species:
        for bid in a.biome_ids:
            biome = biomes.get(bid)
            if biome is None:
                continue
            checks += 1
            if kg.supports_fauna(biome.type.value, a.category.value):
                passed += 1
            else:
                problems.append(f"{a.id} cannot live in {biome.type.value}")

        # Diet realism.
        if a.trophic_role in _HERBIVOROUS:
            checks += 1
            if a.diet_flora_ids:
                passed += 1
            else:
                problems.append(f"{a.id} herbivore with no plant diet")
        if a.trophic_role in _PREDATORY:
            checks += 1
            if a.diet_fauna_ids:
                passed += 1
            else:
                problems.append(f"{a.id} predator with no prey")

    value = ratio_score(passed, checks, floor=0.0)
    detail = "ecology realistic" if not problems else "; ".join(problems[:3])
    return MetricResult(name=NAME, score=value, weight=WEIGHT, detail=detail)
