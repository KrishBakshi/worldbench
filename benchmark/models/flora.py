"""Flora: plant species and their placement across biomes."""

from __future__ import annotations

from enum import Enum

from pydantic import Field, field_validator, model_validator

from .common import EntityId, Rarity, WorldBenchModel, validate_id_format


class FloraCategory(str, Enum):
    TREE = "tree"
    CONIFER = "conifer"
    SHRUB = "shrub"
    GRASS = "grass"
    FLOWER = "flower"
    CACTUS = "cactus"
    SUCCULENT = "succulent"
    FERN = "fern"
    MOSS = "moss"
    LICHEN = "lichen"
    FUNGUS = "fungus"
    VINE = "vine"
    REED = "reed"
    ALGAE = "algae"
    SEAGRASS = "seagrass"
    CORAL = "coral"


class PollinationMode(str, Enum):
    WIND = "wind"
    INSECT = "insect"
    BIRD = "bird"
    BAT = "bat"
    WATER = "water"
    SELF = "self"
    SPORE = "spore"
    NONE = "none"


class FloraSpecies(WorldBenchModel):
    """A plant species and where it grows."""

    id: EntityId
    name: str = Field(min_length=1, max_length=120)
    category: FloraCategory
    biome_ids: list[EntityId] = Field(
        min_length=1,
        description="Biomes where the species grows. Each must ecologically "
        "support this flora category (checked against the knowledge base).",
    )
    rarity: Rarity = Field(default=Rarity.COMMON)
    pollination: PollinationMode = Field(
        description="How the species reproduces. Insect/bird/bat pollination "
        "requires a matching pollinator interaction in the world."
    )
    water_requirement: float = Field(
        ge=0.0,
        le=1.0,
        description="Normalized water need: 0 xerophyte, 1 aquatic.",
    )
    provides_food: bool = Field(
        default=False,
        description="Whether fauna can feed on this species (fruit, leaves, "
        "nectar, seeds).",
    )
    provides_shelter: bool = Field(
        default=False,
        description="Whether the species offers nesting or cover for fauna.",
    )
    max_height: float = Field(
        gt=0.0,
        description="Typical mature height in world units.",
    )
    description: str = Field(default="", max_length=2000)

    @field_validator("id")
    @classmethod
    def _id_format(cls, v: str) -> str:
        return validate_id_format(v)

    @field_validator("biome_ids")
    @classmethod
    def _ref_id_format(cls, v: list[str]) -> list[str]:
        for item in v:
            validate_id_format(item)
        return v


class Flora(WorldBenchModel):
    """All plant species in the world."""

    species: list[FloraSpecies] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_ids(self) -> "Flora":
        ids = [s.id for s in self.species]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate flora species ids: {sorted(dupes)}")
        return self
