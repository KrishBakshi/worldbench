"""The canonical valid WorldBench world used by the mock adapter and tests.

``sample_world()`` builds *The Verdant Expanse* — a floating island echoing the
project's founding world description (``prompts/overview.md``): snow peaks in the
north grading through highlands, forest, central grasslands, desert, and a
volcanic wasteland, ringed by wetlands, beaches, and a coastal sea that spills
off the island's cliff edges into the void.

It is constructed programmatically through the Pydantic models so it is
guaranteed schema-valid, and it is designed to satisfy every validator and score
well across every metric. Keeping one canonical example in code (rather than a
checked-in JSON blob) means it stays in lock-step with the schema.
"""

from __future__ import annotations

from functools import lru_cache

from .models import (
    Biome,
    Biomes,
    BiomeType,
    BoundingRegion,
    CardinalDirection,
    Coordinate2D,
    EcologicalInteraction,
    EdgeType,
    EventType,
    Fauna,
    FaunaCategory,
    FaunaSpecies,
    Flora,
    FloraCategory,
    FloraSpecies,
    InteractionType,
    Interactions,
    Locomotion,
    LongTermDynamic,
    MoistureLevel,
    NaturalEvent,
    NaturalEvents,
    PollinationMode,
    PrecipitationType,
    Rarity,
    Region,
    Season,
    Seasons,
    Simulation,
    TemperatureBand,
    Terrain,
    TerrainFeature,
    TerrainType,
    TrophicRole,
    VolcanicActivity,
    WaterBody,
    WaterBodyType,
    WaterQuality,
    WaterSystems,
    Weather,
    BiomeWeather,
    WindPattern,
    World,
    WorldLayout,
    WorldMetadata,
    WorldTopology,
)
from .models.simulation import DynamicType


def _box(min_x: float, min_y: float, max_x: float, max_y: float) -> BoundingRegion:
    return BoundingRegion(min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y)


def _metadata() -> WorldMetadata:
    return WorldMetadata(
        id="world_verdant_expanse",
        name="The Verdant Expanse",
        description=(
            "A vast floating island suspended in an empty void. Snow-capped peaks "
            "in the north feed glass-clear rivers that wind south through forest and "
            "grassland before pooling in a mirror lake and spilling into a coastal "
            "sea that cascades off the island's cliff edges. A dormant belt of "
            "volcanic wasteland smolders to the west, while wetlands and pale beaches "
            "soften the southern shore."
        ),
        tags=["floating", "island", "temperate", "volcanic", "self_contained"],
        seed=104729,
    )


def _layout() -> WorldLayout:
    regions = [
        Region(
            id="r_north_peaks",
            name="Frostspire Range",
            description="The island's high northern spine of snow and stone.",
            footprint=_box(300, 750, 700, 1000),
            direction=CardinalDirection.NORTH,
            adjacent_to=["r_highland"],
        ),
        Region(
            id="r_highland",
            name="Windward Highlands",
            description="Rocky plateaus and river sources below the peaks.",
            footprint=_box(350, 550, 650, 750),
            direction=CardinalDirection.CENTER,
            adjacent_to=["r_north_peaks", "r_forest", "r_grassland"],
        ),
        Region(
            id="r_forest",
            name="Emerald Reach",
            description="Dense temperate forest on the eastern slopes.",
            footprint=_box(650, 400, 950, 750),
            direction=CardinalDirection.EAST,
            adjacent_to=["r_highland", "r_grassland", "r_coast"],
        ),
        Region(
            id="r_grassland",
            name="Central Plains",
            description="Rolling grasslands at the heart of the island.",
            footprint=_box(300, 300, 650, 550),
            direction=CardinalDirection.CENTER,
            adjacent_to=["r_highland", "r_forest", "r_desert", "r_wetland"],
        ),
        Region(
            id="r_desert",
            name="Ochre Flats",
            description="Arid sandstone flats in the southwest.",
            footprint=_box(50, 150, 350, 450),
            direction=CardinalDirection.SOUTHWEST,
            adjacent_to=["r_grassland", "r_volcano"],
        ),
        Region(
            id="r_volcano",
            name="Emberwaste",
            description="A basalt wasteland around a smoldering volcano.",
            footprint=_box(50, 400, 300, 650),
            direction=CardinalDirection.WEST,
            adjacent_to=["r_desert"],
        ),
        Region(
            id="r_wetland",
            name="Reedmere",
            description="Marshy lowlands along the southern shore.",
            footprint=_box(300, 100, 600, 300),
            direction=CardinalDirection.SOUTH,
            adjacent_to=["r_grassland", "r_coast"],
        ),
        Region(
            id="r_coast",
            name="Cliffshore",
            description="Beaches and coastal sea at the island's cliff edge.",
            footprint=_box(600, 50, 1000, 400),
            direction=CardinalDirection.SOUTHEAST,
            adjacent_to=["r_forest", "r_wetland"],
        ),
    ]
    return WorldLayout(
        topology=WorldTopology.FLOATING_ISLAND,
        edge_type=EdgeType.CLIFF,
        bounds=_box(0, 0, 1000, 1000),
        sea_level=120.0,
        regions=regions,
    )


