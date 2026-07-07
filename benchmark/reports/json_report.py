"""Render a run result as a structured JSON report."""

from __future__ import annotations

import json

from ..runner.runner import RunResult


def build_json_report(result: RunResult) -> dict:
    """Return a fully structured, JSON-serializable report for ``result``."""
    return {
        "summary": result.summary(),
        "validation": result.validation.model_dump(mode="json"),
        "metrics": result.score.model_dump(mode="json"),
        "logs": result.logs,
    }


def render_json(result: RunResult, *, indent: int = 2) -> str:
    """Return the JSON report as a formatted string."""
    return json.dumps(build_json_report(result), indent=indent)
