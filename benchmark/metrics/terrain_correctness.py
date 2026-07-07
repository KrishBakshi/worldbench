"""Metric: terrain correctness.

Checks that landforms are internally coherent: peaks sit above bases, elevated
landform classes really are higher than lowland ones, volcanoes declare an
activity state, ``connected_to`` references resolve, and any sparse
elevation samples do not contradict the features that contain them.
"""

from __future__ import annotations

from ..models import TerrainType, World, build_world_graph
from ..results import MetricResult, ValidationReport
from ._common import ratio_score

NAME = "terrain_correctness"
WEIGHT = 0.10

#: Landform classes expected to stand above the world's lowlands.
_ELEVATED = {
    TerrainType.MOUNTAIN,
    TerrainType.MOUNTAIN_RANGE,
    TerrainType.PLATEAU,
    TerrainType.MESA,
    TerrainType.VOLCANO,
    TerrainType.GLACIER,
}
_LOWLAND = {TerrainType.PLAIN, TerrainType.BASIN, TerrainType.VALLEY}


def score(world: World, report: ValidationReport | None = None) -> MetricResult:
    """Score the geometric and categorical coherence of terrain."""
    features = world.terrain.features
    checks = 0
    passed = 0
    problems: list[str] = []

    ids = {f.id for f in features}

    # Highest lowland peak — elevated features should exceed it.
    lowland_ceiling = max(
        (f.peak_elevation for f in features if f.type in _LOWLAND), default=None
    )

    for f in features:
        checks += 1  # peak above base
        if f.peak_elevation >= f.base_elevation:
            passed += 1
        else:
            problems.append(f"{f.id} peak below base")

        checks += 1  # connected_to references resolve
        if all(ref in ids for ref in f.connected_to):
            passed += 1
        else:
            problems.append(f"{f.id} dangling connected_to")

        if f.type is TerrainType.VOLCANO:
            checks += 1
            if f.volcanic_activity is not None:
                passed += 1
            else:
                problems.append(f"{f.id} volcano missing activity")

        if f.type in _ELEVATED and lowland_ceiling is not None:
            checks += 1
            if f.peak_elevation >= lowland_ceiling:
                passed += 1
            else:
                problems.append(f"{f.id} not above lowlands")

    # Elevation samples should not wildly contradict a containing feature's band.
    for sample in world.terrain.elevation_samples:
        for f in features:
            fp = f.footprint
            if fp.min_x <= sample.position.x <= fp.max_x and fp.min_y <= sample.position.y <= fp.max_y:
                checks += 1
                if f.base_elevation - 1e-6 <= sample.elevation <= f.peak_elevation + 1e-6:
                    passed += 1
                else:
                    problems.append(f"sample at ({sample.position.x},{sample.position.y}) outside {f.id} band")
                break

    build_world_graph(world)  # exercised for connectivity side-effects / parity with validators
    value = ratio_score(passed, checks, floor=100.0)
    detail = "terrain coherent" if not problems else "; ".join(problems[:3])
    return MetricResult(name=NAME, score=value, weight=WEIGHT, detail=detail)
