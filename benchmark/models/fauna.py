"""Fauna: animal species, their diets, habitats, and trophic roles."""

from __future__ import annotations

from enum import Enum

from pydantic import Field, field_validator, model_validator

from .common import ConservationTrend, EntityId, Rarity, WorldBenchModel, validate_id_format


class FaunaCategory(str, Enum):
    MAMMAL = "mammal"
    BIRD = "bird"
    REPTILE = "reptile"
    AMPHIBIAN = "amphibian"
    FISH = "fish"
    INSECT = "insect"
    ARACHNID = "arachnid"
    CRUSTACEAN = "crustacean"
    MOLLUSK = "mollusk"
    CEPHALOPOD = "cephalopod"


class TrophicRole(str, Enum):
    PRODUCER_CONSUMER = "producer_consumer"  # e.g. coral hosting algae
    HERBIVORE = "herbivore"
    OMNIVORE = "omnivore"
    CARNIVORE = "carnivore"
    APEX_PREDATOR = "apex_predator"
    SCAVENGER = "scavenger"
    DECOMPOSER = "decomposer"
    POLLINATOR = "pollinator"
    FILTER_FEEDER = "filter_feeder"


class Locomotion(str, Enum):
    WALKING = "walking"
    CLIMBING = "climbing"
    FLYING = "flying"
    SWIMMING = "swimming"
    BURROWING = "burrowing"
    GLIDING = "gliding"
    AMPHIBIOUS = "amphibious"


class FaunaSpecies(WorldBenchModel):
    """An animal species and its ecological role."""

    id: EntityId
    name: str = Field(min_length=1, max_length=120)
    category: FaunaCategory
    trophic_role: TrophicRole
    locomotion: list[Locomotion] = Field(
        min_length=1,
        description="How the animal moves. Determines which biomes/terrain it "
        "can occupy (e.g. only 'swimming' fauna in deep ocean).",
    )
    biome_ids: list[EntityId] = Field(
        min_length=1,
        description="Biomes the species inhabits. Each must ecologically support "
        "this fauna category (checked against the knowledge base).",
    )
    rarity: Rarity = Field(default=Rarity.COMMON)
    population_trend: ConservationTrend = Field(default=ConservationTrend.STABLE)
    diet_flora_ids: list[EntityId] = Field(
        default_factory=list,
        description="Flora species this animal eats. Required (non-empty) for "
        "herbivores and omnivores.",
    )
    diet_fauna_ids: list[EntityId] = Field(
        default_factory=list,
        description="Fauna species this animal preys on. Required for carnivores, "
        "omnivores, and apex predators. No species may appear in its own diet.",
    )
    description: str = Field(default="", max_length=2000)

    @field_validator("id")
    @classmethod
    def _id_format(cls, v: str) -> str:
        return validate_id_format(v)

    @field_validator("biome_ids", "diet_flora_ids", "diet_fauna_ids")
    @classmethod
    def _ref_id_format(cls, v: list[str]) -> list[str]:
        for item in v:
            validate_id_format(item)
        return v

    @model_validator(mode="after")
    def _no_self_predation(self) -> "FaunaSpecies":
        if self.id in self.diet_fauna_ids:
            raise ValueError(f"fauna {self.id}: a species cannot prey on itself")
        return self


class Fauna(WorldBenchModel):
    """All animal species in the world."""

    species: list[FaunaSpecies] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_ids(self) -> "Fauna":
        ids = [s.id for s in self.species]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate fauna species ids: {sorted(dupes)}")
        return self
