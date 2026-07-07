"""Seasons: the world's cyclical calendar and per-season ecological modifiers."""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from .common import EntityId, WorldBenchModel, validate_id_format


class Season(WorldBenchModel):
    """One phase of the world's annual cycle."""

    id: EntityId
    name: str = Field(min_length=1, max_length=120)
    order: int = Field(ge=0, description="Position in the annual cycle, starting at 0.")
    length_fraction: float = Field(
        gt=0.0,
        le=1.0,
        description="Fraction of the full year this season occupies. Season "
        "length_fractions across the world must sum to ~1.0.",
    )
    temperature_modifier: float = Field(
        default=0.0,
        description="Additive offset applied to biome average temperatures.",
    )
    precipitation_modifier: float = Field(
        default=1.0,
        ge=0.0,
        description="Multiplier applied to biome annual precipitation.",
    )
    triggers_event_ids: list[EntityId] = Field(
        default_factory=list,
        description="Natural event ids that characteristically occur this season "
        "(e.g. spring floods, dry-season wildfires).",
    )
    description: str = Field(default="", max_length=2000)

    @field_validator("id")
    @classmethod
    def _id_format(cls, v: str) -> str:
        return validate_id_format(v)

    @field_validator("triggers_event_ids")
    @classmethod
    def _ref_id_format(cls, v: list[str]) -> list[str]:
        for item in v:
            validate_id_format(item)
        return v


class Seasons(WorldBenchModel):
    """The full seasonal cycle of the world."""

    cycle: list[Season] = Field(
        min_length=1,
        description="Ordered seasons. A world with no seasonality may declare a "
        "single perpetual season.",
    )

    @model_validator(mode="after")
    def _consistency(self) -> "Seasons":
        ids = [s.id for s in self.cycle]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate season ids: {sorted(dupes)}")
        orders = sorted(s.order for s in self.cycle)
        if orders != list(range(len(self.cycle))):
            raise ValueError(
                "season 'order' values must be contiguous starting at 0 "
                f"(got {orders})"
            )
        total = sum(s.length_fraction for s in self.cycle)
        if not (0.98 <= total <= 1.02):
            raise ValueError(
                f"season length_fractions must sum to ~1.0 (got {total:.3f})"
            )
        return self
