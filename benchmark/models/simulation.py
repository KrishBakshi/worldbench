"""Simulation: long-term ecological dynamics the world claims to sustain.

This section lets a generator declare qualitative long-run behavior (population
cycles, succession, climate drift) that validators check for internal
consistency with the static ecosystem — e.g. a declared predator-prey cycle
must reference an actual predation interaction.
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field, field_validator, model_validator

from .common import EntityId, WorldBenchModel, validate_id_format


class DynamicType(str, Enum):
    PREDATOR_PREY_CYCLE = "predator_prey_cycle"
    ECOLOGICAL_SUCCESSION = "ecological_succession"
    MIGRATION_CYCLE = "migration_cycle"
    NUTRIENT_CYCLE = "nutrient_cycle"
    POPULATION_BOOM_BUST = "population_boom_bust"
    CLIMATE_DRIFT = "climate_drift"
    GLACIAL_CYCLE = "glacial_cycle"
    WILDFIRE_REGENERATION = "wildfire_regeneration"


class LongTermDynamic(WorldBenchModel):
    """A declared long-run ecological process."""

    id: EntityId
    name: str = Field(min_length=1, max_length=120)
    type: DynamicType
    period_years: float | None = Field(
        default=None,
        gt=0.0,
        description="Cycle period in years, for periodic dynamics.",
    )
    involves_ids: list[EntityId] = Field(
        min_length=1,
        description="Ids of species, biomes, interactions, or events this "
        "dynamic operates on.",
    )
    description: str = Field(default="", max_length=2000)

    @field_validator("id")
    @classmethod
    def _id_format(cls, v: str) -> str:
        return validate_id_format(v)

    @field_validator("involves_ids")
    @classmethod
    def _ref_id_format(cls, v: list[str]) -> list[str]:
        for item in v:
            validate_id_format(item)
        return v


class Simulation(WorldBenchModel):
    """Declared long-term dynamics of the world."""

    stability_index: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Generator's self-assessed ecosystem stability (0 fragile, "
        "1 highly resilient).",
    )
    dynamics: list[LongTermDynamic] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids(self) -> "Simulation":
        ids = [d.id for d in self.dynamics]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate dynamic ids: {sorted(dupes)}")
        return self
