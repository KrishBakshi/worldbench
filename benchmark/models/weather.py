"""Weather: prevailing atmospheric patterns and per-biome climate behavior."""

from __future__ import annotations

from enum import Enum

from pydantic import Field, field_validator, model_validator

from .common import EntityId, WorldBenchModel, validate_id_format


class PrecipitationType(str, Enum):
    NONE = "none"
    RAIN = "rain"
    SNOW = "snow"
    SLEET = "sleet"
    HAIL = "hail"
    MIST = "mist"
    ASH = "ash"


class WindPattern(WorldBenchModel):
    """A prevailing wind affecting weather and pollination/migration."""

    id: EntityId
    name: str = Field(min_length=1, max_length=120)
    direction: str = Field(
        description="Cardinal/intercardinal bearing the wind blows toward "
        "(e.g. 'northeast')."
    )
    strength: float = Field(ge=0.0, le=1.0, description="Normalized wind strength.")

    @field_validator("id")
    @classmethod
    def _id_format(cls, v: str) -> str:
        return validate_id_format(v)


class BiomeWeather(WorldBenchModel):
    """Prevailing weather behavior for a specific biome."""

    biome_id: EntityId
    avg_temperature: float = Field(
        description="Average temperature in arbitrary but consistent units."
    )
    precipitation: PrecipitationType
    annual_precipitation: float = Field(
        ge=0.0,
        description="Relative annual precipitation (0 for none). Must be 0 for "
        "'none' precipitation and > 0 otherwise.",
    )
    storm_frequency: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Normalized likelihood of storms.",
    )

    @field_validator("biome_id")
    @classmethod
    def _id_format(cls, v: str) -> str:
        return validate_id_format(v)

    @model_validator(mode="after")
    def _precip_consistency(self) -> "BiomeWeather":
        if self.precipitation is PrecipitationType.NONE and self.annual_precipitation > 0:
            raise ValueError(
                f"biome_weather {self.biome_id}: precipitation 'none' but "
                f"annual_precipitation is {self.annual_precipitation}"
            )
        if self.precipitation is not PrecipitationType.NONE and self.annual_precipitation == 0:
            raise ValueError(
                f"biome_weather {self.biome_id}: precipitation "
                f"'{self.precipitation.value}' requires annual_precipitation > 0"
            )
        return self


class Weather(WorldBenchModel):
    """Global winds and per-biome climate patterns."""

    prevailing_winds: list[WindPattern] = Field(default_factory=list)
    biome_weather: list[BiomeWeather] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique(self) -> "Weather":
        wind_ids = [w.id for w in self.prevailing_winds]
        wdupes = {i for i in wind_ids if wind_ids.count(i) > 1}
        if wdupes:
            raise ValueError(f"duplicate wind ids: {sorted(wdupes)}")
        biome_ids = [b.biome_id for b in self.biome_weather]
        bdupes = {i for i in biome_ids if biome_ids.count(i) > 1}
        if bdupes:
            raise ValueError(f"duplicate biome_weather entries: {sorted(bdupes)}")
        return self
