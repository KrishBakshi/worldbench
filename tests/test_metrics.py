"""Tests for the WorldBench scoring metrics.

A rich, ecologically sound world fixture (:func:`good_world`) is scored to
confirm each metric rewards quality, and deliberately degraded variants confirm
each metric penalises the failure mode it is responsible for.
"""

from __future__ import annotations

import math

import pytest

from benchmark.metrics import (
    load_weights,
    score_biodiversity,
    score_completeness,
    score_creativity,
    score_ecological_correctness,
    score_hydrology_correctness,
    score_interaction_richness,
    score_schema_validity,
    score_spatial_coherence,
    score_terrain_correctness,
    score_world,
)
from benchmark.models import (
    Biome,
    Biomes,
    BiomeWeather,
    BoundingRegion,
    CardinalDirection,
    Coordinate2D,
    EcologicalInteraction,
    EdgeType,
    Fauna,
    FaunaSpecies,
    Flora,
    FloraSpecies,
    Interactions,
    LongTermDynamic,
    NaturalEvent,
    NaturalEvents,
    Region,
    Season,
    Seasons,
    Simulation,
    Terrain,
    TerrainFeature,
    WaterBody,
    WaterSystems,
    Weather,
    World,
    WorldLayout,
    WorldMetadata,
)


def _box(a: float, b: float, c: float, d: float) -> BoundingRegion:
    return BoundingRegion(min_x=a, min_y=b, max_x=c, max_y=d)


