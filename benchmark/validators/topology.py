"""Topology validation: spatial bounds, region adjacency, and edge coherence."""

from __future__ import annotations

from ..models import EdgeType, World, WorldTopology
from ..models.common import BoundingRegion
from ..results import Severity, ValidationResult
from .base import FindingCollector

NAME = "topology"
PREFIX = "TOP"

_FLOATING = {WorldTopology.FLOATING_ISLAND, WorldTopology.FLOATING_ARCHIPELAGO}
_FLOATING_EDGES = {EdgeType.VOID, EdgeType.CLIFF}


def _within(inner: BoundingRegion, outer: BoundingRegion) -> bool:
    return (
        inner.min_x >= outer.min_x
        and inner.max_x <= outer.max_x
        and inner.min_y >= outer.min_y
        and inner.max_y <= outer.max_y
    )


def validate(world: World) -> ValidationResult:
    c = FindingCollector(NAME, PREFIX)
    bounds = world.layout.bounds
    region_ids = {r.id for r in world.layout.regions}

    # Edge behavior must match topology.
    if world.layout.topology in _FLOATING:
        c.check(
            world.layout.edge_type in _FLOATING_EDGES,
            f"floating topology '{world.layout.topology.value}' must use a void or "
            f"cliff edge, not '{world.layout.edge_type.value}'",
            path="layout.edge_type",
        )
    else:
        c.check(
            world.layout.edge_type != EdgeType.VOID,
            f"grounded topology '{world.layout.topology.value}' should not use a "
            "void edge",
            severity=Severity.WARNING,
            path="layout.edge_type",
        )

    # Region footprints inside world bounds; adjacency symmetric and resolvable.
    for region in world.layout.regions:
        c.check(
            _within(region.footprint, bounds),
            f"region '{region.id}' footprint extends outside world bounds",
            entity_id=region.id,
        )
        for other in region.adjacent_to:
            if not c.check(
                other in region_ids,
                f"region '{region.id}' is adjacent to unknown region '{other}'",
                entity_id=region.id,
            ):
                continue
            back = next(r for r in world.layout.regions if r.id == other)
            c.check(
                region.id in back.adjacent_to,
                f"region adjacency not symmetric: '{region.id}' -> '{other}' but not "
                "the reverse",
                severity=Severity.WARNING,
                entity_id=region.id,
            )

    # Terrain footprints inside bounds; connectivity + region references resolve.
    terrain_ids = {f.id for f in world.terrain.features}
    for feature in world.terrain.features:
        c.check(
            _within(feature.footprint, bounds),
            f"terrain '{feature.id}' footprint extends outside world bounds",
            entity_id=feature.id,
        )
        c.check(
            feature.region_id in region_ids,
            f"terrain '{feature.id}' references unknown region '{feature.region_id}'",
            entity_id=feature.id,
        )
        for other in feature.connected_to:
            c.check(
                other in terrain_ids,
                f"terrain '{feature.id}' connected to unknown feature '{other}'",
                severity=Severity.WARNING,
                entity_id=feature.id,
            )

    return c.result()