def _terrain() -> Terrain:
    features = [
        TerrainFeature(
            id="t_frost_peaks", name="Frostspire Peaks", type=TerrainType.MOUNTAIN_RANGE,
            region_id="r_north_peaks", footprint=_box(320, 780, 680, 990),
            base_elevation=400.0, peak_elevation=900.0, slope=0.8,
            connected_to=["t_north_glacier"],
            description="Jagged alpine peaks cloaked in permanent snow.",
        ),
        TerrainFeature(
            id="t_north_glacier", name="Hollow Glacier", type=TerrainType.GLACIER,
            region_id="r_north_peaks", footprint=_box(400, 760, 600, 850),
            base_elevation=500.0, peak_elevation=850.0, slope=0.5,
            connected_to=["t_frost_peaks"],
            description="A slow river of ice feeding the meltwater streams.",
        ),
        TerrainFeature(
            id="t_highland_plateau", name="Windward Plateau", type=TerrainType.PLATEAU,
            region_id="r_highland", footprint=_box(360, 560, 640, 740),
            base_elevation=300.0, peak_elevation=500.0, slope=0.3,
        ),
        TerrainFeature(
            id="t_forest_hills", name="Emerald Hills", type=TerrainType.HILL,
            region_id="r_forest", footprint=_box(660, 420, 940, 740),
            base_elevation=150.0, peak_elevation=350.0, slope=0.4,
        ),
        TerrainFeature(
            id="t_central_plain", name="Heartfield", type=TerrainType.PLAIN,
            region_id="r_grassland", footprint=_box(310, 310, 640, 540),
            base_elevation=130.0, peak_elevation=190.0, slope=0.1,
        ),
        TerrainFeature(
            id="t_desert_mesa", name="Ochre Mesa", type=TerrainType.MESA,
            region_id="r_desert", footprint=_box(60, 160, 340, 440),
            base_elevation=150.0, peak_elevation=400.0, slope=0.6,
        ),
        TerrainFeature(
            id="t_ember_volcano", name="Mount Ember", type=TerrainType.VOLCANO,
            region_id="r_volcano", footprint=_box(80, 420, 280, 640),
            base_elevation=200.0, peak_elevation=750.0, slope=0.7,
            volcanic_activity=VolcanicActivity.ACTIVE,
            description="An active cone venting ash and feeding hot springs.",
        ),
        TerrainFeature(
            id="t_coastal_cliffs", name="Cliffshore Wall", type=TerrainType.CLIFF,
            region_id="r_coast", footprint=_box(620, 60, 980, 380),
            base_elevation=120.0, peak_elevation=300.0, slope=0.95,
        ),
        TerrainFeature(
            id="t_wetland_basin", name="Reedmere Basin", type=TerrainType.BASIN,
            region_id="r_wetland", footprint=_box(310, 110, 590, 290),
            base_elevation=110.0, peak_elevation=140.0, slope=0.05,
        ),
    ]
    samples = [
        {"position": Coordinate2D(x=500, y=880), "elevation": 820.0},
        {"position": Coordinate2D(x=500, y=650), "elevation": 400.0},
        {"position": Coordinate2D(x=470, y=420), "elevation": 190.0},
        {"position": Coordinate2D(x=450, y=200), "elevation": 130.0},
        {"position": Coordinate2D(x=800, y=200), "elevation": 120.0},
    ]
    return Terrain.model_validate({"features": features, "elevation_samples": samples})


