"""Biomes: climatic/ecological zones layered over regions and terrain."""

from __future__ import annotations

from enum import Enum

from pydantic import Field, field_validator, model_validator

from .common import EntityId, WorldBenchModel, validate_id_format


class BiomeType(str, Enum):
    ALPINE = "alpine"
    TUNDRA = "tundra"
    SNOW_FOREST = "snow_forest"
    TEMPERATE_FOREST = "temperate_forest"
    RAINFOREST = "rainforest"
    GRASSLAND = "grassland"
    SAVANNA = "savanna"
    SHRUBLAND = "shrubland"
    DESERT = "desert"
    VOLCANIC = "volcanic"
    WETLAND = "wetland"
    BEACH = "beach"
    COASTAL_OCEAN = "coastal_ocean"
    DEEP_OCEAN = "deep_ocean"
    CORAL_REEF = "coral_reef"
    FLOWERING_GROVE = "flowering_grove"
    HIGHLAND = "highland"
    CAVE = "cave"


class MoistureLevel(str, Enum):
    ARID = "arid"
    SEMI_ARID = "semi_arid"
    MODERATE = "moderate"
    HUMID = "humid"
    SATURATED = "saturated"


class TemperatureBand(str, Enum):
    POLAR = "polar"
    COLD = "cold"
    TEMPERATE = "temperate"
    WARM = "warm"
    HOT = "hot"


class Biome(WorldBenchModel):
    """A climatic and ecological zone of the world."""

    id: EntityId
    name: str = Field(min_length=1, max_length=120)
    type: BiomeType
    region_ids: list[EntityId] = Field(
        min_length=1,
        description="Layout regions this biome covers (fully or partially).",
    )
    temperature: TemperatureBand
    moisture: MoistureLevel
    elevation_range: tuple[float, float] = Field(
        description="(min, max) elevation band the biome occupies, in world units."
    )
    adjacent_to: list[EntityId] = Field(
        default_factory=list,
        description="Ids of biomes sharing a border. Must be symmetric.",
    )
    terrain_feature_ids: list[EntityId] = Field(
        default_factory=list,
        description="Terrain features lying within this biome.",
    )
    water_body_ids: list[EntityId] = Field(
        default_factory=list,
        description="Water bodies within or bordering this biome.",
    )
    description: str = Field(default="", max_length=2000)

    @field_validator("id")
    @classmethod
    def _id_format(cls, v: str) -> str:
        return validate_id_format(v)

    @field_validator("region_ids", "adjacent_to", "terrain_feature_ids", "water_body_ids")
    @classmethod
    def _ref_id_format(cls, v: list[str]) -> list[str]:
        for item in v:
            validate_id_format(item)
        return v

    @model_validator(mode="after")
    def _elevation_band(self) -> "Biome":
        lo, hi = self.elevation_range
        if hi < lo:
            raise ValueError(
                f"biome {self.id}: elevation_range max ({hi}) below min ({lo})"
            )
        return self


class Biomes(WorldBenchModel):
    """All biomes in the world."""

    zones: list[Biome] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_ids(self) -> "Biomes":
        ids = [b.id for b in self.zones]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate biome ids: {sorted(dupes)}")
        return self
