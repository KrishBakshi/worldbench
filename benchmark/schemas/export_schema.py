"""Generate the versioned WorldBench JSON Schema from the Pydantic models.

Run this whenever the models change to refresh the committed schema file::

    python -m benchmark.schemas.export_schema

The emitted file is the machine-readable contract handed to models under test
and used by :mod:`benchmark.validators.schema_validator`.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..models.metadata import SCHEMA_VERSION
from ..models.world import World

SCHEMA_DIR = Path(__file__).parent
SCHEMA_FILENAME = f"world_schema_v{SCHEMA_VERSION.split('.')[0]}.json"


def build_schema() -> dict:
    """Return the JSON Schema dict for :class:`World`, annotated with version."""
    schema = World.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"https://worldbench.dev/schemas/{SCHEMA_FILENAME}"
    schema["title"] = "WorldBench World"
    schema["x-worldbench-schema-version"] = SCHEMA_VERSION
    return schema


def export(path: Path | None = None) -> Path:
    """Write the schema to ``path`` (defaults to the packaged schema file)."""
    target = path or (SCHEMA_DIR / SCHEMA_FILENAME)
    target.write_text(json.dumps(build_schema(), indent=2) + "\n", encoding="utf-8")
    return target


def load_schema() -> dict:
    """Load the committed schema file (falling back to a fresh build)."""
    path = SCHEMA_DIR / SCHEMA_FILENAME
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return build_schema()


if __name__ == "__main__":  # pragma: no cover - CLI entry
    written = export()
    print(f"Wrote {written}")
