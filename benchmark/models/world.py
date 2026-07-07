"""The top-level :class:`World` model composing every schema section.

A :class:`World` is the single artifact a model under test must produce and the
single input every validator and metric consumes. It intentionally performs
only *local* structural validation (shapes, ranges, per-section invariants);
*cross-section* checks (does every referenced id exist? does water flow
downhill globally? is the food web connected?) live in the validators package
so that a structurally-valid-but-ecologically-broken world still parses and can
be scored.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field

from .biomes import Biomes
from .common import WorldBenchModel
from .fauna import Fauna
from .flora import Flora
from .interactions import Interactions
from .layout import WorldLayout
from .metadata import WorldMetadata
from .natural_events import NaturalEvents
from .seasons import Seasons
from .simulation import Simulation
from .terrain import Terrain
from .water import WaterSystems
from .weather import Weather


class World(WorldBenchModel):
    """A complete WorldBench world."""

    metadata: WorldMetadata
    layout: WorldLayout
    terrain: Terrain
    water: WaterSystems
    biomes: Biomes
    flora: Flora
    fauna: Fauna
    interactions: Interactions = Field(default_factory=Interactions)
    weather: Weather
    seasons: Seasons
    natural_events: NaturalEvents = Field(default_factory=NaturalEvents)
    simulation: Simulation = Field(default_factory=Simulation)

    @classmethod
    def from_json(cls, data: str | bytes) -> "World":
        """Parse and validate a world from a JSON string."""
        return cls.model_validate_json(data)

    @classmethod
    def from_file(cls, path: str | Path) -> "World":
        """Parse and validate a world from a JSON file."""
        return cls.model_validate_json(Path(path).read_bytes())

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialize the world to a JSON string."""
        return self.model_dump_json(indent=indent)

    def save(self, path: str | Path) -> None:
        """Write the world to a JSON file."""
        Path(path).write_text(self.to_json(), encoding="utf-8")

    def all_ids(self) -> set[str]:
        """Collect every entity id declared anywhere in the world.

        Used by referential-integrity validators to confirm that every
        cross-section id reference resolves to a real entity.
        """
        ids: set[str] = {self.metadata.id}
        ids.update(r.id for r in self.layout.regions)
        ids.update(f.id for f in self.terrain.features)
        ids.update(b.id for b in self.water.bodies)
        ids.update(z.id for z in self.biomes.zones)
        ids.update(s.id for s in self.flora.species)
        ids.update(s.id for s in self.fauna.species)
        ids.update(e.id for e in self.interactions.edges)
        ids.update(w.id for w in self.weather.prevailing_winds)
        ids.update(s.id for s in self.seasons.cycle)
        ids.update(e.id for e in self.natural_events.events)
        ids.update(d.id for d in self.simulation.dynamics)
        return ids


def load_world(path: str | Path) -> World:
    """Convenience loader used throughout the runner and CLI."""
    return World.from_file(path)


def dump_schema(indent: int = 2) -> str:
    """Return the JSON Schema for :class:`World` as a formatted string."""
    return json.dumps(World.model_json_schema(), indent=indent)
