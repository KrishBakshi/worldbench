# WorldBench — repo guide for Claude

WorldBench benchmarks LLMs on generating structured, **living natural** worlds as
JSON, scored by deterministic validators + a knowledge-graph ontology (no image
eval, no reference-world comparison). Scope is natural environments only — no
humans, civilization, cities, roads, buildings, politics, or economy.

WorldBench is a **two-artifact** benchmark: (1) a `world.json`, scored on its
own out of 100 as above, and (2) an optional companion `world.html` — a
self-contained Three.js visualization that must be built *from* that exact
JSON (see "HTML companion artifact" below). The HTML gets its own separate
fidelity score; it is never blended into the JSON's `overall_score`.

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
- `benchmark/validators/` — 11 world validators + `validate_world(world, constraints=None)`.
  Finding-code prefixes: SCH/TOP/HYD/BIO/FLO/FAU/ECO/INT/CON/WEA/SIM. Plus
  `html_fidelity.py` (prefix HTM) — a 12th validator with a different shape:
  `validate(html, world)` takes two arguments (HTML text + the JSON it should
  derive from) and is not part of `validate_world`'s composite; call it via
  `validate_html` or `worldbench score-html`.
- `benchmark/metrics/` — 9 metrics + `score_world(world, report=None)` → `/100`.
  Weights in `benchmark/metrics/weights.yaml`. Metrics do NOT import validators.
  `html_fidelity.py`'s `score_html_fidelity(html, world)` is a 10th, standalone
  metric deliberately excluded from `METRICS`/`weights.yaml` — it scores the
  HTML against the JSON as a reference, not the JSON in isolation.
- `benchmark/runner/` — `loader.py` (task discovery), `extract.py` (recover JSON
  from prose), `runner.py` (orchestrator), `adapters/` (mock + real httpx
  OpenAI/Anthropic/Gemini/Ollama/vLLM).
- `benchmark/samples.py` — `sample_world()` "The Verdant Expanse", the canonical
  valid world (scores ~95/100). The `mock` adapter returns it.
- `prompts/NN_category/<TASKID>/` — one benchmark task per category. Tasks that
  support manual (no-API) generation also carry `01_generate_json_prompt.md`
  (stage 1, ready-to-paste) and `02_generate_html_prompt.md` (stage 2) right
  in their own folder — the single source of truth for that task's prompts,
  not duplicated elsewhere. At the top of `prompts/`:
  `01_json_generation_prompt_template.md` documents stage 1's assembly recipe
  (it's inherently per-task, so this is a recipe + pointer, not one shared
  prompt) and `02_html_generation_prompt_template.md` is the one shared,
  task-agnostic template every task's `02_generate_html_prompt.md` is built
  from. See `prompts/overview.md` for the two-stage pipeline explained at the
  top level.
- `manual_generation/` — **results only** for the manual (no-API) workflow;
  the prompts themselves live in `prompts/` (see above), not here. Results land
  in `manual_generation/output/<model_name>/{world.json, world.html}`; see its
  `README.md`. Distinct from the repo-root
  `outputs/<adapter>__<model>/<task_id>/` bundle format `worldbench leaderboard`
  scans — the former is raw hand-generated artifacts, the latter is scored,
  leaderboard-ready output.
- `references/` — **gitignored, local-only** archive of prior experiments and
  material that isn't part of live benchmark evaluation (currently
  `ref_gen_html/`, an earlier prose-prompted-HTML experiment, and
  `example_prompt.md`). Never pushed, but still readable when working in this
  checkout.

## HTML companion artifact
- Stage 2 asks a model to turn a specific `world.json` into a self-contained
  `world.html` (Three.js, CDN import is fine, one file, free camera).
- Grading is deterministic text analysis only — no rendering, no screenshots,
  no LLM-as-judge: the HTML must embed the exact source JSON verbatim in
  `<script type="application/json" id="world-data">`, the embedded
  `metadata.id` must match the source world, and the code must demonstrably
  read that blob back out (`getElementById`/`querySelector` + `JSON.parse`)
  and reference the schema's real section keys/entity ids — not just embed the
  JSON inertly next to a generic, hardcoded scene.
- Check it with `worldbench score-html <html> --world <json>`, or score both
  artifacts for one model in a single shot with
  `worldbench evaluate <model_dir>` (expects `<model_dir>/world.json` and,
  optionally, `<model_dir>/world.html` — exactly the layout
  `manual_generation/output/<model_name>/` produces).

## Conventions
- Python 3.12+; local dev venv at `.venv/` (built on 3.14). Use `.venv/bin/python`
  and `.venv/bin/worldbench`.
- Run tests: `.venv/bin/python -m pytest -q`.
- Every entity has a stable snake_case `id`; relationships are id references.
- Validators return errors (hard) vs warnings (soft); `passed` ignores warnings.
