"""The ``worldbench`` command-line interface.

Commands:

* ``worldbench list`` — list discoverable benchmark tasks.
* ``worldbench run`` — run a task against a model adapter and score it.
* ``worldbench validate`` — validate an existing world.json (no model call).
* ``worldbench score`` — score an existing world.json.
* ``worldbench report`` — render a Markdown/JSON/HTML report for a world.json.
* ``worldbench leaderboard`` — aggregate outputs/ into a leaderboard.

The CLI is a thin shell over :mod:`benchmark.runner`, :mod:`benchmark.validators`,
:mod:`benchmark.metrics`, and :mod:`benchmark.reports`; all heavy lifting lives
in those packages so the same operations are usable programmatically.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .models import World
from .reports import (
    collect_standings,
    render_html,
    render_json,
    render_leaderboard_html,
    render_leaderboard_markdown,
    render_markdown,
)
from .runner import BenchmarkRunner, available_adapters, discover_tasks, find_task, load_task
from .runner.runner import OUTPUTS_DIR

app = typer.Typer(
    add_completion=False,
    help="WorldBench — benchmark LLMs on structured, living natural world generation.",
)
console = Console()


def _load_world_or_exit(path: Path) -> World:
    if not path.exists():
        console.print(f"[red]No such file:[/red] {path}")
        raise typer.Exit(code=2)
    try:
        return World.from_file(path)
    except Exception as exc:  # noqa: BLE001 - surface any parse/validation error
        console.print(f"[red]Failed to parse world:[/red] {exc}")
        raise typer.Exit(code=1)


@app.command("list")
def list_tasks(
    prompts_dir: Path = typer.Option(None, "--prompts", help="Override the prompts directory."),
) -> None:
    """List all discoverable benchmark tasks."""
    tasks = discover_tasks(prompts_dir)
    if not tasks:
        console.print("[yellow]No tasks found.[/yellow]")
        raise typer.Exit()
    table = Table(title="WorldBench Tasks")
    table.add_column("Task ID", style="cyan")
    table.add_column("Category", style="green")
    table.add_column("Title")
    for task in tasks:
        table.add_row(task.id, task.category, task.title)
    console.print(table)


@app.command()
def run(
    task: str = typer.Option(..., "--task", "-t", help="Task id or directory name."),
    adapter: str = typer.Option("mock", "--adapter", "-a", help="Model adapter to use."),
    model: str = typer.Option(None, "--model", "-m", help="Override the adapter's model."),
    prompts_dir: Path = typer.Option(None, "--prompts", help="Override the prompts directory."),
    outputs_dir: Path = typer.Option(None, "--outputs", help="Override the outputs directory."),
    no_persist: bool = typer.Option(False, "--no-persist", help="Do not write output files."),
) -> None:
    """Run a task against a model adapter, validate, and score it."""
    if adapter not in available_adapters():
        console.print(f"[red]Unknown adapter[/red] {adapter!r}. "
                      f"Available: {', '.join(available_adapters())}")
        raise typer.Exit(code=2)
    task_obj = find_task(task, prompts_dir) if prompts_dir else find_task(task)
    runner = BenchmarkRunner.from_adapter_name(
        adapter, model=model, outputs_dir=outputs_dir
    )
    result = runner.run_task(task_obj, persist=not no_persist)

    console.print(f"[bold]{task_obj.id}[/bold] via [cyan]{adapter}[/cyan] "
                  f"([magenta]{result.model}[/magenta])")
    console.print(f"  parsed: {result.parsed}  "
                  f"validation: {'PASS' if result.validation.passed else 'FAIL'} "
                  f"({result.validation.error_count()}E/{result.validation.warning_count()}W)")
    console.print(f"  [bold]overall score: {result.overall_score:.1f}/100[/bold]")
    if result.output_dir:
        console.print(f"  output: {result.output_dir}")


@app.command()
def validate(
    world_path: Path = typer.Argument(..., help="Path to a world.json to validate."),
    constraints: Path = typer.Option(None, "--constraints", help="Optional constraints.yaml."),
) -> None:
    """Validate a world.json against schema, topology, ecology, and more."""
    from .validators import validate_world

    world = _load_world_or_exit(world_path)
    constraint_data = None
    if constraints and constraints.exists():
        import yaml

        constraint_data = yaml.safe_load(constraints.read_text(encoding="utf-8"))
    report = validate_world(world, constraints=constraint_data)

    table = Table(title=f"Validation — {world_path.name}")
    table.add_column("Validator", style="cyan")
    table.add_column("Passed")
    table.add_column("Errors", justify="right")
    table.add_column("Warnings", justify="right")
    for r in report.results:
        table.add_row(
            r.validator,
            "[green]yes[/green]" if r.passed else "[red]no[/red]",
            str(len(r.errors)),
            str(len(r.warnings)),
        )
    console.print(table)
    console.print(f"Overall: {'[green]PASSED[/green]' if report.passed else '[red]FAILED[/red]'} "
                  f"({report.error_count()} errors, {report.warning_count()} warnings)")
    if not report.passed:
        raise typer.Exit(code=1)


@app.command()
def score(
    world_path: Path = typer.Argument(..., help="Path to a world.json to score."),
    as_json: bool = typer.Option(False, "--json", help="Emit the score report as JSON."),
) -> None:
    """Compute the weighted metric score for a world.json."""
    from .metrics import score_world
    from .validators import validate_world

    world = _load_world_or_exit(world_path)
    report = validate_world(world)
    scores = score_world(world, report)

    if as_json:
        console.print_json(scores.model_dump_json())
        return
    table = Table(title=f"Score — {world_path.name}")
    table.add_column("Metric", style="cyan")
    table.add_column("Score", justify="right")
    table.add_column("Weight", justify="right")
    for m in scores.metrics:
        table.add_row(m.name, f"{m.score:.1f}", f"{m.weight:.2f}")
    console.print(table)
    console.print(f"[bold]Overall: {scores.overall:.1f}/100[/bold]")


@app.command()
def report(
    world_path: Path = typer.Argument(..., help="Path to a world.json to report on."),
    fmt: str = typer.Option("markdown", "--format", "-f", help="markdown | json | html"),
    out: Path = typer.Option(None, "--out", "-o", help="Write to a file instead of stdout."),
    task: str = typer.Option(None, "--task", help="Attribute the report to this task id."),
) -> None:
    """Render a full report (Markdown, JSON, or HTML) for a world.json."""
    from .metrics import score_world
    from .validators import validate_world
    from .runner.runner import RunResult

    world = _load_world_or_exit(world_path)
    validation = validate_world(world)
    scores = score_world(world, validation)
    result = RunResult(
        task_id=task or world.metadata.id,
        category="ad-hoc",
        adapter="file",
        model=world.metadata.name,
        parsed=True,
        overall_score=scores.overall,
        validation=validation,
        score=scores,
        raw_output=world.to_json(),
        world_json=world.to_json(),
    )

    renderers = {"markdown": render_markdown, "json": render_json, "html": render_html}
    if fmt not in renderers:
        console.print(f"[red]Unknown format[/red] {fmt!r}. Choose: {', '.join(renderers)}")
        raise typer.Exit(code=2)
    rendered = renderers[fmt](result)
    if out:
        out.write_text(rendered, encoding="utf-8")
        console.print(f"Wrote {fmt} report to {out}")
    else:
        console.print(rendered)


@app.command()
def leaderboard(
    outputs_dir: Path = typer.Option(None, "--outputs", help="Override the outputs directory."),
    fmt: str = typer.Option("markdown", "--format", "-f", help="markdown | json | html"),
    out: Path = typer.Option(None, "--out", "-o", help="Write to a file instead of stdout."),
) -> None:
    """Aggregate outputs/ into a cross-model leaderboard."""
    standings = collect_standings(outputs_dir or OUTPUTS_DIR)
    if fmt == "json":
        from .reports import build_leaderboard_json

        rendered = json.dumps(build_leaderboard_json(standings), indent=2)
    elif fmt == "html":
        rendered = render_leaderboard_html(standings)
    elif fmt == "markdown":
        rendered = render_leaderboard_markdown(standings)
    else:
        console.print(f"[red]Unknown format[/red] {fmt!r}.")
        raise typer.Exit(code=2)
    if out:
        out.write_text(rendered, encoding="utf-8")
        console.print(f"Wrote leaderboard to {out}")
    else:
        console.print(rendered)


def main() -> None:  # pragma: no cover - console entry point
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