def _water() -> WaterSystems:
    bodies = [
        WaterBody(
            id="w_alpine_spring", name="Frostspire Spring", type=WaterBodyType.SPRING,
            quality=WaterQuality.GLACIAL, region_ids=["r_north_peaks"],
            surface_elevation=860.0, mouth_elevation=800.0,
            source_ids=["t_frost_peaks"], flows_to="w_glass_river",
            path=[Coordinate2D(x=520, y=880), Coordinate2D(x=510, y=820)],
        ),
        WaterBody(
            id="w_glacier_melt", name="Hollow Meltwater", type=WaterBodyType.GLACIER_MELT,
            quality=WaterQuality.GLACIAL, region_ids=["r_north_peaks"],
            surface_elevation=840.0, mouth_elevation=800.0,
            source_ids=["t_north_glacier"], flows_to="w_glass_river",
            path=[Coordinate2D(x=480, y=830), Coordinate2D(x=500, y=805)],
        ),
        WaterBody(
            id="w_glass_river", name="Glass River", type=WaterBodyType.RIVER,
            quality=WaterQuality.FRESH, region_ids=["r_north_peaks", "r_highland", "r_grassland"],
            surface_elevation=800.0, mouth_elevation=210.0,
            source_ids=["w_alpine_spring", "w_glacier_melt"], flows_to="w_mirror_lake",
            path=[Coordinate2D(x=500, y=800), Coordinate2D(x=500, y=650),
                  Coordinate2D(x=470, y=420), Coordinate2D(x=460, y=300)],
            description="The island's main river, widening as it descends.",
        ),
        WaterBody(
            id="w_cascade", name="Emerald Cascade", type=WaterBodyType.WATERFALL,
            quality=WaterQuality.FRESH, region_ids=["r_forest"],
            surface_elevation=450.0, mouth_elevation=210.0,
            source_ids=["w_glass_river"], flows_to="w_mirror_lake",
            path=[Coordinate2D(x=700, y=430), Coordinate2D(x=560, y=310)],
        ),
        WaterBody(
            id="w_mirror_lake", name="Mirror Lake", type=WaterBodyType.LAKE,
            quality=WaterQuality.FRESH, region_ids=["r_grassland"],
            footprint=_box(420, 280, 520, 360), surface_elevation=200.0,
            source_ids=["w_glass_river", "w_cascade"], flows_to="w_coastal_sea",
        ),
        WaterBody(
            id="w_coastal_sea", name="Cliffshore Sea", type=WaterBodyType.OCEAN,
            quality=WaterQuality.SALT, region_ids=["r_coast"],
            footprint=_box(700, 60, 1000, 380), surface_elevation=120.0,
            source_ids=["w_mirror_lake"], exits_world=True,
            description="A shallow sea that pours off the cliff edge into the void.",
        ),
        WaterBody(
            id="w_desert_oasis", name="Ochre Oasis", type=WaterBodyType.OASIS,
            quality=WaterQuality.FRESH, region_ids=["r_desert"],
            footprint=_box(150, 250, 200, 300), surface_elevation=160.0,
        ),
        WaterBody(
            id="w_hot_spring", name="Ember Springs", type=WaterBodyType.HOT_SPRING,
            quality=WaterQuality.MINERAL, region_ids=["r_volcano"],
            surface_elevation=300.0, mouth_elevation=205.0,
            source_ids=["t_ember_volcano"], flows_to="w_mirror_lake",
            path=[Coordinate2D(x=200, y=450), Coordinate2D(x=440, y=310)],
        ),
    ]
    return WaterSystems(bodies=bodies)


