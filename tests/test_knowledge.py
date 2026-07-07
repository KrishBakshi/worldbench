"""Tests for the ecological knowledge base and its query API."""

from __future__ import annotations

from benchmark.knowledge import KnowledgeGraph, load_knowledge


def test_knowledge_loads_and_caches() -> None:
    kg1 = load_knowledge()
    kg2 = load_knowledge()
    assert kg1 is kg2  # lru_cache returns the same instance
    assert isinstance(kg1, KnowledgeGraph)
    assert len(kg1.concepts) >= 10


def test_alias_resolution_maps_enum_values_to_concepts() -> None:
    kg = load_knowledge()
    assert kg.resolve("temperate_forest").key == "forest"
    assert kg.resolve("rainforest").key == "forest"
    assert kg.resolve("deep_ocean").key == "marine"
    assert kg.resolve("tundra").key == "alpine"
    assert kg.resolve("nonexistent_biome") is None


def test_supports_flora_rules() -> None:
    kg = load_knowledge()
    assert kg.supports_flora("desert", "cactus")
    assert not kg.supports_flora("desert", "coral")
    assert kg.supports_flora("temperate_forest", "tree")
    assert kg.supports_flora("coral_reef", "coral")


def test_supports_fauna_rules() -> None:
    kg = load_knowledge()
    assert kg.supports_fauna("deep_ocean", "fish")
    assert not kg.supports_fauna("desert", "fish")
    assert kg.supports_fauna("temperate_forest", "bird")


def test_climate_requirements() -> None:
    kg = load_knowledge()
    assert kg.allows_temperature("desert", "hot")
    assert not kg.allows_temperature("desert", "polar")
    assert kg.allows_moisture("desert", "arid")
    assert not kg.allows_moisture("desert", "saturated")


def test_adjacency_and_incompatibility() -> None:
    kg = load_knowledge()
    assert kg.may_be_adjacent("beach", "coastal_ocean")
    assert not kg.may_be_adjacent("desert", "rainforest")
    assert kg.incompatible("desert", "rainforest")
    assert not kg.incompatible("grassland", "temperate_forest")


def test_water_flow_rules() -> None:
    kg = load_knowledge()
    assert kg.may_flow_to("river", "lake")
    assert kg.may_flow_to("stream", "ocean")
    assert kg.is_terminal_water("ocean")
    assert not kg.may_flow_to("ocean", "lake")  # terminal bodies do not flow onward


def test_terrain_produces_water_and_events() -> None:
    kg = load_knowledge()
    assert "glacier_melt" in kg.produces_water("mountain")
    assert "volcanic_eruption" in kg.produces_events("volcano")


def test_every_yaml_concept_has_unique_aliases() -> None:
    kg = load_knowledge()
    seen: dict[str, str] = {}
    for concept in kg.concepts:
        for alias in concept.aliases:
            assert alias not in seen, f"alias {alias} claimed by {seen.get(alias)} and {concept.key}"
            seen[alias] = concept.key
