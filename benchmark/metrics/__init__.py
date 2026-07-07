"""WorldBench scoring metrics.

Nine metrics, each a pure function ``score(world, report=None) -> MetricResult``
on a 0-100 scale, combined by :func:`score_world` into a weighted
:class:`~benchmark.results.ScoreReport` out of 100.
"""

from __future__ import annotations

from ..results import MetricResult, ScoreReport
from .biodiversity import score as score_biodiversity
from .completeness import score as score_completeness
from .creativity import score as score_creativity
from .ecological_correctness import score as score_ecological_correctness
from .hydrology_correctness import score as score_hydrology_correctness
from .interaction_richness import score as score_interaction_richness
from .overall import METRICS, load_weights, score_world
from .schema_validity import score as score_schema_validity
from .spatial_coherence import score as score_spatial_coherence
from .terrain_correctness import score as score_terrain_correctness

__all__ = [
    "MetricResult",
    "ScoreReport",
    "METRICS",
    "load_weights",
    "score_world",
    "score_schema_validity",
    "score_completeness",
    "score_terrain_correctness",
    "score_hydrology_correctness",
    "score_ecological_correctness",
    "score_interaction_richness",
    "score_spatial_coherence",
    "score_biodiversity",
    "score_creativity",
]
