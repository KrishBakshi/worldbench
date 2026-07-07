"""Tests for the benchmark runner, adapters, and JSON extraction."""

from __future__ import annotations

import json

import pytest

from benchmark.runner import BenchmarkRunner, available_adapters, get_adapter
from benchmark.runner.adapters import AdapterError, GenerationConfig, MockAdapter
from benchmark.runner.adapters.base import ModelAdapter
from benchmark.runner.extract import extract_json


# -- JSON extraction --------------------------------------------------------
def test_extract_plain_json() -> None:
    result = extract_json('{"a": 1, "b": [2, 3]}')
    assert result.ok and result.data == {"a": 1, "b": [2, 3]}
    assert not result.used_fallback


def test_extract_fenced_json() -> None:
    result = extract_json('```json\n{"x": 10}\n```')
    assert result.ok and result.data == {"x": 10}


def test_extract_json_from_prose() -> None:
    text = 'Here is your world:\n{"name": "w", "nested": {"k": "}"}}\nHope that helps!'
    result = extract_json(text)
    assert result.ok and result.used_fallback
    assert result.data["nested"]["k"] == "}"


def test_extract_handles_braces_in_strings() -> None:
    result = extract_json('{"s": "a { b } c", "n": 1}')
    assert result.ok and result.data == {"s": "a { b } c", "n": 1}


def test_extract_empty_and_garbage() -> None:
    assert not extract_json("").ok
    assert not extract_json("no json here").ok
    assert not extract_json("{ not valid json ").ok


# -- adapters ---------------------------------------------------------------
def test_registry_contains_all_providers() -> None:
    names = available_adapters()
    for expected in ("mock", "openai", "anthropic", "gemini", "ollama", "vllm"):
        assert expected in names


def test_unknown_adapter_raises() -> None:
    with pytest.raises(AdapterError):
        get_adapter("does-not-exist")


def test_mock_adapter_returns_valid_world_json() -> None:
    adapter = MockAdapter()
    raw = adapter.generate("anything")
    data = json.loads(raw)
    assert data["metadata"]["name"] == "The Verdant Expanse"


def test_provider_adapters_construct_with_defaults() -> None:
    # Construction must not require network or keys; only .generate() would.
    for name in ("openai", "anthropic", "gemini", "ollama", "vllm"):
        adapter = get_adapter(name)
        assert adapter.name == name
        assert adapter.config.model  # a default model is always set


def test_missing_api_key_errors_on_generate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    adapter = get_adapter("openai")
    with pytest.raises(AdapterError):
        adapter.generate("hi")


# -- end-to-end run via the mock adapter ------------------------------------
def test_run_task_with_mock_adapter(tmp_path) -> None:
    from benchmark.runner.loader import Task

    task = Task(
        id="TEST001",
        category="unit",
        path=tmp_path,
        prompt="Generate a world.",
    )
    runner = BenchmarkRunner(MockAdapter(), outputs_dir=tmp_path / "outputs")
    result = runner.run_task(task, persist=True)

    assert result.parsed is True
    assert result.validation.passed is True
    assert result.overall_score > 50
    # Output bundle written.
    out = result.output_dir
    assert (out / "world.json").exists()
    assert (out / "validation.json").exists()
    assert (out / "metrics.json").exists()
    assert (out / "report.json").exists()
    assert (out / "logs.txt").exists()
    summary = json.loads((out / "report.json").read_text())
    assert summary["task_id"] == "TEST001"
    assert summary["passed_validation"] is True


def test_run_handles_unparseable_output(tmp_path) -> None:
    class BadAdapter(ModelAdapter):
        name = "bad"

        def __init__(self):
            super().__init__(GenerationConfig(model="bad-1"))

        def generate(self, prompt: str, *, system: str | None = None) -> str:
            return "I refuse to emit JSON."

    from benchmark.runner.loader import Task

    task = Task(id="BAD001", category="unit", path=tmp_path, prompt="x")
    runner = BenchmarkRunner(BadAdapter(), outputs_dir=tmp_path / "outputs")
    result = runner.run_task(task, persist=True)
    assert result.parsed is False
    assert result.overall_score == 0.0
    # Raw output is preserved for debugging.
    assert (result.output_dir / "world.json").read_text() == "I refuse to emit JSON."
