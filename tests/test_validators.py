"""Tests for every WorldBench validator.

The canonical valid world (:func:`benchmark.samples.sample_world`) is the
positive fixture: every validator must pass it. Each validator also gets a
negative case built by mutating a JSON dump of the sample into a world that
still *parses* structurally but violates the cross-section rule the validator
guards, so we can assert the expected error-code prefix is raised.
"""

from __future__ import annotations

import pytest

from benchmark.models import World
from benchmark.samples import sample_world
from benchmark.validators import (
    biome,
    constraint,
    ecology,
    fauna,
    flora,
    hydrology,
    interaction,
    schema_validator,
    simulation,
    topology,
    validate_world,
    weather,
)


@pytest.fixture()
def good() -> World:
    return sample_world()


@pytest.fixture()
def good_dict() -> dict:
    return sample_world().model_dump(mode="json")


def _codes(result) -> set[str]:
    return {f.code[:3] for f in result.findings}


def _error_codes(result) -> set[str]:
    return {f.code[:3] for f in result.errors}


# --------------------------------------------------------------------------
# Positive: every validator passes the canonical world.
# --------------------------------------------------------------------------

def test_full_valid_world_passes(good: World) -> None:
    report = validate_world(good)
    assert report.passed, [str(f) for f in report.all_findings if f.severity.value == "error"]
    assert report.error_count() == 0


@pytest.mark.parametrize(
    "module",
    [schema_validator, topology, hydrology, biome, flora, fauna, ecology,
     interaction, weather, simulation],
)
def test_each_validator_passes_good_world(module, good: World) -> None:
    result = module.validate(good)
    assert result.passed, [str(f) for f in result.errors]


def test_constraint_passes_good_world(good: World) -> None:
    assert constraint.validate(good).passed


# --------------------------------------------------------------------------
# Negative: each validator flags its violation.
# --------------------------------------------------------------------------

def test_schema_validator_flags_malformed_dict() -> None:
    result = schema_validator.validate_dict({"metadata": {"id": "x"}})
    assert not result.passed
    assert "SCH" in _error_codes(result)


def test_topology_flags_floating_ocean_edge(good_dict: dict) -> None:
    good_dict["layout"]["edge_type"] = "ocean"  # floating world may not use an ocean edge
    world = World.model_validate(good_dict)
    result = topology.validate(world)
    assert not result.passed
    assert "TOP" in _error_codes(result)


def test_hydrology_flags_river_with_no_outlet(good_dict: dict) -> None:
    # Pick the first river and strip its outlet so its flow chain never terminates.
    river = next(b for b in good_dict["water"]["bodies"] if b["type"] == "river")
    river["flows_to"] = None
    river["exits_world"] = False
    world = World.model_validate(good_dict)
    result = hydrology.validate(world)
    assert not result.passed
    assert "HYD" in _error_codes(result)


def test_biome_flags_impossible_climate(good_dict: dict) -> None:
    desert = next(b for b in good_dict["biomes"]["zones"] if b["type"] == "desert")
    desert["temperature"] = "polar"  # deserts cannot be polar
    world = World.model_validate(good_dict)
    result = biome.validate(world)
    assert not result.passed
    assert "BIO" in _error_codes(result)


def test_flora_flags_unsupported_habitat(good_dict: dict) -> None:
    plant = good_dict["flora"]["species"][0]
    plant["category"] = "coral"  # coral cannot grow in a land biome
    world = World.model_validate(good_dict)
    result = flora.validate(world)
    assert not result.passed
    assert "FLO" in _error_codes(result)


def test_fauna_flags_herbivore_without_diet(good_dict: dict) -> None:
    herb = next(f for f in good_dict["fauna"]["species"] if f["trophic_role"] == "herbivore")
    herb["diet_flora_ids"] = []
    world = World.model_validate(good_dict)
    result = fauna.validate(world)
    assert not result.passed
    assert "FAU" in _error_codes(result)


def test_ecology_flags_trophic_cycle(good_dict: dict) -> None:
    species = good_dict["fauna"]["species"]
    a = next(f for f in species if f["trophic_role"] == "carnivore")
    b = next(f for f in species if f["trophic_role"] == "apex_predator")
    a["diet_fauna_ids"] = [b["id"]]
    b["diet_fauna_ids"] = [a["id"]]  # mutual predation -> impossible cycle
    world = World.model_validate(good_dict)
    result = ecology.validate(world)
    assert not result.passed
    assert "ECO" in _error_codes(result)


def test_interaction_flags_wrong_endpoint(good_dict: dict) -> None:
    flora_id = good_dict["flora"]["species"][0]["id"]
    fauna_id = good_dict["fauna"]["species"][0]["id"]
    good_dict["interactions"]["edges"].append(
        {"id": "int_bad", "type": "predation", "source_id": flora_id,
         "target_id": fauna_id, "strength": 0.5, "seasonal": False}
    )
    world = World.model_validate(good_dict)
    result = interaction.validate(world)
    assert not result.passed
    assert "INT" in _error_codes(result)


def test_constraint_flags_civilization_term(good_dict: dict) -> None:
    good_dict["metadata"]["name"] = "The Village of the Floating Sea"
    world = World.model_validate(good_dict)
    result = constraint.validate(world)
    assert not result.passed
    assert "CON" in _error_codes(result)


def test_constraint_enforces_quantitative_task_rules(good: World) -> None:
    result = constraint.validate(good, {"min_biomes": 999})
    assert not result.passed
    assert "CON" in _error_codes(result)


def test_weather_flags_missing_biome_coverage(good_dict: dict) -> None:
    good_dict["weather"]["biome_weather"].pop()  # drop coverage for one biome
    world = World.model_validate(good_dict)
    result = weather.validate(world)
    assert not result.passed
    assert "WEA" in _error_codes(result)


def test_simulation_flags_unknown_reference(good_dict: dict) -> None:
    good_dict["simulation"]["dynamics"][0]["involves_ids"] = ["nonexistent_entity"]
    world = World.model_validate(good_dict)
    result = simulation.validate(world)
    assert not result.passed
    assert "SIM" in _error_codes(result)


# --------------------------------------------------------------------------
# Aggregate behavior.
# --------------------------------------------------------------------------

def test_validate_world_aggregates_and_fails_on_any_error(good_dict: dict) -> None:
    good_dict["metadata"]["name"] = "Kingdom of the Sky"  # constraint violation
    world = World.model_validate(good_dict)
    report = validate_world(world)
    assert not report.passed
    assert report.error_count() >= 1
    assert len(report.results) == 11  # every validator ran


def test_constraint_receives_task_constraints_via_aggregate(good: World) -> None:
    report = validate_world(good, {"required_topology": "continent"})
    assert not report.passed  # sample is a floating_island, not a continent