def _biomes() -> Biomes:
    zones = [
        Biome(
            id="b_alpine", name="Frostspire Alpine", type=BiomeType.ALPINE,
            region_ids=["r_north_peaks"], temperature=TemperatureBand.COLD,
            moisture=MoistureLevel.MODERATE, elevation_range=(400.0, 900.0),
            adjacent_to=["b_highland"],
            terrain_feature_ids=["t_frost_peaks", "t_north_glacier"],
            water_body_ids=["w_alpine_spring", "w_glacier_melt"],
        ),
        Biome(
            id="b_highland", name="Windward Highland", type=BiomeType.HIGHLAND,
            region_ids=["r_highland"], temperature=TemperatureBand.TEMPERATE,
            moisture=MoistureLevel.MODERATE, elevation_range=(300.0, 500.0),
            adjacent_to=["b_alpine", "b_forest", "b_grassland"],
            terrain_feature_ids=["t_highland_plateau"], water_body_ids=["w_glass_river"],
        ),
        Biome(
            id="b_forest", name="Emerald Forest", type=BiomeType.TEMPERATE_FOREST,
            region_ids=["r_forest"], temperature=TemperatureBand.TEMPERATE,
            moisture=MoistureLevel.HUMID, elevation_range=(150.0, 350.0),
            adjacent_to=["b_highland", "b_grassland", "b_beach"],
            terrain_feature_ids=["t_forest_hills"], water_body_ids=["w_cascade"],
        ),
        Biome(
            id="b_grassland", name="Central Grassland", type=BiomeType.GRASSLAND,
            region_ids=["r_grassland"], temperature=TemperatureBand.TEMPERATE,
            moisture=MoistureLevel.MODERATE, elevation_range=(130.0, 300.0),
            adjacent_to=["b_highland", "b_forest", "b_desert", "b_wetland"],
            terrain_feature_ids=["t_central_plain"],
            water_body_ids=["w_glass_river", "w_mirror_lake"],
        ),
        Biome(
            id="b_desert", name="Ochre Desert", type=BiomeType.DESERT,
            region_ids=["r_desert"], temperature=TemperatureBand.HOT,
            moisture=MoistureLevel.ARID, elevation_range=(150.0, 400.0),
            adjacent_to=["b_grassland", "b_volcanic"],
            terrain_feature_ids=["t_desert_mesa"], water_body_ids=["w_desert_oasis"],
        ),
        Biome(
            id="b_volcanic", name="Emberwaste", type=BiomeType.VOLCANIC,
            region_ids=["r_volcano"], temperature=TemperatureBand.HOT,
            moisture=MoistureLevel.SEMI_ARID, elevation_range=(200.0, 750.0),
            adjacent_to=["b_desert"],
            terrain_feature_ids=["t_ember_volcano"], water_body_ids=["w_hot_spring"],
        ),
        Biome(
            id="b_wetland", name="Reedmere Wetland", type=BiomeType.WETLAND,
            region_ids=["r_wetland"], temperature=TemperatureBand.WARM,
            moisture=MoistureLevel.SATURATED, elevation_range=(110.0, 140.0),
            adjacent_to=["b_grassland", "b_beach"],
            terrain_feature_ids=["t_wetland_basin"], water_body_ids=["w_mirror_lake"],
        ),
        Biome(
            id="b_beach", name="Cliffshore Beach", type=BiomeType.BEACH,
            region_ids=["r_coast"], temperature=TemperatureBand.WARM,
            moisture=MoistureLevel.MODERATE, elevation_range=(118.0, 140.0),
            adjacent_to=["b_forest", "b_wetland", "b_marine"],
            terrain_feature_ids=["t_coastal_cliffs"], water_body_ids=["w_coastal_sea"],
        ),
        Biome(
            id="b_marine", name="Cliffshore Shallows", type=BiomeType.COASTAL_OCEAN,
            region_ids=["r_coast"], temperature=TemperatureBand.TEMPERATE,
            moisture=MoistureLevel.SATURATED, elevation_range=(100.0, 120.0),
            adjacent_to=["b_beach"], water_body_ids=["w_coastal_sea"],
        ),
    ]
    return Biomes(zones=zones)


