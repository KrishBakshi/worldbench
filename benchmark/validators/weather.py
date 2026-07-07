"""Weather validation: biome coverage, precipitation, and wind references."""

from __future__ import annotations

from ..models import PrecipitationType, World
from ..models.biomes import TemperatureBand
from ..results import Severity, ValidationResult
from .base import FindingCollector

NAME = "weather"
PREFIX = "WEA"

_COLD_BANDS = {TemperatureBand.POLAR, TemperatureBand.COLD}


def validate(world: World) -> ValidationResult:
    c = FindingCollector(NAME, PREFIX)
    biomes = {b.id: b for b in world.biomes.zones}
    covered = {bw.biome_id for bw in world.weather.biome_weather}

    for bid in biomes:
        c.check(
            bid in covered,
            f"biome '{bid}' has no weather entry",
            entity_id=bid,
        )

    for bw in world.weather.biome_weather:
        biome = biomes.get(bw.biome_id)
        if not c.check(
            biome is not None,
            f"weather entry references unknown biome '{bw.biome_id}'",
            entity_id=bw.biome_id,
        ):
            continue
        # Precipitation/amount consistency (model also guards this).
        if bw.precipitation is PrecipitationType.NONE:
            c.check(
                bw.annual_precipitation == 0,
                f"biome '{bw.biome_id}' has 'none' precipitation but nonzero amount",
                entity_id=bw.biome_id,
            )
        # Snow only makes sense in cold/polar biomes.
        if bw.precipitation is PrecipitationType.SNOW:
            c.check(
                biome.temperature in _COLD_BANDS,
                f"biome '{bw.biome_id}' has snow but temperature band is "
                f"'{biome.temperature.value}'",
                severity=Severity.WARNING,
                entity_id=bw.biome_id,
            )

    wind_ids = {w.id for w in world.weather.prevailing_winds}
    c.check(
        len(wind_ids) == len(world.weather.prevailing_winds),
        "duplicate prevailing wind ids",
        severity=Severity.WARNING,
    )

    return c.result()
