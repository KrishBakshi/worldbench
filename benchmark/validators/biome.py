"""Biome validation: climate feasibility, adjacency plausibility, references."""

from __future__ import annotations

from ..knowledge import load_knowledge
from ..models import World
from ..results import Severity, ValidationResult
from .base import FindingCollector

NAME = "biome"
PREFIX = "BIO"


def validate(world: World) -> ValidationResult:
    c = FindingCollector(NAME, PREFIX)
    kg = load_knowledge()
    biome_ids = {b.id for b in world.biomes.zones}
    region_ids = {r.id for r in world.layout.regions}
    terrain_ids = {f.id for f in world.terrain.features}
    water_ids = {b.id for b in world.water.bodies}
    biomes = {b.id: b for b in world.biomes.zones}

    for biome in world.biomes.zones:
        btype = biome.type.value

        # Climate feasibility against the knowledge base.
        c.check(
            kg.allows_temperature(btype, biome.temperature.value),
            f"biome '{biome.id}' ({btype}) cannot exist in temperature band "
            f"'{biome.temperature.value}'",
            entity_id=biome.id,
        )
        c.check(
            kg.allows_moisture(btype, biome.moisture.value),
            f"biome '{biome.id}' ({btype}) cannot exist at moisture level "
            f"'{biome.moisture.value}'",
            entity_id=biome.id,
        )

        # Cross-references resolve.
        for rid in biome.region_ids:
            c.check(
                rid in region_ids,
                f"biome '{biome.id}' references unknown region '{rid}'",
                entity_id=biome.id,
            )
        for tid in biome.terrain_feature_ids:
            c.check(
                tid in terrain_ids,
                f"biome '{biome.id}' references unknown terrain '{tid}'",
                entity_id=biome.id,
            )
        for wid in biome.water_body_ids:
            c.check(
                wid in water_ids,
                f"biome '{biome.id}' references unknown water body '{wid}'",
                entity_id=biome.id,
            )

        # Adjacency: symmetric, plausible, not incompatible.
        for other in biome.adjacent_to:
            if not c.check(
                other in biome_ids,
                f"biome '{biome.id}' adjacent to unknown biome '{other}'",
                entity_id=biome.id,
            ):
                continue
            back = biomes[other]
            c.check(
                biome.id in back.adjacent_to,
                f"biome adjacency not symmetric: '{biome.id}' -> '{other}'",
                severity=Severity.WARNING,
                entity_id=biome.id,
            )
            c.check(
                not kg.incompatible(btype, back.type.value),
                f"biomes '{biome.id}' ({btype}) and '{other}' ({back.type.value}) "
                "should not be directly adjacent",
                severity=Severity.WARNING,
                entity_id=biome.id,
            )

    return c.result()
