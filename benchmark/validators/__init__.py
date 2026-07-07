"""WorldBench validators.

Each validator module exposes ``validate(world) -> ValidationResult``. The
:func:`validate_world` aggregate runs them all and returns a
:class:`ValidationReport`. Import the aggregate from here rather than reaching
into submodules so call sites stay stable.
"""

from __future__ import annotations

from ..results import Finding, Severity, ValidationReport, ValidationResult
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
from .composite import VALIDATORS, validate_world
from .schema_validator import validate_dict

__all__ = [
    "validate_world",
    "validate_dict",
    "VALIDATORS",
    "ValidationReport",
    "ValidationResult",
    "Finding",
    "Severity",
    "schema_validator",
    "topology",
    "hydrology",
    "biome",
    "flora",
    "fauna",
    "ecology",
    "interaction",
    "weather",
    "simulation",
    "constraint",
]
