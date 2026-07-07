"""Metric: schema validity.

Measures how cleanly the world conforms to the WorldBench schema and its
structural validators. When a :class:`ValidationReport` is supplied the score is
driven by the pass-rates of the schema/topology/hydrology validators; without
one, it falls back to confirming the world round-trips through the Pydantic
model.
"""

from __future__ import annotations

from ..models import World
from ..results import MetricResult, ValidationReport
from ._common import clamp

NAME = "schema_validity"
WEIGHT = 0.15

#: Validators whose pass-rates dominate this metric when a report is available.
_STRUCTURAL = {"schema", "schema_validator", "topology", "hydrology"}


def score(world: World, report: ValidationReport | None = None) -> MetricResult:
    """Score structural conformance of ``world`` on a 0-100 scale."""
    if report is not None and report.results:
        structural = [r for r in report.results if r.validator.lower() in _STRUCTURAL]
        judged = structural or report.results
        pass_rate = sum(r.pass_rate for r in judged) / len(judged)
        errors = sum(len(r.errors) for r in judged)
        value = clamp(100.0 * pass_rate - 5.0 * errors)
        detail = f"{errors} structural error(s) across {len(judged)} validator(s)"
        return MetricResult(name=NAME, score=value, weight=WEIGHT, detail=detail)

    # No report: confirm the model round-trips through validation.
    try:
        World.model_validate(world.model_dump())
        return MetricResult(
            name=NAME, score=100.0, weight=WEIGHT, detail="world round-trips through schema"
        )
    except Exception as exc:  # pragma: no cover - defensive; a World is already valid
        return MetricResult(name=NAME, score=0.0, weight=WEIGHT, detail=f"round-trip failed: {exc}")
