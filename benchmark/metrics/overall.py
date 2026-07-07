"""Composite scoring: combine the nine WorldBench metrics into one score.

``score_world`` runs every registered metric, applies the weights declared in
``weights.yaml``, and returns a :class:`ScoreReport` whose ``overall`` is the
weighted sum on a 0-100 scale. An optional pre-computed
:class:`ValidationReport` is threaded through to metrics that can use it (chiefly
:mod:`schema_validity`).
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

import yaml

from ..models import World
from ..results import MetricResult, ScoreReport, ValidationReport
from . import (
    biodiversity,
    completeness,
    creativity,
    ecological_correctness,
    hydrology_correctness,
    interaction_richness,
    schema_validity,
    spatial_coherence,
    terrain_correctness,
)

WEIGHTS_PATH = Path(__file__).parent / "weights.yaml"

#: Ordered registry of (name, scoring function). The report preserves this order.
MetricFn = Callable[[World, ValidationReport | None], MetricResult]
METRICS: list[tuple[str, MetricFn]] = [
    (schema_validity.NAME, schema_validity.score),
    (completeness.NAME, completeness.score),
    (terrain_correctness.NAME, terrain_correctness.score),
    (hydrology_correctness.NAME, hydrology_correctness.score),
    (ecological_correctness.NAME, ecological_correctness.score),
    (interaction_richness.NAME, interaction_richness.score),
    (spatial_coherence.NAME, spatial_coherence.score),
    (biodiversity.NAME, biodiversity.score),
    (creativity.NAME, creativity.score),
]


@lru_cache(maxsize=1)
def load_weights() -> dict[str, float]:
    """Load and cache the metric weights from ``weights.yaml``."""
    data = yaml.safe_load(WEIGHTS_PATH.read_text(encoding="utf-8"))
    return {str(k): float(v) for k, v in data.items()}


def score_world(world: World, report: ValidationReport | None = None) -> ScoreReport:
    """Score ``world`` across all metrics and return a weighted :class:`ScoreReport`."""
    weights = load_weights()
    results: list[MetricResult] = []
    for name, fn in METRICS:
        result = fn(world, report)
        # Authoritative weight comes from weights.yaml, overriding module defaults.
        result.weight = weights.get(name, result.weight)
        results.append(result)

    weight_total = sum(r.weight for r in results) or 1.0
    overall = sum(r.score * r.weight for r in results) / weight_total
    return ScoreReport(metrics=results, overall=round(max(0.0, min(100.0, overall)), 2))