def good_world() -> World:
    """A varied, ecologically coherent world used as the positive fixture."""
    metadata = WorldMetadata(
        id="verdant_isle",
        name="The Verdant Isle",
        description="A temperate island of forest, plains, beach and coastal sea.",
        tags=["temperate", "coastal", "forest", "living", "balanced"],
    )
    layout = WorldLayout(
        topology="island",
        edge_type=EdgeType.OCEAN,
        bounds=_box(0, 0, 1000, 1000),
        sea_level=0.0,
        regions=[
            Region(
                id="r_north", name="Northern Highlands",
                description="Cool forested highlands above the plains.",
                footprint=_box(0, 600, 1000, 1000), direction=CardinalDirection.NORTH,
                adjacent_to=["r_central"],
            ),
            Region(
                id="r_central", name="Central Plains",
                description="Rolling grassland threaded by a river.",
                footprint=_box(0, 200, 1000, 600), direction=CardinalDirection.CENTER,
                adjacent_to=["r_north", "r_coast"],
            ),
            Region(
                id="r_coast", name="Southern Coast",
                description="Beaches giving way to a shallow coastal sea.",
                footprint=_box(0, 0, 1000, 200), direction=CardinalDirection.SOUTH,
                adjacent_to=["r_central"],
            ),
        ],
    )
    terrain = Terrain(
        features=[
            TerrainFeature(
                id="t_mountain", name="Frostpeak", type="mountain", region_id="r_north",
                footprint=_box(200, 700, 500, 950), base_elevation=200, peak_elevation=900,
                slope=0.8, description="A snow-capped peak feeding the island's rivers.",
            ),
            TerrainFeature(
                id="t_plain", name="Green Flats", type="plain", region_id="r_central",
                footprint=_box(0, 250, 1000, 550), base_elevation=50, peak_elevation=250,
                slope=0.1, description="Broad grassy lowland plains.",
            ),
            TerrainFeature(
                id="t_cliff", name="Saltwind Cliffs", type="cliff", region_id="r_coast",
                footprint=_box(0, 50, 1000, 200), base_elevation=-40, peak_elevation=100,
                slope=0.9, description="Weathered cliffs meeting the sea.",
            ),
        ],
    )
    water = WaterSystems(
        bodies=[
            WaterBody(
                id="w_river", name="Glass River", type="river", region_ids=["r_north", "r_central"],
                path=[Coordinate2D(x=350, y=850), Coordinate2D(x=400, y=300)],
                surface_elevation=850, mouth_elevation=100, source_ids=["t_mountain"],
                flows_to="w_lake", description="A cold river descending from Frostpeak.",
            ),
            WaterBody(
                id="w_lake", name="Mirror Lake", type="lake", region_ids=["r_central"],
                footprint=_box(380, 280, 460, 340), surface_elevation=100,
                flows_to="w_ocean", description="A still lake at the heart of the plains.",
            ),
            WaterBody(
                id="w_ocean", name="Turquoise Shallows", type="ocean", quality="salt",
                region_ids=["r_coast"], footprint=_box(0, 0, 1000, 120), surface_elevation=0,
                description="Warm shallow coastal water ringing the island.",
            ),
        ],
    )
    biomes = Biomes(
        zones=[
            Biome(
                id="b_forest", name="Highland Forest", type="temperate_forest",
                region_ids=["r_north"], temperature="temperate", moisture="humid",
                elevation_range=(200, 900), adjacent_to=["b_grassland"],
                terrain_feature_ids=["t_mountain"], water_body_ids=["w_river"],
                description="A dense emerald forest cloaking the highlands.",
            ),
            Biome(
                id="b_grassland", name="Central Grassland", type="grassland",
                region_ids=["r_central"], temperature="temperate", moisture="moderate",
                elevation_range=(50, 250), adjacent_to=["b_forest", "b_beach"],
                terrain_feature_ids=["t_plain"], water_body_ids=["w_river", "w_lake"],
                description="Open rolling grassland grazed by herds.",
            ),
            Biome(
                id="b_beach", name="Coral Beach", type="beach",
                region_ids=["r_coast"], temperature="warm", moisture="moderate",
                elevation_range=(0, 60), adjacent_to=["b_grassland", "b_marine"],
                terrain_feature_ids=["t_cliff"], water_body_ids=["w_ocean"],
                description="A bright sandy shore fringed with palms.",
            ),
            Biome(
                id="b_marine", name="Coastal Sea", type="coastal_ocean",
                region_ids=["r_coast"], temperature="warm", moisture="saturated",
                elevation_range=(-40, 0), adjacent_to=["b_beach"],
                water_body_ids=["w_ocean"],
                description="Sunlit shallows teeming with fish.",
            ),
        ]
    )
    flora = Flora(
        species=[
            FloraSpecies(id="fl_oak", name="Silver Oak", category="tree", biome_ids=["b_forest"],
                         pollination="wind", water_requirement=0.6, provides_food=True,
                         max_height=30, description="A towering hardwood bearing acorns."),
            FloraSpecies(id="fl_fern", name="Shade Fern", category="fern", biome_ids=["b_forest"],
                         pollination="spore", water_requirement=0.7, max_height=1.2,
                         description="Feathery ferns carpeting the forest floor."),
            FloraSpecies(id="fl_grass", name="Meadow Grass", category="grass",
                         biome_ids=["b_grassland"], pollination="wind", water_requirement=0.4,
                         provides_food=True, max_height=0.6, description="Tall waving meadow grass."),
            FloraSpecies(id="fl_flower", name="Blue Aster", category="flower",
                         biome_ids=["b_grassland"], pollination="insect", water_requirement=0.5,
                         provides_food=True, max_height=0.3, description="Nectar-rich blue wildflowers."),
            FloraSpecies(id="fl_palm", name="Shore Palm", category="tree", biome_ids=["b_beach"],
                         pollination="wind", water_requirement=0.5, max_height=15,
                         description="Salt-tolerant palms lining the beach."),
            FloraSpecies(id="fl_kelp", name="Ribbon Kelp", category="seagrass",
                         biome_ids=["b_marine"], pollination="water", water_requirement=1.0,
                         provides_food=True, max_height=6, description="Swaying kelp in the shallows."),
        ]
    )
    fauna = Fauna(
        species=[
            FaunaSpecies(id="fa_deer", name="Forest Deer", category="mammal",
                         trophic_role="herbivore", locomotion=["walking"],
                         biome_ids=["b_forest", "b_grassland"], diet_flora_ids=["fl_oak", "fl_grass"],
                         description="Graceful browsers of forest edge and plain."),
            FaunaSpecies(id="fa_rabbit", name="Meadow Hare", category="mammal",
                         trophic_role="herbivore", locomotion=["walking", "burrowing"],
                         biome_ids=["b_grassland"], diet_flora_ids=["fl_grass", "fl_flower"],
                         description="Quick grazers of the open grassland."),
            FaunaSpecies(id="fa_wolf", name="Grey Wolf", category="mammal",
                         trophic_role="carnivore", locomotion=["walking"], biome_ids=["b_forest"],
                         diet_fauna_ids=["fa_deer", "fa_rabbit"],
                         description="Pack hunters ranging the highland forest."),
            FaunaSpecies(id="fa_eagle", name="Isle Eagle", category="bird",
                         trophic_role="apex_predator", locomotion=["flying"],
                         biome_ids=["b_forest", "b_grassland"], diet_fauna_ids=["fa_rabbit"],
                         description="A soaring raptor commanding the skies."),
            FaunaSpecies(id="fa_bee", name="Golden Bee", category="insect",
                         trophic_role="pollinator", locomotion=["flying"], biome_ids=["b_grassland"],
                         diet_flora_ids=["fl_flower"], description="Industrious pollinators of the meadow."),
            FaunaSpecies(id="fa_crab", name="Sand Crab", category="crustacean",
                         trophic_role="herbivore", locomotion=["walking", "swimming"],
                         biome_ids=["b_beach", "b_marine"], diet_flora_ids=["fl_kelp"],
                         description="Scuttling grazers of the tidal shallows."),
            FaunaSpecies(id="fa_fish", name="Silver Fish", category="fish",
                         trophic_role="carnivore", locomotion=["swimming"], biome_ids=["b_marine"],
                         diet_fauna_ids=["fa_crab"], description="Darting predators of the shallows."),
        ]
    )
    interactions = Interactions(
        edges=[
            EcologicalInteraction(id="i_pred_wolf_deer", type="predation",
                                  source_id="fa_wolf", target_id="fa_deer", strength=0.8),
            EcologicalInteraction(id="i_herb_deer_oak", type="herbivory",
                                  source_id="fa_deer", target_id="fl_oak", strength=0.6),
            EcologicalInteraction(id="i_poll_bee_flower", type="pollination",
                                  source_id="fa_bee", target_id="fl_flower", strength=0.9),
            EcologicalInteraction(id="i_migr_eagle", type="migration",
                                  source_id="fa_eagle", target_id="b_grassland", seasonal=True),
            EcologicalInteraction(id="i_symb_crab_kelp", type="symbiosis",
                                  source_id="fa_crab", target_id="fl_kelp", strength=0.4),
            EcologicalInteraction(id="i_seed_eagle_oak", type="seed_dispersal",
                                  source_id="fa_eagle", target_id="fl_oak", strength=0.3),
        ]
    )
    weather = Weather(
        biome_weather=[
            BiomeWeather(biome_id="b_forest", avg_temperature=12, precipitation="rain",
                         annual_precipitation=1200, storm_frequency=0.2),
            BiomeWeather(biome_id="b_grassland", avg_temperature=18, precipitation="rain",
                         annual_precipitation=700, storm_frequency=0.1),
            BiomeWeather(biome_id="b_beach", avg_temperature=22, precipitation="rain",
                         annual_precipitation=900, storm_frequency=0.15),
            BiomeWeather(biome_id="b_marine", avg_temperature=19, precipitation="rain",
                         annual_precipitation=1000, storm_frequency=0.25),
        ]
    )
    seasons = Seasons(
        cycle=[
            Season(id="s_spring", name="Spring", order=0, length_fraction=0.25,
                   temperature_modifier=2, precipitation_modifier=1.2),
            Season(id="s_summer", name="Summer", order=1, length_fraction=0.25,
                   temperature_modifier=6, precipitation_modifier=0.8),
            Season(id="s_autumn", name="Autumn", order=2, length_fraction=0.25,
                   temperature_modifier=0, precipitation_modifier=1.0),
            Season(id="s_winter", name="Winter", order=3, length_fraction=0.25,
                   temperature_modifier=-6, precipitation_modifier=1.1),
        ]
    )
    natural_events = NaturalEvents(
        events=[
            NaturalEvent(id="e_flood", name="Spring Flood", type="flood", severity="moderate",
                         recurrence_years=3, affected_region_ids=["r_central"], triggers=["w_river"]),
            NaturalEvent(id="e_wildfire", name="Summer Wildfire", type="wildfire", severity="major",
                         recurrence_years=12, affected_biome_ids=["b_forest"]),
        ]
    )
    simulation = Simulation(
        stability_index=0.72,
        dynamics=[
            LongTermDynamic(id="d_predprey", name="Wolf-Deer Cycle", type="predator_prey_cycle",
                            period_years=8, involves_ids=["fa_wolf", "fa_deer"]),
            LongTermDynamic(id="d_migration", name="Eagle Migration", type="migration_cycle",
                            period_years=1, involves_ids=["fa_eagle", "b_grassland"]),
        ],
    )
    return World(
        metadata=metadata, layout=layout, terrain=terrain, water=water, biomes=biomes,
        flora=flora, fauna=fauna, interactions=interactions, weather=weather, seasons=seasons,
        natural_events=natural_events, simulation=simulation,
    )


