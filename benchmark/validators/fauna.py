"""Fauna validation: habitat feasibility, diet completeness, locomotion sanity."""

from __future__ import annotations

from ..knowledge import load_knowledge
from ..models import Locomotion, TrophicRole, World
from ..results import Severity, ValidationResult
from .base import FindingCollector

NAME = "fauna"
PREFIX = "FAU"

_NEED_PLANT_DIET = {TrophicRole.HERBIVORE, TrophicRole.OMNIVORE}
_NEED_ANIMAL_DIET = {TrophicRole.CARNIVORE, TrophicRole.OMNIVORE, TrophicRole.APEX_PREDATOR}
_AQUATIC_BIOMES = {"deep_ocean", "coral_reef"}
_AQUATIC_LOCOMOTION = {Locomotion.SWIMMING, Locomotion.AMPHIBIOUS}


def validate(world: World) -> ValidationResult:
    c = FindingCollector(NAME, PREFIX)
    kg = load_knowledge()
    biomes = {b.id: b for b in world.biomes.zones}
    flora_ids = {f.id for f in world.flora.species}
    fauna_ids = {f.id for f in world.fauna.species}

    for fauna in world.fauna.species:
        for bid in fauna.biome_ids:
            biome = biomes.get(bid)
            if not c.check(
                biome is not None,
                f"fauna '{fauna.id}' references unknown biome '{bid}'",
                entity_id=fauna.id,
            ):
                continue
            c.check(
                kg.supports_fauna(biome.type.value, fauna.category.value),
                f"fauna '{fauna.id}' ({fauna.category.value}) cannot live in biome "
                f"'{bid}' ({biome.type.value})",
                entity_id=fauna.id,
            )
            if biome.type.value in _AQUATIC_BIOMES:
                c.check(
                    bool(set(fauna.locomotion) & _AQUATIC_LOCOMOTION),
                    f"fauna '{fauna.id}' inhabits aquatic biome '{bid}' but cannot "
                    "swim or move amphibiously",
                    severity=Severity.WARNING,
                    entity_id=fauna.id,
                )

        # Diet references resolve.
        for fid in fauna.diet_flora_ids:
            c.check(
                fid in flora_ids,
                f"fauna '{fauna.id}' eats unknown flora '{fid}'",
                entity_id=fauna.id,
            )
        for fid in fauna.diet_fauna_ids:
            c.check(
                fid in fauna_ids,
                f"fauna '{fauna.id}' preys on unknown fauna '{fid}'",
                entity_id=fauna.id,
            )

        # Diet completeness by trophic role.
        if fauna.trophic_role in _NEED_PLANT_DIET:
            c.check(
                bool(fauna.diet_flora_ids),
                f"fauna '{fauna.id}' is a {fauna.trophic_role.value} but eats no flora",
                entity_id=fauna.id,
            )
        if fauna.trophic_role in _NEED_ANIMAL_DIET:
            c.check(
                bool(fauna.diet_fauna_ids),
                f"fauna '{fauna.id}' is a {fauna.trophic_role.value} but preys on nothing",
                entity_id=fauna.id,
            )
        c.check(
            fauna.id not in fauna.diet_fauna_ids,
            f"fauna '{fauna.id}' preys on itself",
            entity_id=fauna.id,
        )

    return c.result()