def _flora() -> Flora:
    species = [
        FloraSpecies(
            id="fl_frost_moss", name="Frost Moss", category=FloraCategory.MOSS,
            biome_ids=["b_alpine"], rarity=Rarity.COMMON, pollination=PollinationMode.SPORE,
            water_requirement=0.4, provides_food=True, max_height=0.05,
        ),
        FloraSpecies(
            id="fl_alpine_bellflower", name="Alpine Bellflower", category=FloraCategory.FLOWER,
            biome_ids=["b_alpine", "b_highland"], rarity=Rarity.UNCOMMON,
            pollination=PollinationMode.INSECT, water_requirement=0.5,
            provides_food=True, max_height=0.2,
        ),
        FloraSpecies(
            id="fl_emerald_oak", name="Emerald Oak", category=FloraCategory.TREE,
            biome_ids=["b_forest"], rarity=Rarity.COMMON, pollination=PollinationMode.WIND,
            water_requirement=0.6, provides_food=True, provides_shelter=True, max_height=28.0,
        ),
        FloraSpecies(
            id="fl_glow_fern", name="Glow Fern", category=FloraCategory.FERN,
            biome_ids=["b_forest"], rarity=Rarity.UNCOMMON, pollination=PollinationMode.SPORE,
            water_requirement=0.7, max_height=1.2,
        ),
        FloraSpecies(
            id="fl_canopy_vine", name="Canopy Vine", category=FloraCategory.VINE,
            biome_ids=["b_forest"], rarity=Rarity.COMMON, pollination=PollinationMode.INSECT,
            water_requirement=0.6, provides_food=True, max_height=15.0,
        ),
        FloraSpecies(
            id="fl_meadow_grass", name="Meadow Grass", category=FloraCategory.GRASS,
            biome_ids=["b_grassland"], rarity=Rarity.ABUNDANT, pollination=PollinationMode.WIND,
            water_requirement=0.4, provides_food=True, max_height=0.8,
        ),
        FloraSpecies(
            id="fl_prairie_bloom", name="Prairie Bloom", category=FloraCategory.FLOWER,
            biome_ids=["b_grassland"], rarity=Rarity.COMMON, pollination=PollinationMode.INSECT,
            water_requirement=0.4, provides_food=True, max_height=0.5,
        ),
        FloraSpecies(
            id="fl_sun_cactus", name="Sun Cactus", category=FloraCategory.CACTUS,
            biome_ids=["b_desert"], rarity=Rarity.COMMON, pollination=PollinationMode.INSECT,
            water_requirement=0.05, provides_food=True, max_height=3.5,
        ),
        FloraSpecies(
            id="fl_stone_lichen", name="Stone Lichen", category=FloraCategory.LICHEN,
            biome_ids=["b_desert", "b_volcanic"], rarity=Rarity.COMMON,
            pollination=PollinationMode.SPORE, water_requirement=0.1, max_height=0.02,
        ),
        FloraSpecies(
            id="fl_ash_lichen", name="Ashbloom Lichen", category=FloraCategory.LICHEN,
            biome_ids=["b_volcanic"], rarity=Rarity.RARE, pollination=PollinationMode.SPORE,
            water_requirement=0.15, provides_food=True, max_height=0.03,
        ),
        FloraSpecies(
            id="fl_marsh_reed", name="Marsh Reed", category=FloraCategory.REED,
            biome_ids=["b_wetland"], rarity=Rarity.ABUNDANT, pollination=PollinationMode.WIND,
            water_requirement=0.95, provides_shelter=True, max_height=3.0,
        ),
        FloraSpecies(
            id="fl_water_lily", name="Mirror Lily", category=FloraCategory.FLOWER,
            biome_ids=["b_wetland"], rarity=Rarity.COMMON, pollination=PollinationMode.INSECT,
            water_requirement=1.0, provides_food=True, max_height=0.3,
        ),
        FloraSpecies(
            id="fl_palm", name="Cliffshore Palm", category=FloraCategory.TREE,
            biome_ids=["b_beach"], rarity=Rarity.COMMON, pollination=PollinationMode.WIND,
            water_requirement=0.5, provides_food=True, provides_shelter=True, max_height=12.0,
        ),
        FloraSpecies(
            id="fl_dune_grass", name="Dune Grass", category=FloraCategory.GRASS,
            biome_ids=["b_beach"], rarity=Rarity.COMMON, pollination=PollinationMode.WIND,
            water_requirement=0.3, provides_food=True, max_height=0.6,
        ),
        FloraSpecies(
            id="fl_kelp", name="Cliffshore Kelp", category=FloraCategory.ALGAE,
            biome_ids=["b_marine"], rarity=Rarity.ABUNDANT, pollination=PollinationMode.WATER,
            water_requirement=1.0, provides_food=True, provides_shelter=True, max_height=8.0,
        ),
        FloraSpecies(
            id="fl_reef_coral", name="Sunlit Coral", category=FloraCategory.CORAL,
            biome_ids=["b_marine"], rarity=Rarity.UNCOMMON, pollination=PollinationMode.WATER,
            water_requirement=1.0, provides_shelter=True, max_height=1.5,
        ),
    ]
    return Flora(species=species)


