"""Ecology validation: food-web integrity and trophic structure.

Operates on the trophic subgraph (:func:`food_web`): consumers point at what
they consume, so producers (flora) are sinks and apex predators are sources. A
healthy world has an acyclic web, at least one producer feeding it, prey for
every predator, and non-trivial trophic depth.
"""

from __future__ import annotations

import networkx as nx

from ..models import TrophicRole, World, food_web
from ..results import Severity, ValidationResult
from .base import FindingCollector

NAME = "ecology"
PREFIX = "ECO"

_PREDATORS = {TrophicRole.CARNIVORE, TrophicRole.OMNIVORE, TrophicRole.APEX_PREDATOR}


def validate(world: World) -> ValidationResult:
    c = FindingCollector(NAME, PREFIX)
    web = food_web(world)
    fauna = {f.id: f for f in world.fauna.species}

    # The trophic web must be acyclic (no A-eats-B-eats-A loops).
    cycle_free = True
    try:
        cycle = nx.find_cycle(web, orientation="original")
        cycle_free = False
        path = " -> ".join(edge[0] for edge in cycle)
        c.check(False, f"impossible trophic cycle in food web: {path}")
    except nx.NetworkXNoCycle:
        c.check(True, "food web is acyclic")

    # At least one producer (flora node) must feed the web.
    flora_nodes = [n for n, d in web.nodes(data=True) if d.get("kind") == "flora"]
    fed_flora = [n for n in flora_nodes if web.in_degree(n) > 0]
    c.check(
        bool(fed_flora) or not world.fauna.species,
        "no flora is consumed by any fauna; the food web has no producer base",
    )

    # Every predator must reach some prey.
    for fid, f in fauna.items():
        if f.trophic_role in _PREDATORS:
            has_prey = web.out_degree(fid) > 0 if fid in web else False
            c.check(
                has_prey,
                f"predator '{fid}' ({f.trophic_role.value}) has no reachable prey",
                entity_id=fid,
            )

    # Trophic depth: the longest consumer chain should exceed a single link.
    if cycle_free and web.number_of_edges() > 0:
        depth = nx.dag_longest_path_length(web)
        c.check(
            depth >= 2,
            f"food web is trophically shallow (max chain length {depth}); expected a "
            "producer -> herbivore -> predator structure",
            severity=Severity.WARNING,
        )

    # Species with no ecological connections at all are suspicious.
    for fid in fauna:
        if fid in web and web.degree(fid) == 0:
            c.check(
                False,
                f"fauna '{fid}' participates in no feeding relationship",
                severity=Severity.WARNING,
                entity_id=fid,
            )

    return c.result()
