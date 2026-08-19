"""Wraps a check call so it becomes an auditable LangSmith run: the full
per-item breakdown plus the score, not just pass/fail.

This is a harness concern. Direct `uv run python tests/WC00N/...` does
not import this module. @traceable no-ops unless LANGSMITH_TRACING=true
and LANGSMITH_API_KEY are set (loaded from .env via python-dotenv).
"""

from __future__ import annotations

import inspect
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from langsmith import traceable

from harness.score import score_result


def _to_jsonable(result) -> dict:
    if is_dataclass(result) and not isinstance(result, type):
        return asdict(result)
    if isinstance(result, dict):
        return dict(result)
    return {
        "passed": getattr(result, "passed", False),
        "reason": getattr(result, "reason", ""),
        "details": getattr(result, "details", {}) or {},
    }


def run_audited_check(
    check_fn: Callable,
    html_path: str,
    *,
    test_id: str,
    model: str,
    out_dir: Path | str | None = None,
) -> dict:
    """Runs check_fn. Traced as "<test_id>::<check_fn.__name__>".

    Passes out_dir when the check accepts it (WC002+ write artifacts).
    Direct test CLIs never go through here, so they never need LangSmith.
    """

    @traceable(
        name=f"{test_id}::{check_fn.__name__}",
        run_type="tool",
        metadata={"model": model, "test_id": test_id},
    )
    def _traced(path: str) -> dict:
        kwargs = {}
        sig = inspect.signature(check_fn)
        if out_dir is not None and "out_dir" in sig.parameters:
            kwargs["out_dir"] = Path(out_dir)
        result = check_fn(path, **kwargs)
        score = score_result(result)
        payload = _to_jsonable(result)
        payload["score"] = score.score
        payload["max_score"] = score.max_score
        return payload

    return _traced(html_path)
