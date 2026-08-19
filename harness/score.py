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


# A hovering ocean is not a sea. WC003/WC004 still count inland biomes, but
# Coastal Delta / Ocean (delta) points are removed when still water has no bed
# or never holds as a body of water.
SEA_GATE_IDS = frozenset({"water_physics", "water_bed"})
SEA_BIOME_ID = "delta"
CONTENT_PREFIXES = ("WC003_", "WC004_")


def _wc000_lost_ids(records: dict[str, dict]) -> set[str]:
    for key, rec in records.items():
        if "WC000_" not in key or not isinstance(rec, dict):
            continue
        details = rec.get("details") or {}
        missing = details.get("missing")
        if isinstance(missing, list):
            return {str(item) for item in missing}
        card = details.get("scorecard") or {}
        lost = card.get("lost") or []
        return {str(row.get("id")) for row in lost if isinstance(row, dict)}
    return set()


def _sea_biome_score(rec: dict) -> float:
    details = rec.get("details") or {}
    card = details.get("scorecard") if isinstance(details, dict) else None
    biomes = (card or {}).get("biomes") if isinstance(card, dict) else None
    biome = (biomes or {}).get(SEA_BIOME_ID) if isinstance(biomes, dict) else None
    if not isinstance(biome, dict):
        return 0.0
    return float(biome.get("score") or 0)


def apply_island_gate(records: dict[str, dict]) -> bool:
    """Drop ocean/sea (delta) points on WC003/WC004 when water has no seafloor."""
    gated = bool(_wc000_lost_ids(records) & SEA_GATE_IDS)
    for key, rec in records.items():
        if not isinstance(rec, dict) or not key.startswith(CONTENT_PREFIXES):
            continue
        if "probe_score" not in rec:
            rec["probe_score"] = rec.get("score") or 0
            rec["probe_reason"] = rec.get("reason") or ""
            rec["probe_passed"] = rec.get("passed")
        if gated:
            deduct = _sea_biome_score(rec)
            max_score = rec.get("max_score") or 0
            rec["score"] = round(max(0.0, float(rec["probe_score"]) - deduct), 2)
            rec["passed"] = False
            rec["gated"] = True
            rec["sea_deduction"] = deduct
            probe_reason = str(rec.get("probe_reason") or "")
            if "Scored " in probe_reason and "/" in probe_reason:
                rec["reason"] = f"Scored {rec['score']}/{probe_reason.split('/', 1)[1]}"
            else:
                rec["reason"] = probe_reason or f"Scored {rec['score']}/{max_score}"
            details = rec.get("details")
            if isinstance(details, dict):
                details["score"] = rec["score"]
        else:
            rec["score"] = rec["probe_score"]
            rec["reason"] = rec.get("probe_reason") or ""
            rec["passed"] = rec.get("probe_passed")
            rec.pop("gated", None)
            rec.pop("sea_deduction", None)
            details = rec.get("details")
            if isinstance(details, dict):
                details["score"] = rec["score"]
    return gated


def score_records(records: dict[str, dict]) -> dict:
    """Sum already-scored harness records (dicts with score/max_score/passed)."""
    gated = apply_island_gate(records)
    total_score = sum(float(r.get("score") or 0) for r in records.values())
    total_max = sum(float(r.get("max_score") or 0) for r in records.values())
    out = {
        "total_score": total_score,
        "total_max_score": total_max,
        "pct": total_score / total_max if total_max else 0.0,
        "island_gate": gated,
    }
    return out
