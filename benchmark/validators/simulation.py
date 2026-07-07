"""Simulation validation: long-term dynamics must reference real ecology."""

from __future__ import annotations

from ..models import DynamicType, World
from ..models.fauna import TrophicRole
from ..results import Severity, ValidationResult
from .base import FindingCollector

NAME = "simulation"
PREFIX = "SIM"

_PREDATORS = {TrophicRole.CARNIVORE, TrophicRole.OMNIVORE, TrophicRole.APEX_PREDATOR}


def validate(world: World) -> ValidationResult:
    c = FindingCollector(NAME, PREFIX)
    all_ids = world.all_ids()
    fauna = {f.id: f for f in world.fauna.species}

    has_predation = any(f.trophic_role in _PREDATORS and f.diet_fauna_ids
                        for f in world.fauna.species) or any(
        e.type.value == "predation" for e in world.interactions.edges
    )
    has_migration = any(
        e.type.value == "migration" for e in world.interactions.edges
    )

    for dyn in world.simulation.dynamics:
        for iid in dyn.involves_ids:
            c.check(
                iid in all_ids,
                f"dynamic '{dyn.id}' references unknown id '{iid}'",
                entity_id=dyn.id,
            )
        if dyn.type is DynamicType.PREDATOR_PREY_CYCLE:
            c.check(
                has_predation,
                f"dynamic '{dyn.id}' is a predator-prey cycle but the world has no "
                "predation relationship",
                entity_id=dyn.id,
            )
        if dyn.type is DynamicType.MIGRATION_CYCLE:
            involved_fauna = [i for i in dyn.involves_ids if i in fauna]
            c.check(
                has_migration or bool(involved_fauna),
                f"dynamic '{dyn.id}' is a migration cycle but references no migratory "
                "fauna or migration interaction",
                severity=Severity.WARNING,
                entity_id=dyn.id,
            )

    if not world.simulation.dynamics:
        c.check(True, "no long-term dynamics declared")

    return c.result()
