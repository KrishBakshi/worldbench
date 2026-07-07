"""Discover and load benchmark tasks from the ``prompts/`` tree.

A *task* is a directory containing at least ``prompt.md`` and ``task.yaml``.
Optional companions (``constraints.yaml``, ``scoring.yaml``,
``expected_schema.json``, ``metadata.yaml``) are loaded when present. The loader
is filesystem-driven so new tasks need no code changes — dropping a conformant
folder under ``prompts/<category>/`` is enough.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Repo root is three levels up from this file: benchmark/runner/loader.py.
REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = REPO_ROOT / "prompts"


@dataclass
class Task:
    """A loaded benchmark task."""

    id: str
    category: str
    path: Path
    prompt: str
    metadata: dict = field(default_factory=dict)
    spec: dict = field(default_factory=dict)
    constraints: dict = field(default_factory=dict)
    scoring: dict = field(default_factory=dict)
    expected_schema: dict | None = None

    @property
    def title(self) -> str:
        return self.metadata.get("title") or self.spec.get("title") or self.id

    @property
    def system_prompt(self) -> str | None:
        return self.spec.get("system_prompt") or self.metadata.get("system_prompt")


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {}


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def is_task_dir(path: Path) -> bool:
    """A directory is a task if it holds a prompt and a task spec."""
    return (path / "prompt.md").exists() and (path / "task.yaml").exists()


def load_task(path: str | Path) -> Task:
    """Load a single task from its directory."""
    path = Path(path)
    if not is_task_dir(path):
        raise FileNotFoundError(
            f"{path} is not a task directory (needs prompt.md and task.yaml)"
        )
    spec = _read_yaml(path / "task.yaml")
    metadata = _read_yaml(path / "metadata.yaml")
    return Task(
        id=spec.get("id") or metadata.get("id") or path.name,
        category=spec.get("category") or path.parent.name,
        path=path,
        prompt=(path / "prompt.md").read_text(encoding="utf-8"),
        metadata=metadata,
        spec=spec,
        constraints=_read_yaml(path / "constraints.yaml"),
        scoring=_read_yaml(path / "scoring.yaml"),
        expected_schema=_read_json(path / "expected_schema.json"),
    )


def discover_tasks(prompts_dir: str | Path | None = None) -> list[Task]:
    """Load every task under ``prompts_dir`` (defaults to the repo's prompts/)."""
    root = Path(prompts_dir) if prompts_dir else PROMPTS_DIR
    tasks: list[Task] = []
    if not root.exists():
        return tasks
    for task_dir in sorted(root.glob("*/*")):
        if task_dir.is_dir() and is_task_dir(task_dir):
            tasks.append(load_task(task_dir))
    return tasks


def find_task(task_id: str, prompts_dir: str | Path | None = None) -> Task:
    """Locate a task by id (or by directory name) under ``prompts_dir``."""
    root = Path(prompts_dir) if prompts_dir else PROMPTS_DIR
    # Direct directory-name match first (fast path).
    for candidate in sorted(root.glob(f"*/{task_id}")):
        if is_task_dir(candidate):
            return load_task(candidate)
    for task in discover_tasks(root):
        if task.id == task_id:
            return task
    raise FileNotFoundError(f"no task with id or directory name {task_id!r} under {root}")