@pytest.fixture()
def world() -> World:
    return good_world()


# --- per-metric range + positive-signal tests --------------------------------
ALL_METRICS = [
    score_schema_validity, score_completeness, score_terrain_correctness,
    score_hydrology_correctness, score_ecological_correctness, score_interaction_richness,
    score_spatial_coherence, score_biodiversity, score_creativity,
]


@pytest.mark.parametrize("fn", ALL_METRICS)
def test_metric_in_range(world: World, fn) -> None:
    result = fn(world)
    assert 0.0 <= result.score <= 100.0
    assert result.weight >= 0.0
    assert result.name


def test_good_world_scores_well(world: World) -> None:
    assert score_ecological_correctness(world).score >= 90
    assert score_hydrology_correctness(world).score >= 90
    assert score_terrain_correctness(world).score >= 90
    assert score_completeness(world).score >= 80
    assert score_spatial_coherence(world).score >= 80


def test_ecological_correctness_penalises_misplaced_flora(world: World) -> None:
    baseline = score_ecological_correctness(world).score
    broken = world.model_copy(deep=True)
    # A cactus placed in a temperate forest is ecologically wrong.
    broken.flora.species[0].category = "cactus"  # type: ignore[assignment]
    assert score_ecological_correctness(broken).score < baseline