def _fauna() -> Fauna:
    W, C, F, S, B, A = (
        Locomotion.WALKING, Locomotion.CLIMBING, Locomotion.FLYING,
        Locomotion.SWIMMING, Locomotion.BURROWING, Locomotion.AMPHIBIOUS,
    )
    species = [
        FaunaSpecies(
            id="fa_alpine_hare", name="Alpine Hare", category=FaunaCategory.MAMMAL,
            trophic_role=TrophicRole.HERBIVORE, locomotion=[W, B], biome_ids=["b_alpine"],
            rarity=Rarity.COMMON, diet_flora_ids=["fl_frost_moss", "fl_alpine_bellflower"],
        ),
        FaunaSpecies(
            id="fa_snow_finch", name="Snow Finch", category=FaunaCategory.BIRD,
            trophic_role=TrophicRole.HERBIVORE, locomotion=[F, W],
            biome_ids=["b_alpine", "b_grassland"], rarity=Rarity.COMMON,
            diet_flora_ids=["fl_alpine_bellflower", "fl_meadow_grass"],
        ),
        FaunaSpecies(
            id="fa_forest_deer", name="Emerald Deer", category=FaunaCategory.MAMMAL,
            trophic_role=TrophicRole.HERBIVORE, locomotion=[W], biome_ids=["b_forest", "b_grassland"],
            rarity=Rarity.COMMON, diet_flora_ids=["fl_emerald_oak", "fl_meadow_grass", "fl_canopy_vine"],
        ),
        FaunaSpecies(
            id="fa_pollinator_bee", name="Verdant Bee", category=FaunaCategory.INSECT,
            trophic_role=TrophicRole.POLLINATOR, locomotion=[F],
            biome_ids=["b_forest", "b_grassland", "b_desert", "b_wetland", "b_beach"],
            rarity=Rarity.ABUNDANT,
            diet_flora_ids=["fl_prairie_bloom", "fl_alpine_bellflower", "fl_water_lily", "fl_sun_cactus"],
        ),
        FaunaSpecies(
            id="fa_songbird", name="Reach Songbird", category=FaunaCategory.BIRD,
            trophic_role=TrophicRole.OMNIVORE, locomotion=[F, W], biome_ids=["b_forest"],
            rarity=Rarity.COMMON, diet_flora_ids=["fl_emerald_oak", "fl_canopy_vine"],
            diet_fauna_ids=["fa_pollinator_bee"],
        ),
        FaunaSpecies(
            id="fa_grass_hopper", name="Prairie Hopper", category=FaunaCategory.INSECT,
            trophic_role=TrophicRole.HERBIVORE, locomotion=[W, F], biome_ids=["b_grassland"],
            rarity=Rarity.ABUNDANT, diet_flora_ids=["fl_meadow_grass", "fl_prairie_bloom"],
        ),
        FaunaSpecies(
            id="fa_prairie_fox", name="Plains Fox", category=FaunaCategory.MAMMAL,
            trophic_role=TrophicRole.CARNIVORE, locomotion=[W], biome_ids=["b_grassland", "b_forest"],
            rarity=Rarity.UNCOMMON, diet_fauna_ids=["fa_grass_hopper", "fa_songbird"],
        ),
        FaunaSpecies(
            id="fa_desert_beetle", name="Ochre Beetle", category=FaunaCategory.INSECT,
            trophic_role=TrophicRole.HERBIVORE, locomotion=[W, B], biome_ids=["b_desert"],
            rarity=Rarity.COMMON, diet_flora_ids=["fl_sun_cactus", "fl_stone_lichen"],
        ),
        FaunaSpecies(
            id="fa_desert_lizard", name="Basking Lizard", category=FaunaCategory.REPTILE,
            trophic_role=TrophicRole.CARNIVORE, locomotion=[W, C], biome_ids=["b_desert"],
            rarity=Rarity.COMMON, diet_fauna_ids=["fa_desert_beetle"],
        ),
        FaunaSpecies(
            id="fa_lava_beetle", name="Ember Beetle", category=FaunaCategory.INSECT,
            trophic_role=TrophicRole.HERBIVORE, locomotion=[W], biome_ids=["b_volcanic"],
            rarity=Rarity.RARE, diet_flora_ids=["fl_ash_lichen", "fl_stone_lichen"],
        ),
        FaunaSpecies(
            id="fa_apex_raptor", name="Spire Raptor", category=FaunaCategory.BIRD,
            trophic_role=TrophicRole.APEX_PREDATOR, locomotion=[F],
            biome_ids=["b_alpine", "b_grassland", "b_forest"], rarity=Rarity.RARE,
            diet_fauna_ids=["fa_alpine_hare", "fa_prairie_fox", "fa_songbird"],
        ),
        FaunaSpecies(
            id="fa_marsh_frog", name="Reedmere Frog", category=FaunaCategory.AMPHIBIAN,
            trophic_role=TrophicRole.CARNIVORE, locomotion=[A, S], biome_ids=["b_wetland"],
            rarity=Rarity.COMMON, diet_fauna_ids=["fa_pollinator_bee", "fa_grass_hopper"],
        ),
        FaunaSpecies(
            id="fa_heron", name="Pale Heron", category=FaunaCategory.BIRD,
            trophic_role=TrophicRole.CARNIVORE, locomotion=[F, W], biome_ids=["b_wetland"],
            rarity=Rarity.UNCOMMON, diet_fauna_ids=["fa_marsh_frog"],
        ),
        FaunaSpecies(
            id="fa_shore_crab", name="Cliffshore Crab", category=FaunaCategory.CRUSTACEAN,
            trophic_role=TrophicRole.SCAVENGER, locomotion=[W, S], biome_ids=["b_beach", "b_marine"],
            rarity=Rarity.COMMON, diet_flora_ids=["fl_kelp", "fl_dune_grass"],
        ),
        FaunaSpecies(
            id="fa_reef_fish", name="Sunlit Wrasse", category=FaunaCategory.FISH,
            trophic_role=TrophicRole.HERBIVORE, locomotion=[S], biome_ids=["b_marine"],
            rarity=Rarity.ABUNDANT, diet_flora_ids=["fl_kelp"],
        ),
        FaunaSpecies(
            id="fa_reef_shark", name="Cliff Shark", category=FaunaCategory.FISH,
            trophic_role=TrophicRole.APEX_PREDATOR, locomotion=[S], biome_ids=["b_marine"],
            rarity=Rarity.RARE, diet_fauna_ids=["fa_reef_fish", "fa_shore_crab"],
        ),
        FaunaSpecies(
            id="fa_decomposer_beetle", name="Loam Beetle", category=FaunaCategory.INSECT,
            trophic_role=TrophicRole.DECOMPOSER, locomotion=[W, B], biome_ids=["b_forest", "b_wetland"],
            rarity=Rarity.COMMON,
        ),
    ]
    return Fauna(species=species)


