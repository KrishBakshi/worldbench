"""Shared result types produced by validators and metrics.

These are deliberately dependency-light (only Pydantic) so that every part of
the pipeline — validators, metrics, the runner, and reporters — agrees on a
single stable contract for structured findings and scores.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Severity of a validation finding."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Finding(BaseModel):
    """A single structured observation emitted by a validator."""

    code: str = Field(description="Stable machine-readable finding code, e.g. 'HYD001'.")
    severity: Severity
    message: str = Field(description="Human-readable explanation of the finding.")
    entity_id: str | None = Field(
        default=None, description="Id of the entity the finding concerns, if any."
    )
    path: str | None = Field(
        default=None, description="Dotted schema path the finding concerns, if any."
    )

    def __str__(self) -> str:  # pragma: no cover - display helper
        where = f" [{self.entity_id}]" if self.entity_id else ""
        return f"{self.severity.value.upper()} {self.code}{where}: {self.message}"


class ValidationResult(BaseModel):
    """The outcome of running a single validator against a world."""

    validator: str = Field(description="Name of the validator that produced this result.")
    passed: bool = Field(description="True when no ERROR-severity findings were raised.")
    findings: list[Finding] = Field(default_factory=list)
    checks_run: int = Field(default=0, description="Number of individual checks performed.")
    checks_passed: int = Field(default=0, description="Number of checks that passed.")

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.WARNING]

    @property
    def pass_rate(self) -> float:
        """Fraction of checks that passed (1.0 when no checks were run)."""
        return 1.0 if self.checks_run == 0 else self.checks_passed / self.checks_run

    @classmethod
    def build(cls, validator: str, findings: list[Finding], checks_run: int) -> "ValidationResult":
        """Assemble a result, deriving ``passed`` and ``checks_passed``."""
        errors = [f for f in findings if f.severity is Severity.ERROR]
        return cls(
            validator=validator,
            passed=not errors,
            findings=findings,
            checks_run=checks_run,
            checks_passed=max(0, checks_run - len(errors)),
        )


class ValidationReport(BaseModel):
    """Aggregated results from every validator."""

    results: list[ValidationResult] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def all_findings(self) -> list[Finding]:
        return [f for r in self.results for f in r.findings]

    def error_count(self) -> int:
        return sum(len(r.errors) for r in self.results)

    def warning_count(self) -> int:
        return sum(len(r.warnings) for r in self.results)


class MetricResult(BaseModel):
    """A single named metric score on a 0-100 scale."""

    name: str
    score: float = Field(ge=0.0, le=100.0, description="Metric score in [0, 100].")
    weight: float = Field(ge=0.0, description="Weight applied in the overall composite.")
    detail: str = Field(default="", description="Short explanation of how the score arose.")

    @property
    def weighted(self) -> float:
        return self.score * self.weight


class ScoreReport(BaseModel):
    """The complete weighted scorecard for a world, out of 100."""

    metrics: list[MetricResult] = Field(default_factory=list)
    overall: float = Field(ge=0.0, le=100.0, description="Weighted composite score out of 100.")

    def get(self, name: str) -> MetricResult | None:
        return next((m for m in self.metrics if m.name == name), None)