def test_biodiversity_penalises_monoculture(world: World) -> None:
    baseline = score_biodiversity(world).score
    mono = world.model_copy(deep=True)
    for sp in mono.flora.species:
        sp.category = "grass"  # type: ignore[assignment]
    for sp in mono.fauna.species:
        sp.category = "mammal"  # type: ignore[assignment]
        sp.trophic_role = "herbivore"  # type: ignore[assignment]
        sp.diet_fauna_ids = []
    assert score_biodiversity(mono).score < baseline


def test_interaction_richness_penalises_single_relation(world: World) -> None:
    baseline = score_interaction_richness(world).score
    poor = world.model_copy(deep=True)
    poor.interactions.edges = [poor.interactions.edges[0]]  # only one predation edge
    assert score_interaction_richness(poor).score < baseline


def test_hydrology_penalises_missing_outlet(world: World) -> None:
    baseline = score_hydrology_correctness(world).score
    broken = world.model_copy(deep=True)
    # A flowing river that neither flows onward nor exits the world is stranded.
    broken.water.bodies[0].flows_to = None
    assert score_hydrology_correctness(broken).score < baseline


def test_completeness_penalises_sparse_world(world: World) -> None:
    baseline = score_completeness(world).score
    sparse = world.model_copy(deep=True)
    sparse.interactions.edges = []
    sparse.natural_events.events = []
    sparse.simulation.dynamics = []
    assert score_completeness(sparse).score < baseline


# --- composite ---------------------------------------------------------------
def test_score_world_composite(world: World) -> None:
    report = score_world(world)
    assert 0.0 <= report.overall <= 100.0
    assert len(report.metrics) == 9
    names = {m.name for m in report.metrics}
    assert names == {
        "schema_validity", "completeness", "terrain_correctness", "hydrology_correctness",
        "ecological_correctness", "interaction_richness", "spatial_coherence",
        "biodiversity", "creativity",
    }
    # A strong world should comfortably clear the midpoint.
    assert report.overall >= 70


def test_weights_sum_to_one() -> None:
    weights = load_weights()
    assert len(weights) == 9
    assert math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9)
