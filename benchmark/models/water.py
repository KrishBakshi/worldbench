"""Water systems: rivers, lakes, oceans, waterfalls, springs, and flow topology.

Hydrology is modeled as a directed flow graph: every flowing body declares
``source_id``/``flows_to`` references, and validators check that water always
moves downhill and eventually reaches a terminal body (ocean, endorheic lake,
or — on floating worlds — the void edge).
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field, field_validator, model_validator

from .common import (
    BoundingRegion,
    Coordinate2D,
    EntityId,
    WorldBenchModel,
    validate_id_format,
)


class WaterBodyType(str, Enum):
    OCEAN = "ocean"
    SEA = "sea"
    LAKE = "lake"
    POND = "pond"
    RIVER = "river"
    STREAM = "stream"
    WATERFALL = "waterfall"
    SPRING = "spring"
    HOT_SPRING = "hot_spring"
    GLACIER_MELT = "glacier_melt"
    LAGOON = "lagoon"
    WETLAND = "wetland"
    OASIS = "oasis"


class WaterQuality(str, Enum):
    FRESH = "fresh"
    BRACKISH = "brackish"
    SALT = "salt"
    MINERAL = "mineral"
    GLACIAL = "glacial"


#: Types that flow and therefore require a downstream connection.
FLOWING_TYPES = frozenset(
    {WaterBodyType.RIVER, WaterBodyType.STREAM, WaterBodyType.WATERFALL,
     WaterBodyType.GLACIER_MELT}
)

#: Types that may terminate a flow chain.
TERMINAL_TYPES = frozenset(
    {WaterBodyType.OCEAN, WaterBodyType.SEA, WaterBodyType.LAKE,
     WaterBodyType.LAGOON, WaterBodyType.WETLAND, WaterBodyType.POND,
     WaterBodyType.OASIS}
)


class WaterBody(WorldBenchModel):
    """A single water body participating in the world's flow graph."""

    id: EntityId
    name: str = Field(min_length=1, max_length=120)
    type: WaterBodyType
    quality: WaterQuality = Field(default=WaterQuality.FRESH)
    region_ids: list[EntityId] = Field(
        min_length=1,
        description="Layout regions this body passes through or occupies.",
    )
    footprint: BoundingRegion | None = Field(
        default=None,
        description="Extent for area bodies (lakes, oceans, wetlands). Linear "
        "bodies should use 'path' instead.",
    )
    path: list[Coordinate2D] | None = Field(
        default=None,
        description="Ordered course for linear bodies (rivers, streams), from "
        "source to mouth.",
    )
    surface_elevation: float = Field(
        description="Elevation of the water surface at the body's source (for "
        "flowing bodies) or overall (for still bodies)."
    )
    mouth_elevation: float | None = Field(
        default=None,
        description="Elevation where a flowing body ends. Must be <= "
        "surface_elevation (water flows downhill).",
    )
    source_ids: list[EntityId] = Field(
        default_factory=list,
        description="Ids of terrain features or water bodies feeding this one "
        "(e.g. a glacier, spring, or upstream river).",
    )
    flows_to: EntityId | None = Field(
        default=None,
        description="Id of the downstream water body. Required for flowing "
        "types unless the body exits the world at a void/cliff edge "
        "(set exits_world instead).",
    )
    exits_world: bool = Field(
        default=False,
        description="True when the body plunges off the world edge (floating "
        "worlds). Mutually exclusive with flows_to.",
    )
    description: str = Field(default="", max_length=2000)

    @field_validator("id")
    @classmethod
    def _id_format(cls, v: str) -> str:
        return validate_id_format(v)

    @field_validator("region_ids", "source_ids")
    @classmethod
    def _ref_id_format(cls, v: list[str]) -> list[str]:
        for item in v:
            validate_id_format(item)
        return v

    @model_validator(mode="after")
    def _flow_consistency(self) -> "WaterBody":
        if self.flows_to is not None and self.exits_world:
            raise ValueError(
                f"water {self.id}: flows_to and exits_world are mutually exclusive"
            )
        if self.mouth_elevation is not None and self.mouth_elevation > self.surface_elevation:
            raise ValueError(
                f"water {self.id}: mouth_elevation ({self.mouth_elevation}) is above "
                f"surface_elevation ({self.surface_elevation}); water cannot flow uphill"
            )
        if self.type in FLOWING_TYPES and self.path is not None and len(self.path) < 2:
            raise ValueError(f"water {self.id}: a flowing body's path needs >= 2 points")
        return self


class WaterSystems(WorldBenchModel):
    """All water bodies in the world."""

    bodies: list[WaterBody] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_ids(self) -> "WaterSystems":
        ids = [b.id for b in self.bodies]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate water body ids: {sorted(dupes)}")
        return self
