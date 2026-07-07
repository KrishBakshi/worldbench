# WorldBench Developer Guide

Everything you need to work on WorldBench itself: set up the environment, run the
tests, and extend each layer.

## Environment setup

WorldBench targets **Python 3.12+**.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Shapely links against GEOS. On Debian/Ubuntu:

```bash
sudo apt-get install -y libgeos-dev
```

macOS (Homebrew): `brew install geos`.

## Running the tests

```bash
pytest                      # whole suite
pytest tests/test_validators.py -q
pytest --cov=benchmark      # with coverage
```

The suite covers every layer: models, knowledge graph, validators, metrics,
runner, and CLI. Tests never make live network calls — the runner/CLI tests use
the deterministic `mock` adapter or an injected fake.

## Linting and type-checking

```bash
ruff check benchmark tests
mypy benchmark
```

Both are configured in `pyproject.toml` (line length 100, target py312).

## Regenerating the JSON Schema

The schema file is generated from the Pydantic models — never edit it by hand.
After changing anything under `benchmark/models/`, run:

```bash
python -m benchmark.schemas.export_schema
```

This rewrites `benchmark/schemas/world_schema_v1.json`. Commit the regenerated
file alongside your model change.

## Adding a validator

1. Create `benchmark/validators/<name>.py`.
2. Give it a module-level `NAME` and a unique three-letter finding-code prefix
   (e.g. `SOI` for a hypothetical soil validator).
3. Implement `def validate(world: World) -> ValidationResult:` — collect
   `Finding`s and return `ValidationResult.build(NAME, findings, checks_run)`.
   Use `Severity.ERROR` for broken natural laws and `Severity.WARNING` for
   implausible-but-not-impossible cases.
4. Register it in `benchmark/validators/composite.py` so `validate_world` runs it
   and it appears in the aggregated `ValidationReport`.
5. Add tests in `tests/test_validators.py`: one asserting it passes on a good
   world, one asserting it errors on a broken one (assert on the code prefix).

Consult the knowledge graph rather than hard-coding ecology:

```python
from benchmark.knowledge import load_knowledge

kg = load_knowledge()
if not kg.supports_flora(biome_type, flora_category):
    ...  # emit a Finding
```

## Adding a metric

1. Create `benchmark/metrics/<name>.py` exposing
   `def score(world: World, report: ValidationReport | None = None) -> MetricResult:`
   returning a score in `[0, 100]` with a short `detail` string.
2. Register it in `benchmark/metrics/overall.py` and add its weight to
   `benchmark/metrics/weights.yaml` (weights should still sum to ~1.0).
3. Add tests in `tests/test_metrics.py`: a strong world should score high and a
   deliberately weak world should score lower on your metric.

Metrics must not import from `benchmark.validators`; if you need validation
signal, read it from the optional `report` argument.

## Adding a model provider adapter

1. Create `benchmark/runner/adapters/<provider>.py` subclassing the base
   `ModelAdapter` and implementing `generate(self, prompt: str) -> str` (return
   the raw model text; the runner extracts JSON).
2. Read credentials/endpoints from environment variables — never hard-code keys.
3. Register the adapter name in the adapter factory so `--adapter <provider>`
   resolves it.
4. Keep network I/O in `httpx`; no heavyweight provider SDKs.

## Coding standards

- `from __future__ import annotations` at the top of every module.
- Full type annotations; run `mypy` before pushing.
- Module and public-function docstrings that explain *why*, not just *what*.
- Pydantic models forbid extra fields (`WorldBenchModel`) — malformed input
  should fail loudly.
- No placeholder `TODO`s in committed code.
- Prefer editing the YAML ontology over embedding ecological facts in Python.
