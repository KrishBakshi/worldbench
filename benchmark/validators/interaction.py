"""Interaction validation: endpoint resolution and type-appropriate wiring."""

from __future__ import annotations

from ..models import InteractionType, World
from ..results import Severity, ValidationResult
from .base import FindingCollector

NAME = "interaction"
PREFIX = "INT"


def validate(world: World) -> ValidationResult:
    c = FindingCollector(NAME, PREFIX)
    fauna_ids = {f.id for f in world.fauna.species}
    flora_ids = {f.id for f in world.flora.species}
    biome_ids = {b.id for b in world.biomes.zones}
    region_ids = {r.id for r in world.layout.regions}
    all_ids = world.all_ids()

    seen: set[tuple[str, str, str]] = set()
    for edge in world.interactions.edges:
        src_ok = c.check(
            edge.source_id in all_ids,
            f"interaction '{edge.id}' has unknown source '{edge.source_id}'",
            entity_id=edge.id,
        )
        tgt_ok = c.check(
            edge.target_id in all_ids,
            f"interaction '{edge.id}' has unknown target '{edge.target_id}'",
            entity_id=edge.id,
        )
        if not (src_ok and tgt_ok):
            continue

        signature = (edge.type.value, edge.source_id, edge.target_id)
        c.check(
            signature not in seen,
            f"duplicate interaction: {edge.type.value} {edge.source_id} -> "
            f"{edge.target_id}",
            severity=Severity.WARNING,
            entity_id=edge.id,
        )
        seen.add(signature)

        _check_endpoints(c, edge, fauna_ids, flora_ids, biome_ids, region_ids)

    return c.result()


def _check_endpoints(c, edge, fauna_ids, flora_ids, biome_ids, region_ids) -> None:
    t = edge.type
    src, tgt = edge.source_id, edge.target_id
    if t is InteractionType.PREDATION:
        c.check(
            src in fauna_ids and tgt in fauna_ids,
            f"predation '{edge.id}' must connect fauna to fauna",
            entity_id=edge.id,
        )
    elif t in {InteractionType.HERBIVORY, InteractionType.SEED_DISPERSAL}:
        c.check(
            src in fauna_ids and tgt in flora_ids,
            f"{t.value} '{edge.id}' must connect fauna to flora",
            entity_id=edge.id,
        )
    elif t is InteractionType.POLLINATION:
        c.check(
            src in fauna_ids and (tgt in flora_ids or tgt in biome_ids),
            f"pollination '{edge.id}' must connect a pollinator to flora",
            entity_id=edge.id,
        )
    elif t is InteractionType.MIGRATION:
        c.check(
            src in fauna_ids and (tgt in biome_ids or tgt in region_ids),
            f"migration '{edge.id}' must connect fauna to a biome or region",
            entity_id=edge.id,
        )
