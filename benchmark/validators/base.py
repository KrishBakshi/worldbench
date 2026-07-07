"""Shared plumbing for WorldBench validators.

Every validator is a callable ``(World) -> ValidationResult``. Modules expose a
``validate`` function, a ``NAME`` string, and a unique finding-code ``PREFIX``.
The helpers here keep the individual validators terse: they accumulate
:class:`Finding` objects and a running check count, then hand off to
:meth:`ValidationResult.build`, which derives pass/fail from the presence of
error-severity findings.
"""

from __future__ import annotations

from typing import Callable

from ..models import World
from ..results import Finding, Severity, ValidationResult

#: A validator is any callable turning a world into a structured result.
ValidatorFn = Callable[[World], ValidationResult]


class FindingCollector:
    """Accumulates findings and counts checks for a single validator run.

    Call :meth:`check` once per logical assertion. When ``ok`` is False a
    finding of the given severity is recorded; the total number of checks is
    tracked regardless so the resulting :class:`ValidationResult` can report a
    meaningful pass rate.
    """

    def __init__(self, name: str, prefix: str):
        self.name = name
        self.prefix = prefix
        self.findings: list[Finding] = []
        self.checks_run = 0
        self._code_counter = 0

    def _next_code(self) -> str:
        self._code_counter += 1
        return f"{self.prefix}{self._code_counter:03d}"

    def check(
        self,
        ok: bool,
        message: str,
        *,
        severity: Severity = Severity.ERROR,
        entity_id: str | None = None,
        path: str | None = None,
    ) -> bool:
        """Record one check. Emits a finding when ``ok`` is falsy."""
        self.checks_run += 1
        if not ok:
            self.findings.append(
                Finding(
                    code=self._next_code(),
                    severity=severity,
                    message=message,
                    entity_id=entity_id,
                    path=path,
                )
            )
        return bool(ok)

    def error(self, message: str, *, entity_id: str | None = None, path: str | None = None) -> None:
        """Record an unconditional error finding (counts as a failed check)."""
        self.check(False, message, severity=Severity.ERROR, entity_id=entity_id, path=path)

    def warn(self, message: str, *, entity_id: str | None = None, path: str | None = None) -> None:
        """Record an unconditional warning finding (counts as a check)."""
        self.check(False, message, severity=Severity.WARNING, entity_id=entity_id, path=path)

    def result(self) -> ValidationResult:
        """Assemble the final :class:`ValidationResult`."""
        return ValidationResult.build(self.name, self.findings, self.checks_run)


def unknown_ids(referenced: list[str], known: set[str]) -> list[str]:
    """Return the subset of ``referenced`` ids that are not in ``known``."""
    return [r for r in referenced if r not in known]
