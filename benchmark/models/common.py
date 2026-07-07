"""Shared primitives used across every WorldBench schema section.

All spatial coordinates are expressed in abstract world units (not meters) on a
bounded coordinate plane defined by ``WorldLayout.bounds``. Elevation is a
signed float where 0.0 is nominal sea level for non-floating worlds, or the
base of the landmass for floating worlds.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


class WorldBenchModel(BaseModel):
    """Base class for all WorldBench schema models.

    Forbids unknown fields so that malformed LLM output fails schema
    validation loudly instead of silently dropping data.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


EntityId = Annotated[
    str,
    Field(
        min_length=2,
        max_length=64,
        description="Stable, lowercase snake_case identifier unique within the world "
        "(e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference "
        "mechanism for graph relationships between entities.",
    ),
]


def validate_id_format(value: str) -> str:
    if not _ID_PATTERN.match(value):
        raise ValueError(
            f"id {value!r} must be lowercase snake_case, start with a letter, "
            "and be 2-64 characters long"
        )
    return value


class Coordinate2D(WorldBenchModel):
    """A location on the world's horizontal plane, in world units."""

    x: float = Field(description="Position along the west-to-east axis.")
    y: float = Field(description="Position along the south-to-north axis.")


class Coordinate3D(WorldBenchModel):
    """A location in three-dimensional world space, in world units."""

    x: float = Field(description="Position along the west-to-east axis.")
    y: float = Field(description="Position along the south-to-north axis.")
    elevation: float = Field(
        description="Height above the world's reference elevation (0.0)."
    )


class BoundingRegion(WorldBenchModel):
    """An axis-aligned or polygonal footprint on the world plane.

    A polygon (``vertices`` with 3+ points) is preferred for irregular natural
    shapes; a simple axis-aligned box may be used for coarse regions.
    """

    min_x: float
    min_y: float
    max_x: float
    max_y: float
    vertices: list[Coordinate2D] | None = Field(
        default=None,
        description="Ordered polygon vertices (closed ring implied) for an "
        "irregular footprint. When omitted, the bounding box above is used.",
    )

    @field_validator("vertices")
    @classmethod
    def _min_polygon_points(cls, v: list[Coordinate2D] | None) -> list[Coordinate2D] | None:
        if v is not None and len(v) < 3:
            raise ValueError("a polygon must have at least 3 vertices")
        return v


class Rarity(str, Enum):
    ABUNDANT = "abundant"
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    KEYSTONE = "keystone"


class ConservationTrend(str, Enum):
    GROWING = "growing"
    STABLE = "stable"
    DECLINING = "declining"
    CRITICAL = "critical"
