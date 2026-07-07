"""Shared helpers for metric computation.

Metrics are pure functions of a :class:`~benchmark.models.World` (plus an
optional pre-computed :class:`~benchmark.results.ValidationReport`). They never
mutate the world and never raise on structurally-valid-but-ecologically-poor
input — a bad world simply earns a low score.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    """Clamp ``value`` into the closed interval ``[low, high]``."""
    return max(low, min(high, value))


def ratio_score(passed: int, total: int, *, floor: float = 0.0) -> float:
    """Turn a passed/total ratio into a 0-100 score.

    When ``total`` is zero the metric has nothing to judge and returns ``floor``
    (defaults to 0.0) so that empty sections cannot inflate a score.
    """
    if total <= 0:
        return floor
    return clamp(100.0 * passed / total)


def shannon_evenness(items: Iterable[str]) -> float:
    """Return Shannon evenness (0-1) over the category labels in ``items``.

    Evenness is the Shannon entropy normalized by ``log(k)`` where ``k`` is the
    number of distinct categories, so a perfectly even spread scores 1.0 and a
    monoculture scores 0.0. An empty or single-category input scores 0.0.
    """
    counts = Counter(items)
    total = sum(counts.values())
    k = len(counts)
    if total == 0 or k <= 1:
        return 0.0
    entropy = -sum((c / total) * math.log(c / total) for c in counts.values())
    return entropy / math.log(k)


def diversity_score(items: Iterable[str], *, richness_target: int) -> float:
    """Blend category *richness* and *evenness* into a 0-100 diversity score.

    ``richness_target`` is the number of distinct categories considered "full
    marks" for richness; evenness rewards a balanced rather than skewed spread.
    """
    labels = list(items)
    if not labels:
        return 0.0
    richness = min(1.0, len(set(labels)) / max(1, richness_target))
    evenness = shannon_evenness(labels)
    return clamp(100.0 * (0.6 * richness + 0.4 * evenness))
