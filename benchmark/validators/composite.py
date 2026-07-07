"""Composite validation: run every validator and aggregate the results."""

from __future__ import annotations

from ..models import World
from ..results import ValidationReport
from . import (
    biome,
    constraint,
    ecology,
    fauna,
    flora,
    hydrology,
    interaction,
    schema_validator,
    simulation,
    topology,
    weather,
)

#: Validators run in dependency order: schema first (structure), then spatial,
#: hydrological, ecological, and finally scope/constraint checks.
VALIDATORS = [
    schema_validator,
    topology,
    hydrology,
    biome,
    flora,
    fauna,
    ecology,
    interaction,
    weather,
    simulation,
    constraint,
]


def validate_world(world: World, constraints: dict | None = None) -> ValidationReport:
    """Run all validators against ``world`` and aggregate their results.

    ``constraints`` is an optional dict from a task's ``constraints.yaml`` that
    the constraint validator uses for per-task quantitative checks.
    """
    results = []
    for module in VALIDATORS:
        if module is constraint:
            results.append(module.validate(world, constraints))
        else:
            results.append(module.validate(world))
    return ValidationReport(results=results)
