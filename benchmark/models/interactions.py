"""Ecological interactions: the explicit relationship graph between species.

While fauna diets and flora pollination modes imply many relationships, the
interactions section makes the ecological web first-class so validators can
score food-chain depth, connectivity, and realism directly.
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field, field_validator, model_validator

from .common import EntityId, WorldBenchModel, validate_id_format


class InteractionType(str, Enum):
    PREDATION = "predation"
    HERBIVORY = "herbivory"
    POLLINATION = "pollination"
    SEED_DISPERSAL = "seed_dispersal"
    MIGRATION = "migration"
    SYMBIOSIS = "symbiosis"
    PARASITISM = "parasitism"
    COMPETITION = "competition"
    DECOMPOSITION = "decomposition"
    NESTING = "nesting"
    CAMOUFLAGE_HOST = "camouflage_host"


class EcologicalInteraction(WorldBenchModel):
    """A directed ecological relationship between two entities.

    ``source_id`` is the actor (predator, pollinator, migrant) and
    ``target_id`` the recipient (prey, flower, destination biome). Both must
    reference existing flora, fauna, or biome ids as appropriate to the type.
    """

    id: EntityId
    type: InteractionType
    source_id: EntityId = Field(description="The acting entity id.")
    target_id: EntityId = Field(description="The receiving entity id.")
    strength: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Relative importance of this interaction to the ecosystem.",
    )
    seasonal: bool = Field(
        default=False,
        description="Whether the interaction only occurs in certain seasons "
        "(e.g. migration, seasonal pollination).",
    )
    description: str = Field(default="", max_length=2000)

    @field_validator("id", "source_id", "target_id")
    @classmethod
    def _id_format(cls, v: str) -> str:
        return validate_id_format(v)

    @model_validator(mode="after")
    def _no_self_loop(self) -> "EcologicalInteraction":
        if self.source_id == self.target_id:
            raise ValueError(
                f"interaction {self.id}: source and target must differ"
            )
        return self


class Interactions(WorldBenchModel):
    """The full ecological interaction web."""

    edges: list[EcologicalInteraction] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids(self) -> "Interactions":
        ids = [e.id for e in self.edges]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate interaction ids: {sorted(dupes)}")
        return self
