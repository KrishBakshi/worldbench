"""Wraps a check call so it becomes an auditable LangSmith run: the full
per-item breakdown (e.g. which biomes were found vs. missing, by which
matched keyword) plus the score, not just the pass/fail bit. Point is:
open a run in LangSmith — whether the check passed or failed — and know
for a fact which item(s), if any, were absent and what the score was,
without re-running anything.

Safe to call with no LangSmith configured: @traceable no-ops (runs the
function normally, records nothing) unless LANGSMITH_TRACING=true and
LANGSMITH_API_KEY are set (see .env.example) — so this can be used from
scripts/dry_run_regex_patterns.py and later harness/validate.py either way.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Callable

from langsmith import traceable

from harness.score import score_result


def _to_jsonable(result) -> dict:
    return asdict(result) if is_dataclass(result) else dict(result)


def run_audited_check(check_fn: Callable, html_path: str, *, test_id: str, model: str) -> dict:
    """Runs check_fn(html_path). Traced to LangSmith as a run named
    "<test_id>::<check_fn.__name__>", tagged with which model/test this
    was, and recording the check's full CheckResult (passed, reason,
    details — including found/missing) plus its score/max_score as the
    run's output. Returns that same dict whether or not tracing is active,
    so callers always get the auditable record even without LangSmith
    configured — LangSmith is just where it additionally gets shipped."""

    @traceable(
        name=f"{test_id}::{check_fn.__name__}",
        run_type="tool",
        metadata={"model": model, "test_id": test_id},
    )
    def _traced(path: str) -> dict:
        result = check_fn(path)
        score = score_result(result)
        return {**_to_jsonable(result), "score": score.score, "max_score": score.max_score}

    return _traced(html_path)