def _interactions() -> Interactions:
    edges = [
        EcologicalInteraction(id="ix_raptor_fox", type=InteractionType.PREDATION,
                              source_id="fa_apex_raptor", target_id="fa_prairie_fox", strength=0.8),
        EcologicalInteraction(id="ix_shark_fish", type=InteractionType.PREDATION,
                              source_id="fa_reef_shark", target_id="fa_reef_fish", strength=0.7),
        EcologicalInteraction(id="ix_deer_oak", type=InteractionType.HERBIVORY,
                              source_id="fa_forest_deer", target_id="fl_emerald_oak", strength=0.5),
        EcologicalInteraction(id="ix_bee_bloom", type=InteractionType.POLLINATION,
                              source_id="fa_pollinator_bee", target_id="fl_prairie_bloom",
                              strength=0.9, seasonal=True),
        EcologicalInteraction(id="ix_bee_cactus", type=InteractionType.POLLINATION,
                              source_id="fa_pollinator_bee", target_id="fl_sun_cactus", strength=0.6),
        EcologicalInteraction(id="ix_bird_oak", type=InteractionType.SEED_DISPERSAL,
                              source_id="fa_songbird", target_id="fl_emerald_oak", strength=0.5),
        EcologicalInteraction(id="ix_finch_migrate", type=InteractionType.MIGRATION,
                              source_id="fa_snow_finch", target_id="b_grassland",
                              strength=0.6, seasonal=True),
        EcologicalInteraction(id="ix_fish_coral", type=InteractionType.SYMBIOSIS,
                              source_id="fa_reef_fish", target_id="fl_reef_coral", strength=0.6),
        EcologicalInteraction(id="ix_beetle_decompose", type=InteractionType.DECOMPOSITION,
                              source_id="fa_decomposer_beetle", target_id="fl_emerald_oak", strength=0.4),
        EcologicalInteraction(id="ix_bird_nest", type=InteractionType.NESTING,
                              source_id="fa_songbird", target_id="fl_emerald_oak", strength=0.5),
        EcologicalInteraction(id="ix_hopper_deer_comp", type=InteractionType.COMPETITION,
                              source_id="fa_grass_hopper", target_id="fa_forest_deer", strength=0.3),
    ]
    return Interactions(edges=edges)


def _weather() -> Weather:
    winds = [
        WindPattern(id="wind_trade", name="Cliffshore Trades", direction="northeast", strength=0.5),
        WindPattern(id="wind_polar", name="Frostspire Downdraft", direction="south", strength=0.3),
    ]
    bw = [
        BiomeWeather(biome_id="b_alpine", avg_temperature=-5.0, precipitation=PrecipitationType.SNOW,
                     annual_precipitation=400.0, storm_frequency=0.3),
        BiomeWeather(biome_id="b_highland", avg_temperature=8.0, precipitation=PrecipitationType.RAIN,
                     annual_precipitation=550.0, storm_frequency=0.2),
        BiomeWeather(biome_id="b_forest", avg_temperature=14.0, precipitation=PrecipitationType.RAIN,
                     annual_precipitation=1200.0, storm_frequency=0.3),
        BiomeWeather(biome_id="b_grassland", avg_temperature=16.0, precipitation=PrecipitationType.RAIN,
                     annual_precipitation=700.0, storm_frequency=0.2),
        BiomeWeather(biome_id="b_desert", avg_temperature=32.0, precipitation=PrecipitationType.NONE,
                     annual_precipitation=0.0, storm_frequency=0.05),
        BiomeWeather(biome_id="b_volcanic", avg_temperature=28.0, precipitation=PrecipitationType.ASH,
                     annual_precipitation=150.0, storm_frequency=0.1),
        BiomeWeather(biome_id="b_wetland", avg_temperature=20.0, precipitation=PrecipitationType.RAIN,
                     annual_precipitation=1500.0, storm_frequency=0.4),
        BiomeWeather(biome_id="b_beach", avg_temperature=24.0, precipitation=PrecipitationType.RAIN,
                     annual_precipitation=900.0, storm_frequency=0.3),
        BiomeWeather(biome_id="b_marine", avg_temperature=18.0, precipitation=PrecipitationType.RAIN,
                     annual_precipitation=1000.0, storm_frequency=0.35),
    ]
    return Weather(prevailing_winds=winds, biome_weather=bw)


