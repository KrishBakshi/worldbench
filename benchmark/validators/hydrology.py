"""Hydrology validation: flow topology, downhill flow, and termination.

Water is modeled as a directed flow graph. This validator confirms the graph is
acyclic, every flowing body eventually reaches a terminal body (or exits a
floating world's edge), water never climbs uphill, and each flow edge is
ecologically plausible per the knowledge base.
"""

from __future__ import annotations

from ..knowledge import load_knowledge
from ..models import FLOWING_TYPES, TERMINAL_TYPES, World
from ..models.water import WaterBody
from ..results import Severity, ValidationResult
from .base import FindingCollector

NAME = "hydrology"
PREFIX = "HYD"


def validate(world: World) -> ValidationResult:
    c = FindingCollector(NAME, PREFIX)
    kg = load_knowledge()
    bodies = {b.id: b for b in world.water.bodies}
    region_ids = {r.id for r in world.layout.regions}
    all_ids = world.all_ids()

    for body in world.water.bodies:
        _validate_body(c, body, bodies, region_ids, all_ids, kg)

    _validate_flow_graph(c, world, bodies)
    return c.result()


def _validate_body(c, body: WaterBody, bodies, region_ids, all_ids, kg) -> None:
    for rid in body.region_ids:
        c.check(
            rid in region_ids,
            f"water '{body.id}' references unknown region '{rid}'",
            entity_id=body.id,
        )
    for sid in body.source_ids:
        c.check(
            sid in all_ids,
            f"water '{body.id}' has unknown source '{sid}'",
            entity_id=body.id,
        )

    is_flowing = body.type in FLOWING_TYPES
    if is_flowing:
        c.check(
            body.flows_to is not None or body.exits_world,
            f"flowing water '{body.id}' ({body.type.value}) must declare flows_to "
            "or exits_world",
            entity_id=body.id,
        )

    if body.flows_to is not None:
        target = bodies.get(body.flows_to)
        if c.check(
            target is not None,
            f"water '{body.id}' flows to unknown body '{body.flows_to}'",
            entity_id=body.id,
        ):
            # Downhill: a body's surface must not sit below its target's surface.
            c.check(
                body.surface_elevation >= target.surface_elevation - 1e-6,
                f"water '{body.id}' flows uphill into '{target.id}' "
                f"({body.surface_elevation} -> {target.surface_elevation})",
                entity_id=body.id,
            )
            c.check(
                kg.may_flow_to(body.type.value, target.type.value),
                f"water '{body.id}' ({body.type.value}) flowing into "
                f"'{target.id}' ({target.type.value}) is ecologically implausible",
                severity=Severity.WARNING,
                entity_id=body.id,
            )

    if body.mouth_elevation is not None:
        c.check(
            body.mouth_elevation <= body.surface_elevation + 1e-6,
            f"water '{body.id}' mouth is above its source (uphill flow)",
            entity_id=body.id,
        )


def _validate_flow_graph(c, world: World, bodies) -> None:
    """Walk each flow chain: detect cycles and confirm termination."""
    for start in world.water.bodies:
        if start.type not in FLOWING_TYPES:
            continue
        seen: list[str] = []
        current = start
        terminated = False
        while True:
            if current.id in seen:
                c.check(
                    False,
                    f"water flow cycle detected: {' -> '.join(seen + [current.id])}",
                    entity_id=start.id,
                )
                break
            seen.append(current.id)
            if current.exits_world:
                terminated = True
                break
            if current.flows_to is None:
                break
            nxt = bodies.get(current.flows_to)
            if nxt is None:
                break  # unresolved reference already reported per-body
            if nxt.type in TERMINAL_TYPES:
                terminated = True
                break
            current = nxt
        c.check(
            terminated,
            f"flow chain from '{start.id}' does not reach a terminal body or world edge",
            entity_id=start.id,
        )
