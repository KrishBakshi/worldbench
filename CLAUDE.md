# WorldBench — repo guide for Claude

WorldBench benchmarks LLMs on generating structured, **living natural** worlds as
JSON, scored by deterministic validators + a knowledge-graph ontology (no image
eval, no reference-world comparison). Scope is natural environments only — no
humans, civilization, cities, roads, buildings, politics, or economy.

## Layout
- Source package dir is `benchmark/`, but it installs and imports as **`benchmark`**
  (see `pyproject.toml`; CLI entry `benchmark.cli:app` → `worldbench`).
- `benchmark/models/` — Pydantic v2 schema (12 sections + top-level `World`);
  `graph.py` builds a networkx view. Regenerate JSON Schema with
  `python -m benchmark.schemas.export_schema`.
- `benchmark/results.py` — shared `ValidationResult`/`ValidationReport`/`Finding`/
  `MetricResult`/`ScoreReport` contracts. Everything downstream depends on these.
- `benchmark/knowledge/` — YAML ontology + cached `KnowledgeGraph` (`load_knowledge()`).
  Concept keys are namespaced (marine biome vs sea water) — see aliases.
- `benchmark/validators/` — 11 validators + `validate_world(world, constraints=None)`.
  Finding-code prefixes: SCH/TOP/HYD/BIO/FLO/FAU/ECO/INT/CON/WEA/SIM.
- `benchmark/metrics/` — 9 metrics + `score_world(world, report=None)` → `/100`.
  Weights in `benchmark/metrics/weights.yaml`. Metrics do NOT import validators.
- `benchmark/runner/` — `loader.py` (task discovery), `extract.py` (recover JSON
  from prose), `runner.py` (orchestrator), `adapters/` (mock + real httpx
  OpenAI/Anthropic/Gemini/Ollama/vLLM).
- `benchmark/samples.py` — `sample_world()` "The Verdant Expanse", the canonical
  valid world (scores ~95/100). The `mock` adapter returns it.
- `prompts/NN_category/<TASKID>/` — one benchmark task per category.

## Conventions
- Python 3.12+; local dev venv at `.venv/` (built on 3.14). Use `.venv/bin/python`
  and `.venv/bin/worldbench`.
- Run tests: `.venv/bin/python -m pytest -q`.
- Every entity has a stable snake_case `id`; relationships are id references.
- Validators return errors (hard) vs warnings (soft); `passed` ignores warnings.
