"""Turns a check's CheckResult into a score. Generic across any test's
content check, not biome-specific — but built to match how
tests/WC001_trying_all_the_biomes/biome_check.py already reports itself:
one point per item found (e.g. one biome), no point for each missing one,
out of however many items that check looks for.

A check earns per-item scoring by putting `score`/`max_score` straight in
its CheckResult.details (as has_all_biomes does). Any check that doesn't
falls back to a plain 1/0 pass-fail score, so this still works for
checks that are genuinely all-or-nothing (e.g. checks/structural.py).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Score:
    score: int
    max_score: int
    passed: bool
    reason: str

    @property
    def pct(self) -> float:
        return self.score / self.max_score if self.max_score else 0.0


def score_result(result) -> Score:
    """`result` is any object with .passed, .reason, .details (a CheckResult
    from checks/structural.py or a test's own check script — both share
    that shape, so this doesn't need to import either)."""
    details = result.details or {}
    if "score" in details and "max_score" in details:
        score, max_score = details["score"], details["max_score"]
    else:
        score, max_score = (1, 1) if result.passed else (0, 1)

    return Score(score=score, max_score=max_score, passed=result.passed, reason=result.reason)


def score_report(results: dict[str, object]) -> dict:
    """Aggregate several named CheckResults (e.g. {"has_all_biomes": result})
    for one test's output into a report.json-shaped dict."""
    scored = {name: score_result(r) for name, r in results.items()}
    total_score = sum(s.score for s in scored.values())
    total_max = sum(s.max_score for s in scored.values())
    return {
        "checks": {
            name: {"score": s.score, "max_score": s.max_score, "passed": s.passed, "reason": s.reason}
            for name, s in scored.items()
        },
        "total_score": total_score,
        "total_max_score": total_max,
        "pct": total_score / total_max if total_max else 0.0,
    }


def score_records(records: dict[str, dict]) -> dict:
    """Sum already-scored harness records (dicts with score/max_score/passed)."""
    total_score = sum(float(r.get("score") or 0) for r in records.values())
    total_max = sum(float(r.get("max_score") or 0) for r in records.values())
    return {
        "total_score": total_score,
        "total_max_score": total_max,
        "pct": total_score / total_max if total_max else 0.0,
    }
