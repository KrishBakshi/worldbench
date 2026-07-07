"""Constraint validation: WorldBench scope enforcement + per-task constraints.

WorldBench worlds are *natural* environments. This validator scans all
human-readable text for a curated lexicon of civilization/anthropogenic terms
and rejects any world that smuggles in cities, roads, people, politics, and the
like. It also enforces optional per-task quantitative constraints supplied by a
task's ``constraints.yaml``.
"""

from __future__ import annotations

import re

from ..models import World
from ..results import Severity, ValidationResult
from .base import FindingCollector

NAME = "constraint"
PREFIX = "CON"

#: Terms that signal humans, civilization, or artificial structures. Matched as
#: whole words, case-insensitively. Kept deliberately conservative to avoid
#: false positives on natural features (e.g. "ford" of a river is allowed).
BANNED_TERMS: frozenset[str] = frozenset(
    {
        "human", "humans", "person", "people", "villager", "village", "town",
        "city", "cities", "citizen", "civilization", "civilisation", "kingdom",
        "king", "queen", "empire", "nation", "country", "government", "politics",
        "political", "economy", "economic", "market", "trade", "currency", "money",
        "road", "highway", "street", "bridge", "building", "house", "hut", "cabin",
        "castle", "fortress", "temple", "church", "shrine", "monastery",
        "farm", "farmland", "plantation", "orchard", "quarry",
        "factory", "mill", "canal", "harbor", "harbour",
        "vehicle", "machine", "army", "soldier",
        "weapon", "sword", "fence", "settlement", "colony",
        "tribe", "clan", "religion", "festival", "monument", "statue",
    }
)

_WORD_RE = {term: re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE) for term in BANNED_TERMS}


def _iter_text(world: World):
    """Yield (label, text) pairs for every human-readable string in the world."""
    yield "metadata.name", world.metadata.name
    yield "metadata.description", world.metadata.description
    for tag in world.metadata.tags:
        yield "metadata.tags", tag
    for r in world.layout.regions:
        yield f"region:{r.id}", f"{r.name} {r.description}"
    for f in world.terrain.features:
        yield f"terrain:{f.id}", f"{f.name} {f.description}"
    for b in world.water.bodies:
        yield f"water:{b.id}", f"{b.name} {b.description}"
    for z in world.biomes.zones:
        yield f"biome:{z.id}", f"{z.name} {z.description}"
    for s in world.flora.species:
        yield f"flora:{s.id}", f"{s.name} {s.description}"
    for s in world.fauna.species:
        yield f"fauna:{s.id}", f"{s.name} {s.description}"
    for e in world.natural_events.events:
        yield f"event:{e.id}", f"{e.name} {e.description}"
    for d in world.simulation.dynamics:
        yield f"dynamic:{d.id}", f"{d.name} {d.description}"


def validate(world: World, constraints: dict | None = None) -> ValidationResult:
    c = FindingCollector(NAME, PREFIX)

    # Scope: no civilization/human content anywhere in the text.
    extra_forbidden = set((constraints or {}).get("forbidden_terms", []))
    for label, text in _iter_text(world):
        if not text:
            continue
        for term, pattern in _WORD_RE.items():
            if pattern.search(text):
                c.check(
                    False,
                    f"forbidden civilization term '{term}' found in {label}: "
                    f"WorldBench worlds must be purely natural",
                    path=label,
                )
        for term in extra_forbidden:
            if re.search(rf"\b{re.escape(term)}\b", text, re.IGNORECASE):
                c.check(
                    False,
                    f"task-forbidden term '{term}' found in {label}",
                    path=label,
                )

    # Per-task quantitative constraints.
    if constraints:
        _check_quantitative(c, world, constraints)
    else:
        # Record a passing check so the validator always reports activity.
        c.check(True, "no per-task constraints supplied")

    return c.result()


def _check_quantitative(c, world: World, constraints: dict) -> None:
    counts = {
        "min_biomes": len(world.biomes.zones),
        "min_flora": len(world.flora.species),
        "min_fauna": len(world.fauna.species),
        "min_water_bodies": len(world.water.bodies),
        "min_terrain_features": len(world.terrain.features),
        "min_interactions": len(world.interactions.edges),
    }
    for key, actual in counts.items():
        if key in constraints:
            required = constraints[key]
            c.check(
                actual >= required,
                f"constraint {key}={required} not met (found {actual})",
            )

    required_biome_types = set(constraints.get("required_biome_types", []))
    if required_biome_types:
        present = {b.type.value for b in world.biomes.zones}
        missing = required_biome_types - present
        c.check(
            not missing,
            f"required biome types missing: {sorted(missing)}",
        )

    required_terrain_types = set(constraints.get("required_terrain_types", []))
    if required_terrain_types:
        present = {f.type.value for f in world.terrain.features}
        missing = required_terrain_types - present
        c.check(
            not missing,
            f"required terrain types missing: {sorted(missing)}",
        )

    if "required_topology" in constraints:
        c.check(
            world.layout.topology.value == constraints["required_topology"],
            f"required topology '{constraints['required_topology']}' but found "
            f"'{world.layout.topology.value}'",
        )
