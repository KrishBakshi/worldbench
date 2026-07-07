"""Task validator for WS001_river_to_sea.

Composes the shared WorldBench engine (hydrology — a connected flow network where every flowing body runs downhill and terminates properly.) and adds any
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

    # Task-specific: require at least one river that terminates in a terminal
    # body or exits the world edge.
    from benchmark.models import WaterBodyType
    rivers = [b for b in world.water.bodies if b.type is WaterBodyType.RIVER]
    terminating = [r for r in rivers if r.flows_to or r.exits_world]
    if rivers and not terminating:
        extra.append(Finding(
            code="WS001", severity=Severity.ERROR,
            message="task requires at least one river that terminates properly",
        ))


    findings.extend(extra)
    errors = [f for f in findings if f.severity is Severity.ERROR]
    return ValidationResult(
        validator="WS001_river_to_sea",
        passed=not errors,
        findings=findings,
        checks_run=checks_run + len(extra),
        checks_passed=checks_run + len(extra) - len(errors),
    )
