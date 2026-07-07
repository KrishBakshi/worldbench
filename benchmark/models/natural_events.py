"""Natural events: disturbances such as floods, wildfires, eruptions, migrations."""

from __future__ import annotations

from enum import Enum

from pydantic import Field, field_validator, model_validator

from .common import EntityId, WorldBenchModel, validate_id_format


class EventType(str, Enum):
    FLOOD = "flood"
    DROUGHT = "drought"
    WILDFIRE = "wildfire"
    VOLCANIC_ERUPTION = "volcanic_eruption"
    STORM = "storm"
    BLIZZARD = "blizzard"
    LANDSLIDE = "landslide"
    EARTHQUAKE = "earthquake"
    ALGAL_BLOOM = "algal_bloom"
    MIGRATION = "migration"
    POLLINATION_BLOOM = "pollination_bloom"


class Severity(str, Enum):
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CATASTROPHIC = "catastrophic"


class NaturalEvent(WorldBenchModel):
    """A recurring or one-off natural disturbance and what it affects."""

    id: EntityId
    name: str = Field(min_length=1, max_length=120)
    type: EventType
    severity: Severity = Field(default=Severity.MODERATE)
    recurrence_years: float | None = Field(
        default=None,
        gt=0.0,
        description="Average years between occurrences. Null for one-off events.",
    )
    affected_region_ids: list[EntityId] = Field(
        default_factory=list,
        description="Layout regions the event affects.",
    )
    affected_biome_ids: list[EntityId] = Field(
        default_factory=list,
        description="Biomes the event affects.",
    )
    triggers: list[EntityId] = Field(
        default_factory=list,
        description="Ids of terrain/water entities that cause this event "
        "(e.g. a volcano triggering an eruption, a river triggering a flood).",
    )
    description: str = Field(default="", max_length=2000)

    @field_validator("id")
    @classmethod
    def _id_format(cls, v: str) -> str:
        return validate_id_format(v)

    @field_validator("affected_region_ids", "affected_biome_ids", "triggers")
    @classmethod
    def _ref_id_format(cls, v: list[str]) -> list[str]:
        for item in v:
            validate_id_format(item)
        return v

    @model_validator(mode="after")
    def _affects_something(self) -> "NaturalEvent":
        if not self.affected_region_ids and not self.affected_biome_ids:
            raise ValueError(
                f"natural_event {self.id}: must affect at least one region or biome"
            )
        return self


class NaturalEvents(WorldBenchModel):
    """All natural events in the world."""

    events: list[NaturalEvent] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids(self) -> "NaturalEvents":
        ids = [e.id for e in self.events]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate natural event ids: {sorted(dupes)}")
        return self
