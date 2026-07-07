"""Build a :class:`networkx.DiGraph` view of a :class:`World`.

Validators and metrics traverse this graph rather than re-walking the nested
Pydantic tree. Node ids are entity ids; every node carries a ``kind`` attribute
(``region``, ``terrain``, ``water``, ``biome``, ``flora``, ``fauna``, ``event``,
``dynamic``) and edges carry a ``relation`` label (``adjacent``, ``flows_to``,
``contains``, ``inhabits``, ``grows_in``, ``preys_on``, ``pollinates``,
``triggers`` ...).
"""

from __future__ import annotations

import networkx as nx

from .interactions import InteractionType
from .world import World

_INTERACTION_RELATION = {
    InteractionType.PREDATION: "preys_on",
    InteractionType.HERBIVORY: "eats",
    InteractionType.POLLINATION: "pollinates",
    InteractionType.SEED_DISPERSAL: "disperses",
    InteractionType.MIGRATION: "migrates_to",
    InteractionType.SYMBIOSIS: "symbiotic_with",
    InteractionType.PARASITISM: "parasitizes",
    InteractionType.COMPETITION: "competes_with",
    InteractionType.DECOMPOSITION: "decomposes",
    InteractionType.NESTING: "nests_in",
    InteractionType.CAMOUFLAGE_HOST: "camouflaged_by",
}


def build_world_graph(world: World) -> nx.DiGraph:
    """Construct the entity relationship graph for ``world``."""
    g: nx.DiGraph = nx.DiGraph()

    for region in world.layout.regions:
        g.add_node(region.id, kind="region", name=region.name)
    for feature in world.terrain.features:
        g.add_node(feature.id, kind="terrain", name=feature.name, type=feature.type.value)
        g.add_edge(feature.region_id, feature.id, relation="contains")
    for body in world.water.bodies:
        g.add_node(body.id, kind="water", name=body.name, type=body.type.value)
    for biome in world.biomes.zones:
        g.add_node(biome.id, kind="biome", name=biome.name, type=biome.type.value)
    for flora in world.flora.species:
        g.add_node(flora.id, kind="flora", name=flora.name, category=flora.category.value)
    for fauna in world.fauna.species:
        g.add_node(
            fauna.id,
            kind="fauna",
            name=fauna.name,
            category=fauna.category.value,
            trophic_role=fauna.trophic_role.value,
        )
    for event in world.natural_events.events:
        g.add_node(event.id, kind="event", name=event.name, type=event.type.value)
    for dynamic in world.simulation.dynamics:
        g.add_node(dynamic.id, kind="dynamic", name=dynamic.name, type=dynamic.type.value)

    # Region adjacency (undirected relationship encoded as two directed edges).
    for region in world.layout.regions:
        for other in region.adjacent_to:
            g.add_edge(region.id, other, relation="adjacent")

    # Terrain connectivity.
    for feature in world.terrain.features:
        for other in feature.connected_to:
            g.add_edge(feature.id, other, relation="connected")

    # Hydrology flow.
    for body in world.water.bodies:
        if body.flows_to:
            g.add_edge(body.id, body.flows_to, relation="flows_to")
        for source in body.source_ids:
            g.add_edge(source, body.id, relation="feeds")

    # Biome adjacency + membership.
    for biome in world.biomes.zones:
        for other in biome.adjacent_to:
            g.add_edge(biome.id, other, relation="adjacent")
        for tid in biome.terrain_feature_ids:
            g.add_edge(biome.id, tid, relation="includes_terrain")
        for wid in biome.water_body_ids:
            g.add_edge(biome.id, wid, relation="includes_water")

    # Flora habitat + food.
    for flora in world.flora.species:
        for bid in flora.biome_ids:
            g.add_edge(flora.id, bid, relation="grows_in")

    # Fauna habitat + diet.
    for fauna in world.fauna.species:
        for bid in fauna.biome_ids:
            g.add_edge(fauna.id, bid, relation="inhabits")
        for fid in fauna.diet_flora_ids:
            g.add_edge(fauna.id, fid, relation="eats")
        for tid in fauna.diet_fauna_ids:
            g.add_edge(fauna.id, tid, relation="preys_on")

    # Explicit interaction edges.
    for edge in world.interactions.edges:
        g.add_edge(
            edge.source_id,
            edge.target_id,
            relation=_INTERACTION_RELATION.get(edge.type, edge.type.value),
            interaction_id=edge.id,
            strength=edge.strength,
        )

    # Event triggers.
    for event in world.natural_events.events:
        for trigger in event.triggers:
            g.add_edge(trigger, event.id, relation="triggers")

    return g


def food_web(world: World) -> nx.DiGraph:
    """Return only the trophic subgraph (predation + herbivory edges).

    Direction points from consumer to what it consumes, so trophic depth is the
    longest path from an apex predator down to a producer.
    """
    g = build_world_graph(world)
    trophic = nx.DiGraph()
    for node, data in g.nodes(data=True):
        if data.get("kind") in {"flora", "fauna"}:
            trophic.add_node(node, **data)
    for u, v, data in g.edges(data=True):
        if data.get("relation") in {"eats", "preys_on"}:
            if u in trophic and v in trophic:
                trophic.add_edge(u, v, **data)
    return trophic
