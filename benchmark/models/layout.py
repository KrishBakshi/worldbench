"""World layout: global topology, bounds, and named regions.

The layout is the spatial skeleton every other section hangs off. Regions are
coarse named areas (e.g. 'northern_range', 'central_plains') that biomes,
terrain features, and water bodies reference by id, forming the base of the
world graph.
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field, field_validator, model_validator

from .common import BoundingRegion, EntityId, WorldBenchModel, validate_id_format


class WorldTopology(str, Enum):
    """The global shape of the world."""

    CONTINENT = "continent"
    ISLAND = "island"
    ARCHIPELAGO = "archipelago"
    FLOATING_ISLAND = "floating_island"
    FLOATING_ARCHIPELAGO = "floating_archipelago"
    RING = "ring"
    CAVERN = "cavern"


class EdgeType(str, Enum):
    """What happens at the boundary of the world."""

    OCEAN = "ocean"
    VOID = "void"
    ICE_WALL = "ice_wall"
    WRAPPING = "wrapping"
    CLIFF = "cliff"


class CardinalDirection(str, Enum):
    NORTH = "north"
    NORTHEAST = "northeast"
    EAST = "east"
    SOUTHEAST = "southeast"
    SOUTH = "south"
    SOUTHWEST = "southwest"
    WEST = "west"
    CENTER = "center"


class Region(WorldBenchModel):
    """A coarse named area of the world referenced by other entities."""

    id: EntityId
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    footprint: BoundingRegion = Field(
        description="Spatial extent of the region on the world plane."
    )
    direction: CardinalDirection = Field(
        description="Approximate position of the region relative to the world center."
    )
    adjacent_to: list[EntityId] = Field(
        default_factory=list,
        description="Ids of regions sharing a border with this one. Adjacency "
        "must be symmetric: if A lists B, B must list A.",
    )

    @field_validator("id")
    @classmethod
    def _id_format(cls, v: str) -> str:
        return validate_id_format(v)


class WorldLayout(WorldBenchModel):
    """Global spatial structure of the world."""

    topology: WorldTopology
    edge_type: EdgeType = Field(
        description="Boundary behavior. Floating topologies must use 'void' or "
        "'cliff'; grounded topologies typically use 'ocean'."
    )
    bounds: BoundingRegion = Field(
        description="Overall extent of the world in world units. All entity "
        "coordinates must fall inside these bounds."
    )
    sea_level: float = Field(
        default=0.0,
        description="Elevation of nominal sea level. Water bodies of type "
        "'ocean' sit at this elevation.",
    )
    regions: list[Region] = Field(
        min_length=1,
        description="Named coarse areas that partition the world.",
    )

    @model_validator(mode="after")
    def _unique_region_ids(self) -> "WorldLayout":
        ids = [r.id for r in self.regions]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate region ids: {sorted(dupes)}")
        return self
