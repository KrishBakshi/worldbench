"""Terrain features: mountains, plains, cliffs, dunes, volcanoes, and their elevations."""

from __future__ import annotations

from enum import Enum

from pydantic import Field, field_validator, model_validator

from .common import BoundingRegion, Coordinate2D, EntityId, WorldBenchModel, validate_id_format


class TerrainType(str, Enum):
    MOUNTAIN = "mountain"
    MOUNTAIN_RANGE = "mountain_range"
    HILL = "hill"
    PLATEAU = "plateau"
    PLAIN = "plain"
    VALLEY = "valley"
    CANYON = "canyon"
    CLIFF = "cliff"
    DUNE_FIELD = "dune_field"
    MESA = "mesa"
    VOLCANO = "volcano"
    CRATER = "crater"
    GLACIER = "glacier"
    CAVE_SYSTEM = "cave_system"
    BASIN = "basin"
    FLOATING_FRAGMENT = "floating_fragment"


class VolcanicActivity(str, Enum):
    EXTINCT = "extinct"
    DORMANT = "dormant"
    ACTIVE = "active"
    ERUPTING = "erupting"


class TerrainFeature(WorldBenchModel):
    """A single landform anchored to a region."""

    id: EntityId
    name: str = Field(min_length=1, max_length=120)
    type: TerrainType
    region_id: EntityId = Field(
        description="Id of the layout region this feature primarily occupies."
    )
    footprint: BoundingRegion
    base_elevation: float = Field(
        description="Elevation of the feature's base in world units."
    )
    peak_elevation: float = Field(
        description="Elevation of the feature's highest point. Must be >= "
        "base_elevation."
    )
    slope: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Normalized average steepness: 0 flat, 1 vertical.",
    )
    volcanic_activity: VolcanicActivity | None = Field(
        default=None,
        description="Required for 'volcano' features; must be null otherwise.",
    )
    connected_to: list[EntityId] = Field(
        default_factory=list,
        description="Ids of physically contiguous terrain features (e.g. peaks "
        "within a range, a cliff bounding a plateau).",
    )
    description: str = Field(default="", max_length=2000)

    @field_validator("id", "region_id")
    @classmethod
    def _id_format(cls, v: str) -> str:
        return validate_id_format(v)

    @model_validator(mode="after")
    def _elevation_order(self) -> "TerrainFeature":
        if self.peak_elevation < self.base_elevation:
            raise ValueError(
                f"terrain {self.id}: peak_elevation ({self.peak_elevation}) is "
                f"below base_elevation ({self.base_elevation})"
            )
        if self.type is TerrainType.VOLCANO and self.volcanic_activity is None:
            raise ValueError(f"terrain {self.id}: volcano requires volcanic_activity")
        if self.type is not TerrainType.VOLCANO and self.volcanic_activity is not None:
            raise ValueError(
                f"terrain {self.id}: volcanic_activity only valid on volcanoes"
            )
        return self


class ElevationSample(WorldBenchModel):
    """A sparse sample of the world's height field for coherence checking."""

    position: Coordinate2D
    elevation: float


class Terrain(WorldBenchModel):
    """All landforms in the world plus a sparse elevation field."""

    features: list[TerrainFeature] = Field(min_length=1)
    elevation_samples: list[ElevationSample] = Field(
        default_factory=list,
        description="Optional sparse height-field samples validators use to "
        "cross-check feature elevations and river flow directions.",
    )

    @model_validator(mode="after")
    def _unique_ids(self) -> "Terrain":
        ids = [f.id for f in self.features]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate terrain feature ids: {sorted(dupes)}")
        return self
