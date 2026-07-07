"""Metric: hydrology correctness.

Scores the world's flow graph: flowing bodies should terminate in a terminal
body or exit the world, water must not run uphill, declared sources should
resolve, and each flow edge should be knowledge-base plausible.
"""

from __future__ import annotations

from ..models import FLOWING_TYPES, World
from ..results import MetricResult, ValidationReport
from ..knowledge import load_knowledge
from ._common import ratio_score

NAME = "hydrology_correctness"
WEIGHT = 0.10


def score(world: World, report: ValidationReport | None = None) -> MetricResult:
    """Score the physical and ecological plausibility of water flow."""
    kg = load_knowledge()
    bodies = {b.id: b for b in world.water.bodies}
    all_ids = world.all_ids()
    checks = 0
    passed = 0
    problems: list[str] = []

    for b in world.water.bodies:
        # Sources must resolve.
        for src in b.source_ids:
            checks += 1
            if src in all_ids:
                passed += 1
            else:
                problems.append(f"{b.id} dangling source {src}")

        if b.type in FLOWING_TYPES:
            # Must terminate somehow.
            checks += 1
            if b.exits_world or b.flows_to is not None:
                passed += 1
            else:
                problems.append(f"{b.id} flowing but no outlet")

            # No uphill flow.
            if b.mouth_elevation is not None:
                checks += 1
                if b.mouth_elevation <= b.surface_elevation:
                    passed += 1
                else:
                    problems.append(f"{b.id} flows uphill")

            # Downstream target resolves and is knowledge-plausible.
            if b.flows_to is not None:
                checks += 1
                target = bodies.get(b.flows_to)
                if target is None:
                    problems.append(f"{b.id} flows to missing {b.flows_to}")
                elif kg.may_flow_to(b.type.value, target.type.value):
                    passed += 1
                else:
                    problems.append(f"{b.id}->{target.id} implausible flow")

    value = ratio_score(passed, checks, floor=100.0)
    detail = "hydrology sound" if not problems else "; ".join(problems[:3])
    return MetricResult(name=NAME, score=value, weight=WEIGHT, detail=detail)