def _seasons() -> Seasons:
    cycle = [
        Season(id="s_verdant", name="Verdant Rise", order=0, length_fraction=0.25,
               temperature_modifier=2.0, precipitation_modifier=1.2,
               triggers_event_ids=["ev_spring_flood"]),
        Season(id="s_high_sun", name="High Sun", order=1, length_fraction=0.25,
               temperature_modifier=6.0, precipitation_modifier=0.7,
               triggers_event_ids=["ev_wildfire"]),
        Season(id="s_amber", name="Amber Fall", order=2, length_fraction=0.25,
               temperature_modifier=0.0, precipitation_modifier=1.0,
               triggers_event_ids=["ev_migration"]),
        Season(id="s_frost", name="Frostfall", order=3, length_fraction=0.25,
               temperature_modifier=-6.0, precipitation_modifier=0.8,
               triggers_event_ids=["ev_blizzard"]),
    ]
    return Seasons(cycle=cycle)


def _natural_events() -> NaturalEvents:
    events = [
        NaturalEvent(id="ev_spring_flood", name="Verdant Flood", type=EventType.FLOOD,
                     recurrence_years=1.0, affected_region_ids=["r_wetland", "r_grassland"],
                     affected_biome_ids=["b_wetland"], triggers=["w_glass_river"]),
        NaturalEvent(id="ev_wildfire", name="Highsun Wildfire", type=EventType.WILDFIRE,
                     recurrence_years=6.0, affected_region_ids=["r_grassland", "r_forest"],
                     affected_biome_ids=["b_grassland"]),
        NaturalEvent(id="ev_migration", name="Great Finch Migration", type=EventType.MIGRATION,
                     recurrence_years=1.0, affected_region_ids=["r_grassland", "r_north_peaks"],
                     affected_biome_ids=["b_grassland", "b_alpine"]),
        NaturalEvent(id="ev_blizzard", name="Frostfall Blizzard", type=EventType.BLIZZARD,
                     recurrence_years=1.0, affected_region_ids=["r_north_peaks"],
                     affected_biome_ids=["b_alpine"]),
        NaturalEvent(id="ev_eruption", name="Ember Eruption", type=EventType.VOLCANIC_ERUPTION,
                     recurrence_years=50.0, affected_region_ids=["r_volcano"],
                     affected_biome_ids=["b_volcanic"], triggers=["t_ember_volcano"]),
    ]
    return NaturalEvents(events=events)


def _simulation() -> Simulation:
    dynamics = [
        LongTermDynamic(id="sim_predator_prey", name="Raptor-Fox-Hopper Cycle",
                        type=DynamicType.PREDATOR_PREY_CYCLE, period_years=7.0,
                        involves_ids=["fa_apex_raptor", "fa_prairie_fox", "fa_grass_hopper"]),
        LongTermDynamic(id="sim_migration", name="Seasonal Finch Migration",
                        type=DynamicType.MIGRATION_CYCLE, period_years=1.0,
                        involves_ids=["fa_snow_finch", "b_grassland", "b_alpine"]),
        LongTermDynamic(id="sim_succession", name="Grassland-Forest Succession",
                        type=DynamicType.ECOLOGICAL_SUCCESSION,
                        involves_ids=["b_grassland", "b_forest"]),
        LongTermDynamic(id="sim_fire_regen", name="Post-Fire Regeneration",
                        type=DynamicType.WILDFIRE_REGENERATION,
                        involves_ids=["ev_wildfire", "b_grassland"]),
    ]
    return Simulation(stability_index=0.72, dynamics=dynamics)


@lru_cache(maxsize=1)
def sample_world() -> World:
    """Return the canonical valid world (built once and cached)."""
    return World(
        metadata=_metadata(),
        layout=_layout(),
        terrain=_terrain(),
        water=_water(),
        biomes=_biomes(),
        flora=_flora(),
        fauna=_fauna(),
        interactions=_interactions(),
        weather=_weather(),
        seasons=_seasons(),
        natural_events=_natural_events(),
        simulation=_simulation(),
    )
