"""Metric: spatial coherence.

Uses the world graph to judge whether the map hangs together: regions form a
connected adjacency graph, biomes reference real regions, no region is
orphaned, and neighbouring biomes are knowledge-base plausible neighbours
rather than jarring, incompatible transitions.
"""

from __future__ import annotations

import networkx as nx

from ..models import World
from ..results import MetricResult, ValidationReport
from ..knowledge import load_knowledge
from ._common import clamp

NAME = "spatial_coherence"
WEIGHT = 0.10


def score(world: World, report: ValidationReport | None = None) -> MetricResult:
    """Score the spatial connectivity and adjacency plausibility of the world."""
    kg = load_knowledge()
    regions = world.layout.regions
    region_ids = {r.id for r in regions}
    biomes = {z.id: z for z in world.biomes.zones}

    problems: list[str] = []

    # Region adjacency connectivity (undirected view).
    radj = nx.Graph()
    radj.add_nodes_from(region_ids)
    for r in regions:
        for other in r.adjacent_to:
            if other in region_ids:
                radj.add_edge(r.id, other)
    if radj.number_of_nodes() <= 1:
        connectivity = 100.0
    else:
        components = nx.number_connected_components(radj)
        connectivity = clamp(100.0 * (1.0 / components))
        if components > 1:
            problems.append(f"{components} disconnected region clusters")

    # Biomes reference real regions.
    ref_checks = ref_ok = 0
    for z in world.biomes.zones:
        for rid in z.region_ids:
            ref_checks += 1
            if rid in region_ids:
                ref_ok += 1
            else:
                problems.append(f"{z.id} references missing region {rid}")
    ref_score = 100.0 if ref_checks == 0 else 100.0 * ref_ok / ref_checks

    # Biome neighbour plausibility.
    adj_checks = adj_ok = 0
    for z in world.biomes.zones:
        for other_id in z.adjacent_to:
            other = biomes.get(other_id)
            if other is None:
                continue
            adj_checks += 1
            if kg.may_be_adjacent(z.type.value, other.type.value):
                adj_ok += 1
            else:
                problems.append(f"{z.type.value}|{other.type.value} implausible neighbours")
    adj_score = 100.0 if adj_checks == 0 else 100.0 * adj_ok / adj_checks

    value = clamp(0.4 * connectivity + 0.3 * ref_score + 0.3 * adj_score)
    detail = "spatially coherent" if not problems else "; ".join(problems[:3])
    return MetricResult(name=NAME, score=value, weight=WEIGHT, detail=detail)
