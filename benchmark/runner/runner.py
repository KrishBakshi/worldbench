"""Orchestrate a single benchmark run end-to-end.

The runner is the spine of WorldBench: given a task and a model adapter it
performs inference, recovers the JSON world, parses it against the schema, runs
every validator, computes every metric, and writes the standard output bundle::

    outputs/<ModelName>/<TaskID>/
        world.json        # the parsed world (or raw output on parse failure)
        validation.json   # ValidationReport
        metrics.json      # ScoreReport
        report.json       # combined run summary
        logs.txt          # human-readable trace

Validation and scoring are imported lazily so the runner module can be imported
even in a partial checkout, and so a world that fails to parse still produces a
meaningful (zeroed) result rather than crashing the batch.
"""

from __future__ import annotations

import platform
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from ..results import ScoreReport, ValidationReport
from .adapters import ModelAdapter, get_adapter
from .extract import extract_json
from .loader import REPO_ROOT, Task, find_task, load_task

OUTPUTS_DIR = REPO_ROOT / "outputs"


@dataclass
class RunResult:
    """The complete outcome of one task/model run."""

    task_id: str
    category: str
    adapter: str
    model: str
    parsed: bool
    overall_score: float
    validation: ValidationReport
    score: ScoreReport
    raw_output: str
    world_json: str | None
    logs: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    output_dir: Path | None = None

    def summary(self) -> dict:
        """A compact, JSON-serializable run summary (``report.json``)."""
        return {
            "task_id": self.task_id,
            "category": self.category,
            "adapter": self.adapter,
            "model": self.model,
            "timestamp": self.timestamp,
            "parsed": self.parsed,
            "overall_score": round(self.overall_score, 2),
            "passed_validation": self.validation.passed,
            "error_count": self.validation.error_count(),
            "warning_count": self.validation.warning_count(),
            "metrics": {m.name: round(m.score, 2) for m in self.score.metrics},
        }


def _empty_validation() -> ValidationReport:
    return ValidationReport(results=[])


def _run_validation(world, constraints: dict | None) -> ValidationReport:
    """Run the composite validator, tolerating an absent validators package."""
    try:
        from ..validators import validate_world
    except ImportError:  # pragma: no cover - only during partial builds
        return _empty_validation()
    return validate_world(world, constraints=constraints)


def _run_scoring(world, report: ValidationReport) -> ScoreReport:
    from ..metrics import score_world

    return score_world(world, report)


class BenchmarkRunner:
    """Runs tasks against a model adapter and persists the results."""

    def __init__(self, adapter: ModelAdapter, outputs_dir: Path | None = None):
        self.adapter = adapter
        self.outputs_dir = outputs_dir or OUTPUTS_DIR

    # -- construction helpers -------------------------------------------
    @classmethod
    def from_adapter_name(cls, name: str, *, model: str | None = None,
                          outputs_dir: Path | None = None) -> "BenchmarkRunner":
        from .adapters import GenerationConfig

        config = GenerationConfig(model=model) if model else None
        return cls(get_adapter(name, config), outputs_dir=outputs_dir)

    # -- execution -------------------------------------------------------
    def run_task(self, task: Task, *, persist: bool = True) -> RunResult:
        """Execute one task and (optionally) write its output bundle."""
        logs: list[str] = []

        def log(msg: str) -> None:
            logs.append(f"[{datetime.now(timezone.utc).isoformat()}] {msg}")

        log(f"task={task.id} category={task.category} adapter={self.adapter.name} "
            f"model={self.adapter.config.model}")

        raw = self.adapter.generate(task.prompt, system=task.system_prompt)
        log(f"received {len(raw)} chars of model output")

        extraction = extract_json(raw)
        world = None
        world_json: str | None = None
        parsed = False
        if not extraction.ok:
            log(f"JSON extraction failed: {extraction.error}")
        else:
            if extraction.used_fallback:
                log("recovered JSON from surrounding prose (fallback extractor)")
            world, parse_error = self._parse_world(extraction.data)
            if world is None:
                log(f"schema parse failed: {parse_error}")
            else:
                parsed = True
                world_json = world.to_json()
                log("world parsed and schema-valid")

        if world is not None:
            validation = _run_validation(world, task.constraints or None)
            score = _run_scoring(world, validation)
            log(f"validation passed={validation.passed} "
                f"errors={validation.error_count()} warnings={validation.warning_count()}")
            log(f"overall score={score.overall:.2f}")
        else:
            validation = _empty_validation()
            score = ScoreReport(metrics=[], overall=0.0)
            log("world unavailable; scored 0")

        result = RunResult(
            task_id=task.id,
            category=task.category,
            adapter=self.adapter.name,
            model=self.adapter.config.model,
            parsed=parsed,
            overall_score=score.overall,
            validation=validation,
            score=score,
            raw_output=raw,
            world_json=world_json,
            logs=logs,
        )
        if persist:
            result.output_dir = self.persist(result)
        return result

    def run_task_id(self, task_id: str, *, persist: bool = True) -> RunResult:
        return self.run_task(find_task(task_id), persist=persist)

    def run_task_path(self, path: str | Path, *, persist: bool = True) -> RunResult:
        return self.run_task(load_task(path), persist=persist)

    # -- persistence -----------------------------------------------------
    @staticmethod
    def _parse_world(data: dict):
        from ..models import World

        try:
            return World.model_validate(data), None
        except ValidationError as exc:
            return None, str(exc)

    def _model_dirname(self) -> str:
        raw = f"{self.adapter.name}__{self.adapter.config.model}"
        return "".join(c if c.isalnum() or c in "._-" else "_" for c in raw)

    def persist(self, result: RunResult) -> Path:
        """Write the standard output bundle for ``result`` and return its dir."""
        import json

        out = self.outputs_dir / self._model_dirname() / result.task_id
        out.mkdir(parents=True, exist_ok=True)
        (out / "world.json").write_text(result.world_json or result.raw_output, encoding="utf-8")
        (out / "validation.json").write_text(
            result.validation.model_dump_json(indent=2), encoding="utf-8"
        )
        (out / "metrics.json").write_text(
            result.score.model_dump_json(indent=2), encoding="utf-8"
        )
        (out / "report.json").write_text(json.dumps(result.summary(), indent=2), encoding="utf-8")
        (out / "logs.txt").write_text(
            "\n".join([f"# host: {platform.platform()}", *result.logs]) + "\n", encoding="utf-8"
        )
        return out
