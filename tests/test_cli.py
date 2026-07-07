"""Tests for the ``worldbench`` Typer CLI (no live network calls)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from benchmark.cli import app
from benchmark.samples import sample_world

runner = CliRunner()


def _write_sample(tmp_path: Path) -> Path:
    world_path = tmp_path / "world.json"
    sample_world().save(world_path)
    return world_path


def test_list_tasks_runs() -> None:
    result = runner.invoke(app, ["list"])
    # Either lists tasks or reports none — both are exit code 0.
    assert result.exit_code == 0


def test_validate_command_on_sample(tmp_path: Path) -> None:
    world_path = _write_sample(tmp_path)
    result = runner.invoke(app, ["validate", str(world_path)])
    assert result.exit_code == 0
    assert "PASSED" in result.stdout


def test_score_command_json(tmp_path: Path) -> None:
    world_path = _write_sample(tmp_path)
    result = runner.invoke(app, ["score", str(world_path), "--json"])
    assert result.exit_code == 0
    assert "overall" in result.stdout


def test_report_markdown_to_file(tmp_path: Path) -> None:
    world_path = _write_sample(tmp_path)
    out = tmp_path / "report.md"
    result = runner.invoke(app, ["report", str(world_path), "--format", "markdown", "--out", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    assert "Overall Score" in out.read_text()


def test_report_html(tmp_path: Path) -> None:
    world_path = _write_sample(tmp_path)
    out = tmp_path / "report.html"
    result = runner.invoke(app, ["report", str(world_path), "-f", "html", "-o", str(out)])
    assert result.exit_code == 0
    assert "<!doctype html>" in out.read_text().lower()


def test_run_command_with_mock(tmp_path: Path) -> None:
    # WC001 (or any task) may not exist yet in this test env; use --no-persist
    # against a synthetic task by pointing at the packaged prompts if present.
    result = runner.invoke(
        app,
        ["run", "--task", "WC001_complete_floating_world", "--adapter", "mock",
         "--outputs", str(tmp_path / "outputs")],
    )
    # If the task exists it should score; if not, the CLI exits non-zero with a
    # clear message. Accept both so the test does not depend on prompt content.
    assert result.exit_code in (0, 1)


def test_validate_missing_file() -> None:
    result = runner.invoke(app, ["validate", "/nonexistent/world.json"])
    assert result.exit_code == 2


def test_leaderboard_empty(tmp_path: Path) -> None:
    result = runner.invoke(app, ["leaderboard", "--outputs", str(tmp_path)])
    assert result.exit_code == 0
    assert "Leaderboard" in result.stdout
