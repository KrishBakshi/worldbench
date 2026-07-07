"""WorldBench schema models.

The public surface is the :class:`World` model and its section models. Import
from ``benchmark.models`` (installed as ``worldbench``) rather than the
submodules to keep call sites stable across schema revisions.
"""

from __future__ import annotations

from .biomes import Biome, Biomes, BiomeType, MoistureLevel, TemperatureBand
from .common import (
    BoundingRegion,
    ConservationTrend,
    Coordinate2D,
    Coordinate3D,
    EntityId,
    Rarity,
    WorldBenchModel,
)
from .fauna import Fauna, FaunaCategory, FaunaSpecies, Locomotion, TrophicRole
from .flora import Flora, FloraCategory, FloraSpecies, PollinationMode
from .graph import build_world_graph, food_web
from .interactions import EcologicalInteraction, Interactions, InteractionType
from .layout import (
    CardinalDirection,
    EdgeType,
    Region,
    WorldLayout,
    WorldTopology,
)
from .metadata import SCHEMA_VERSION, WorldMetadata
from .natural_events import EventType, NaturalEvent, NaturalEvents, Severity
from .seasons import Season, Seasons
from .simulation import DynamicType, LongTermDynamic, Simulation
from .terrain import Terrain, TerrainFeature, TerrainType, VolcanicActivity
from .water import (
    FLOWING_TYPES,
    TERMINAL_TYPES,
    WaterBody,
    WaterBodyType,
    WaterQuality,
    WaterSystems,
)
from .weather import BiomeWeather, PrecipitationType, Weather, WindPattern
from .world import World, dump_schema, load_world

__all__ = [
    "SCHEMA_VERSION",
    "World",
    "WorldBenchModel",
    "WorldMetadata",
    "WorldLayout",
    "WorldTopology",
    "EdgeType",
    "CardinalDirection",
    "Region",
    "Terrain",
    "TerrainFeature",
    "TerrainType",
    "VolcanicActivity",
    "WaterSystems",
    "WaterBody",
    "WaterBodyType",
    "WaterQuality",
    "FLOWING_TYPES",
    "TERMINAL_TYPES",
    "Biomes",
    "Biome",
    "BiomeType",
    "MoistureLevel",
    "TemperatureBand",
    "Flora",
    "FloraSpecies",
    "FloraCategory",
    "PollinationMode",
    "Fauna",
    "FaunaSpecies",
    "FaunaCategory",
    "TrophicRole",
    "Locomotion",
    "Interactions",
    "EcologicalInteraction",
    "InteractionType",
    "Weather",
    "BiomeWeather",
    "WindPattern",
    "PrecipitationType",
    "Seasons",
    "Season",
    "NaturalEvents",
    "NaturalEvent",
    "EventType",
    "Severity",
    "Simulation",
    "LongTermDynamic",
    "DynamicType",
    "BoundingRegion",
    "Coordinate2D",
    "Coordinate3D",
    "EntityId",
    "Rarity",
    "ConservationTrend",
    "build_world_graph",
    "food_web",
    "load_world",
    "dump_schema",
]
