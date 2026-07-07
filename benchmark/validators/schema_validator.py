"""Schema validation: does the document conform to the WorldBench schema?

This is the first gate: raw LLM output is validated as a :class:`World` and its
declared ``schema_version`` is checked against the version this package
implements. Downstream validators assume a structurally-valid world, so the
runner calls :func:`validate_dict` on raw JSON before constructing a ``World``.
"""

from __future__ import annotations

from pydantic import ValidationError

from ..models import SCHEMA_VERSION, World
from ..results import Finding, Severity, ValidationResult
from .base import FindingCollector

NAME = "schema"
PREFIX = "SCH"


def validate_dict(data: dict) -> ValidationResult:
    """Validate a raw dict (e.g. parsed LLM JSON) against the World schema."""
    c = FindingCollector(NAME, PREFIX)
    try:
        world = World.model_validate(data)
    except ValidationError as exc:
        # One finding per structural error, so authors see every problem at once.
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"])
            c.check(False, f"{err['msg']}", path=loc)
        # Ensure at least one check is recorded even for an empty error list.
        c.checks_run = max(c.checks_run, 1)
        return c.result()
    return _validate_world(world, c)


def validate(world: World) -> ValidationResult:
    """Validate an already-parsed :class:`World`."""
    return _validate_world(world, FindingCollector(NAME, PREFIX))


def _validate_world(world: World, c: FindingCollector) -> ValidationResult:
    c.check(
        world.metadata.schema_version == SCHEMA_VERSION,
        f"metadata.schema_version {world.metadata.schema_version!r} does not match "
        f"the implemented schema version {SCHEMA_VERSION!r}",
        severity=Severity.WARNING,
        path="metadata.schema_version",
    )
    # Re-dump/reload round-trip guards against models that pass validation but
    # fail serialization (e.g. non-finite floats).
    try:
        World.model_validate_json(world.to_json())
        c.check(True, "world round-trips through JSON serialization")
    except (ValidationError, ValueError) as exc:  # pragma: no cover - defensive
        c.check(False, f"world failed JSON round-trip: {exc}")
    return c.result()
