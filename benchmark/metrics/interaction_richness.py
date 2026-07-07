"""Metric: interaction richness.

Judges the ecological web itself: how many interactions exist relative to the
species count, how many distinct interaction *types* are present, and whether
the ecologically important relations (predation, herbivory, pollination,
migration, decomposition, symbiosis) are represented.
"""

from __future__ import annotations

from ..models import InteractionType, World
from ..results import MetricResult, ValidationReport
from ._common import clamp

NAME = "interaction_richness"
WEIGHT = 0.10

#: Relations a thriving ecosystem is expected to exhibit.
_KEY_RELATIONS = {
    InteractionType.PREDATION,
    InteractionType.HERBIVORY,
    InteractionType.POLLINATION,
    InteractionType.MIGRATION,
    InteractionType.DECOMPOSITION,
    InteractionType.SYMBIOSIS,
}


def score(world: World, report: ValidationReport | None = None) -> MetricResult:
    """Score the density and diversity of ecological interactions."""
    edges = world.interactions.edges
    species = len(world.flora.species) + len(world.fauna.species)
    if species == 0:
        return MetricResult(name=NAME, score=0.0, weight=WEIGHT, detail="no species")

    present_types = {e.type for e in edges}

    # Density: edges per species, saturating at ~1 edge/species.
    density = clamp(100.0 * min(1.0, len(edges) / species))
    # Type diversity: distinct interaction types out of the enum space.
    type_diversity = 100.0 * len(present_types) / len(InteractionType)
    # Key-relation coverage: fraction of the ecologically important relations.
    key_coverage = 100.0 * len(present_types & _KEY_RELATIONS) / len(_KEY_RELATIONS)

    value = clamp(0.35 * density + 0.30 * type_diversity + 0.35 * key_coverage)
    detail = f"{len(edges)} edges, {len(present_types)} types, {len(present_types & _KEY_RELATIONS)}/{len(_KEY_RELATIONS)} key relations"
    return MetricResult(name=NAME, score=value, weight=WEIGHT, detail=detail)
