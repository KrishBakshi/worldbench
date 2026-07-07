"""Load the YAML ontology into a queryable knowledge graph.

The :class:`KnowledgeGraph` is the single source of ecological truth that
validators and metrics consult. It maps the schema's enum values (e.g. the
biome type ``temperate_forest``) onto ontology *concepts* (``forest``) via each
file's ``aliases`` list, then answers questions like "can a cactus grow in this
biome?" or "may a river flow into a lake?".

Design notes
------------
* The graph is built once and cached (:func:`load_knowledge`); it is read-only.
* Queries accept either a concept key or any of its aliases, so callers can pass
  raw schema enum values without translating first.
* Unknown concepts fail *open* for ``supports`` checks that would otherwise be
  unfair to penalize when the ontology simply lacks coverage — callers can opt
  into strict behavior via ``strict=True``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import networkx as nx
import yaml

KNOWLEDGE_DIR = Path(__file__).parent


@dataclass(frozen=True)
class Concept:
    """A single ontology concept parsed from one YAML file."""

    key: str
    kind: str
    aliases: frozenset[str]
    supports_flora: frozenset[str]
    supports_fauna: frozenset[str]
    supports_features: frozenset[str]
    requires_moisture: frozenset[str]
    requires_temperature: frozenset[str]
    adjacent_to: frozenset[str]
    incompatible_with: frozenset[str]
    flows_to: frozenset[str]
    produces_water: frozenset[str]
    produces_events: frozenset[str]
    terminal: bool = False
    raw: dict = field(default_factory=dict, compare=False)


def _as_set(value) -> frozenset[str]:
    if value is None:
        return frozenset()
    if isinstance(value, str):
        return frozenset({value})
    return frozenset(value)


def _parse_concept(data: dict) -> Concept:
    supports = data.get("supports") or {}
    requires = data.get("requires") or {}
    produces = data.get("produces") or {}
    return Concept(
        key=data["concept"],
        kind=data.get("kind", "unknown"),
        aliases=_as_set(data.get("aliases")) | {data["concept"]},
        supports_flora=_as_set(supports.get("flora")),
        supports_fauna=_as_set(supports.get("fauna")),
        supports_features=_as_set(supports.get("features")),
        requires_moisture=_as_set(requires.get("moisture")),
        requires_temperature=_as_set(requires.get("temperature")),
        adjacent_to=_as_set(data.get("adjacent_to")),
        incompatible_with=_as_set(data.get("incompatible_with")),
        flows_to=_as_set(data.get("flows_to")),
        produces_water=_as_set(produces.get("water")),
        produces_events=_as_set(produces.get("events")),
        terminal=bool(data.get("terminal", False)),
        raw=data,
    )


class KnowledgeGraph:
    """Queryable ecological ontology assembled from the YAML concept files."""

    def __init__(self, concepts: list[Concept]):
        self._concepts: dict[str, Concept] = {c.key: c for c in concepts}
        # Map every alias (and key) to its owning concept for fast resolution.
        self._alias_index: dict[str, Concept] = {}
        for concept in concepts:
            for alias in concept.aliases:
                self._alias_index[alias] = concept
        self._graph = self._build_graph(concepts)

    # -- construction ----------------------------------------------------
    @staticmethod
    def _build_graph(concepts: list[Concept]) -> nx.DiGraph:
        g: nx.DiGraph = nx.DiGraph()
        for c in concepts:
            g.add_node(c.key, kind=c.kind)
        for c in concepts:
            for other in c.adjacent_to:
                g.add_edge(c.key, other, relation="adjacent_to")
            for other in c.flows_to:
                g.add_edge(c.key, other, relation="flows_to")
            for other in c.incompatible_with:
                g.add_edge(c.key, other, relation="incompatible_with")
        return g

    # -- resolution ------------------------------------------------------
    def resolve(self, name: str) -> Concept | None:
        """Return the concept owning ``name`` (a key or alias), or None."""
        return self._alias_index.get(name)

    @property
    def graph(self) -> nx.DiGraph:
        return self._graph

    @property
    def concepts(self) -> list[Concept]:
        return list(self._concepts.values())

    def known(self, name: str) -> bool:
        return name in self._alias_index

    # -- support queries -------------------------------------------------
    def supports_flora(self, biome: str, flora_category: str, *, strict: bool = False) -> bool:
        """Whether ``biome`` can sustain the given flora category."""
        concept = self.resolve(biome)
        if concept is None:
            return not strict
        return flora_category in concept.supports_flora

    def supports_fauna(self, biome: str, fauna_category: str, *, strict: bool = False) -> bool:
        """Whether ``biome`` can sustain the given fauna category."""
        concept = self.resolve(biome)
        if concept is None:
            return not strict
        return fauna_category in concept.supports_fauna

    def supports_feature(self, concept_name: str, feature: str) -> bool:
        concept = self.resolve(concept_name)
        return bool(concept and feature in concept.supports_features)

    # -- climate queries -------------------------------------------------
    def allows_moisture(self, concept_name: str, moisture: str, *, strict: bool = False) -> bool:
        concept = self.resolve(concept_name)
        if concept is None or not concept.requires_moisture:
            return not strict if concept is None else True
        return moisture in concept.requires_moisture

    def allows_temperature(
        self, concept_name: str, temperature: str, *, strict: bool = False
    ) -> bool:
        concept = self.resolve(concept_name)
        if concept is None or not concept.requires_temperature:
            return not strict if concept is None else True
        return temperature in concept.requires_temperature

    # -- adjacency / flow queries ---------------------------------------
    def may_be_adjacent(self, a: str, b: str) -> bool:
        """Whether two concepts may plausibly share a border.

        True when either lists the other in ``adjacent_to`` (adjacency is treated
        symmetrically) and neither declares the other ``incompatible_with``.
        """
        ca, cb = self.resolve(a), self.resolve(b)
        if ca is None or cb is None:
            return True  # unknown concept: don't penalize
        if cb.key in ca.incompatible_with or ca.key in cb.incompatible_with:
            return False
        if not ca.adjacent_to and not cb.adjacent_to:
            return True
        return cb.key in ca.adjacent_to or ca.key in cb.adjacent_to

    def incompatible(self, a: str, b: str) -> bool:
        ca, cb = self.resolve(a), self.resolve(b)
        if ca is None or cb is None:
            return False
        return cb.key in ca.incompatible_with or ca.key in cb.incompatible_with

    def may_flow_to(self, source_water: str, target_water: str, *, strict: bool = False) -> bool:
        """Whether ``source_water`` may flow into ``target_water``."""
        cs = self.resolve(source_water)
        ct = self.resolve(target_water)
        if cs is None or ct is None:
            return not strict
        if cs.terminal:
            return False  # oceans/seas do not flow onward
        if not cs.flows_to:
            return not strict
        return ct.key in cs.flows_to

    def is_terminal_water(self, water: str) -> bool:
        concept = self.resolve(water)
        return bool(concept and (concept.terminal or not concept.flows_to))

    def produces_water(self, terrain: str) -> frozenset[str]:
        concept = self.resolve(terrain)
        return concept.produces_water if concept else frozenset()

    def produces_events(self, terrain: str) -> frozenset[str]:
        concept = self.resolve(terrain)
        return concept.produces_events if concept else frozenset()


def _load_concepts() -> list[Concept]:
    concepts: list[Concept] = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not data or "concept" not in data:
            continue
        concepts.append(_parse_concept(data))
    return concepts


@lru_cache(maxsize=1)
def load_knowledge() -> KnowledgeGraph:
    """Load (and cache) the knowledge graph from the packaged YAML files."""
    return KnowledgeGraph(_load_concepts())
