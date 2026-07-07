"""Flora validation: habitat feasibility and pollinator coherence."""

from __future__ import annotations

from ..knowledge import load_knowledge
from ..models import PollinationMode, World
from ..models.fauna import TrophicRole
from ..results import Severity, ValidationResult
from .base import FindingCollector

NAME = "flora"
PREFIX = "FLO"

_ANIMAL_POLLINATION = {PollinationMode.INSECT, PollinationMode.BIRD, PollinationMode.BAT}


def validate(world: World) -> ValidationResult:
    c = FindingCollector(NAME, PREFIX)
    kg = load_knowledge()
    biomes = {b.id: b for b in world.biomes.zones}

    has_pollinator = any(
        f.trophic_role is TrophicRole.POLLINATOR for f in world.fauna.species
    ) or any(e.type.value == "pollination" for e in world.interactions.edges)

    for flora in world.flora.species:
        for bid in flora.biome_ids:
            biome = biomes.get(bid)
            if not c.check(
                biome is not None,
                f"flora '{flora.id}' references unknown biome '{bid}'",
                entity_id=flora.id,
            ):
                continue
            c.check(
                kg.supports_flora(biome.type.value, flora.category.value),
                f"flora '{flora.id}' ({flora.category.value}) cannot grow in biome "
                f"'{bid}' ({biome.type.value})",
                entity_id=flora.id,
            )

        if flora.pollination in _ANIMAL_POLLINATION:
            c.check(
                has_pollinator,
                f"flora '{flora.id}' relies on {flora.pollination.value} pollination "
                "but the world has no pollinator fauna or pollination interaction",
                severity=Severity.WARNING,
                entity_id=flora.id,
            )

    return c.result()
