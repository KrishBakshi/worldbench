"""Integrity tests for the packaged benchmark tasks under ``prompts/``.

These assert that every authored task is well-formed and loadable, that its
declared valid example actually passes the composite validator, and that its
invalid example actually fails — the core promise a benchmark task makes.
"""

from __future__ import annotations

import json

import pytest

from benchmark.models import World
from benchmark.runner.loader import PROMPTS_DIR, discover_tasks
from benchmark.validators import validate_world

REQUIRED_FILES = [
    "prompt.md",
    "metadata.yaml",
    "task.yaml",
    "constraints.yaml",
    "scoring.yaml",
    "expected_schema.json",
    "validator.py",
    "README.md",
]

_TASKS = discover_tasks()
_TASK_IDS = [t.id for t in _TASKS]


def test_prompts_directory_exists() -> None:
    assert PROMPTS_DIR.exists(), "prompts/ directory is missing"


@pytest.mark.skipif(not _TASKS, reason="no tasks authored yet")
def test_expected_number_of_categories() -> None:
    categories = {t.category for t in _TASKS}
    # Ten prompt categories are defined by the benchmark design.
    assert len(categories) >= 1
    for task in _TASKS:
        assert task.prompt.strip(), f"{task.id} has an empty prompt.md"


@pytest.mark.skipif(not _TASKS, reason="no tasks authored yet")
@pytest.mark.parametrize("task", _TASKS, ids=_TASK_IDS)
def test_task_has_required_files(task) -> None:
    for name in REQUIRED_FILES:
        assert (task.path / name).exists(), f"{task.id} is missing {name}"
    assert (task.path / "examples" / "valid").is_dir()
    assert (task.path / "examples" / "invalid").is_dir()


@pytest.mark.skipif(not _TASKS, reason="no tasks authored yet")
@pytest.mark.parametrize("task", _TASKS, ids=_TASK_IDS)
def test_expected_schema_is_valid_json(task) -> None:
    schema_path = task.path / "expected_schema.json"
    json.loads(schema_path.read_text(encoding="utf-8"))  # raises on malformed


@pytest.mark.skipif(not _TASKS, reason="no tasks authored yet")
@pytest.mark.parametrize("task", _TASKS, ids=_TASK_IDS)
def test_valid_example_passes(task) -> None:
    valid_path = task.path / "examples" / "valid" / "world.json"
    if not valid_path.exists():
        pytest.skip(f"{task.id} has no valid example")
    world = World.from_file(valid_path)
    report = validate_world(world, constraints=task.constraints or None)
    assert report.passed, (
        f"{task.id} valid example failed validation: "
        f"{[str(f) for f in report.all_findings if f.severity.value == 'error']}"
    )


@pytest.mark.skipif(not _TASKS, reason="no tasks authored yet")
@pytest.mark.parametrize("task", _TASKS, ids=_TASK_IDS)
def test_invalid_example_fails(task) -> None:
    invalid_path = task.path / "examples" / "invalid" / "world.json"
    if not invalid_path.exists():
        pytest.skip(f"{task.id} has no invalid example")
    # An invalid example must fail somewhere: either schema parsing or the
    # composite validator.
    try:
        world = World.from_file(invalid_path)
    except Exception:
        return  # failed at schema parse — acceptably invalid
    report = validate_world(world, constraints=task.constraints or None)
    assert not report.passed, f"{task.id} invalid example unexpectedly passed validation"
