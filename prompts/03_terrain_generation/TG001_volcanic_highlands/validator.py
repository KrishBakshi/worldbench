"""Task validator for TG001_volcanic_highlands.

Composes the shared WorldBench engine (terrain — coherent elevations (peaks above bases), connected landforms, and a genuine active volcano.) and adds any
task-specific checks. Exposes ``validate(world) -> ValidationResult``.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from benchmark.models import World
from benchmark.results import Finding, Severity, ValidationResult
from benchmark.validators import validate_world

CONSTRAINTS = yaml.safe_load((Path(__file__).parent / "constraints.yaml").read_text())


def validate(world: World) -> ValidationResult:
    """Validate ``world`` for this task and return a single merged result."""
    report = validate_world(world, constraints=CONSTRAINTS)
    findings = list(report.all_findings)
    checks_run = sum(r.checks_run for r in report.results)

    extra: list[Finding] = []

    # Task-specific: require at least one active or erupting volcano.
    from benchmark.models import TerrainType, VolcanicActivity
    active = [
        f for f in world.terrain.features
        if f.type is TerrainType.VOLCANO
        and f.volcanic_activity in (VolcanicActivity.ACTIVE, VolcanicActivity.ERUPTING)
    ]
    if not active:
        extra.append(Finding(
            code="TG001", severity=Severity.ERROR,
            message="task requires at least one active or erupting volcano",
        ))


    findings.extend(extra)
    errors = [f for f in findings if f.severity is Severity.ERROR]
    return ValidationResult(
        validator="TG001_volcanic_highlands",
        passed=not errors,
        findings=findings,
        checks_run=checks_run + len(extra),
        checks_passed=checks_run + len(extra) - len(errors),
    )
