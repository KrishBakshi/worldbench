"""Metric: biodiversity.

Blends taxonomic and functional diversity: how varied the flora categories,
fauna categories, trophic roles, and biome types are, plus how many trophic
levels the food web sustains. A monoculture or a two-species world scores low;
a balanced, multi-trophic ecosystem scores high.
"""

from __future__ import annotations

import networkx as nx

from ..models import World, food_web
from ..results import MetricResult, ValidationReport
from ._common import clamp, diversity_score

NAME = "biodiversity"
WEIGHT = 0.10


def _trophic_depth(world: World) -> int:
    """Longest consumer->producer chain in the food web (0 if empty/cyclic)."""
    web = food_web(world)
    if web.number_of_nodes() == 0:
        return 0
    if not nx.is_directed_acyclic_graph(web):
        return 0
    return nx.dag_longest_path_length(web)


def score(world: World, report: ValidationReport | None = None) -> MetricResult:
    """Score taxonomic and functional biodiversity."""
    flora_div = diversity_score(
        (f.category.value for f in world.flora.species), richness_target=8
    )
    fauna_div = diversity_score(
        (a.category.value for a in world.fauna.species), richness_target=8
    )
    role_div = diversity_score(
        (a.trophic_role.value for a in world.fauna.species), richness_target=6
    )
    biome_div = diversity_score(
        (z.type.value for z in world.biomes.zones), richness_target=8
    )

    depth = _trophic_depth(world)
    depth_score = clamp(100.0 * min(1.0, depth / 3.0))  # 3+ levels = full marks

    value = clamp(
        0.25 * flora_div + 0.25 * fauna_div + 0.20 * role_div + 0.15 * biome_div + 0.15 * depth_score
    )
    detail = (
        f"flora/fauna/role/biome diversity {flora_div:.0f}/{fauna_div:.0f}/"
        f"{role_div:.0f}/{biome_div:.0f}, trophic depth {depth}"
    )
    return MetricResult(name=NAME, score=value, weight=WEIGHT, detail=detail)
