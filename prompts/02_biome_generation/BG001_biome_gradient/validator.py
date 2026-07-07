"""Task validator for BG001_biome_gradient.

Composes the shared WorldBench engine (biome placement — each biome's temperature and moisture must satisfy its ecological requirements.) and adds any
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
    # No task-specific checks beyond the shared engine.

    findings.extend(extra)
    errors = [f for f in findings if f.severity is Severity.ERROR]
    return ValidationResult(
        validator="BG001_biome_gradient",
        passed=not errors,
        findings=findings,
        checks_run=checks_run + len(extra),
        checks_passed=checks_run + len(extra) - len(errors),
    )
