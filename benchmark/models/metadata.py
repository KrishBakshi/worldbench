"""World metadata: identity, versioning, and generation provenance."""

from __future__ import annotations

from pydantic import Field, field_validator

from .common import EntityId, WorldBenchModel, validate_id_format

SCHEMA_VERSION = "1.0.0"


class WorldMetadata(WorldBenchModel):
    """Identity and provenance for a generated world."""

    id: EntityId = Field(description="Unique identifier for this world.")
    name: str = Field(
        min_length=1,
        max_length=120,
        description="Human-readable world name (e.g. 'The Shattered Verdance').",
    )
    description: str = Field(
        min_length=1,
        max_length=4000,
        description="Prose summary of the world's character and defining features.",
    )
    schema_version: str = Field(
        default=SCHEMA_VERSION,
        description="WorldBench schema version this document conforms to.",
    )
    seed: int | None = Field(
        default=None,
        description="Optional deterministic seed the generator claims to have used.",
    )
    tags: list[str] = Field(
        default_factory=list,
        max_length=32,
        description="Freeform descriptive tags (e.g. 'floating', 'archipelago', 'volcanic').",
    )

    @field_validator("id")
    @classmethod
    def _id_format(cls, v: str) -> str:
        return validate_id_format(v)
