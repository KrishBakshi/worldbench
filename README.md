<p align="center">
  <img src="public/world.png" alt="WorldBench — a generated floating natural world" width="612">
</p>

# WorldBench

**A Open Source benchmark for evaluating Large Language Models on the generation of
structured, living natural worlds.**

WorldBench asks a model to emit a single structured **JSON world** and then
validates that world **deterministically** — with rule-based validators and an
ecological knowledge graph — producing a weighted score out of 100. There is
**no reference world** to match against; WorldBench measures whether a model
can generate a world that is internally coherent, ecologically plausible,
hydrologically sound, topologically consistent, diverse, and complete.

WorldBench is a **two-artifact** benchmark. The JSON above is scored on its
own as described here. There's an optional second artifact — a self-contained
Three.js **`world.html`** built *from* that exact JSON — graded by its own,
separate fidelity score (never blended into the JSON's `overall_score`). This
still isn't image evaluation: fidelity is checked by deterministic text
analysis (does the HTML embed and actually use the source JSON's data), never
by rendering, screenshotting, or an LLM judging what it looks like. See
[Two-stage generation](#two-stage-generation-json-then-html) below.

---

## Why deterministic validation?

Most "world generation" evaluations judge a rendered image, or compare an output
against a golden answer. Both are poor fits for open-ended world design:

- **Images conflate art with structure.** A pretty render can hide an ocean that
  flows uphill; an ugly one can describe a perfectly coherent ecosystem.
- **Reference matching punishes creativity.** There is no single correct world.

WorldBench instead treats a world as a **typed graph of natural entities** and
checks the *laws* that any believable natural world must obey: water flows
downhill to a terminal body, cacti do not grow in rainforests, every carnivore
has reachable prey, biome climates are self-consistent, and so on. These are
checkable without a reference, and they reward any world that is *alive and
consistent* regardless of style.

---

## Scope: natural environments only

WorldBench is deliberately narrow. Worlds are **wild nature** with no trace of
people or their works.

**In scope**

> floating worlds · islands · terrain · mountains · plains · cliffs · deserts ·
> volcanoes · snow regions · rivers · lakes · oceans · beaches · waterfalls ·
> flora · fauna · ecosystems · food chains · pollination · migration ·
> predator–prey · weather · seasons · floods · wildfires · natural disasters ·
> long-term ecological dynamics

**Out of scope (validators actively reject these)**

> humans · civilization · villages · cities · roads · buildings · politics ·
> economy · culture · artificial structures

The `constraint` validator scans every name, description, and tag for a banned
lexicon and fails any world that smuggles in civilization.

---

## Architecture

```
                        ┌──────────────────────────────────────────────┐
   prompt.md  ──────►   │  ModelAdapter  (openai | anthropic | gemini   │
   (a task)             │   | ollama | vllm | mock)                     │
                        └───────────────────────┬──────────────────────┘
                                                │  raw JSON
                                                ▼
                        ┌──────────────────────────────────────────────┐
                        │  World (Pydantic v2)  — 12 typed sections     │
                        │  parsed & structurally validated              │
                        └───────────────────────┬──────────────────────┘
                                                │
                     ┌──────────────────────────┼──────────────────────────┐
                     ▼                           ▼                          ▼
             ┌───────────────┐          ┌────────────────┐        ┌─────────────────┐
             │  Validators   │          │  Knowledge     │        │    Metrics      │
             │  (11 + comp.) │◄────────►│  Graph (YAML   │◄──────►│  (9 + weighted  │
             │  ValidationRpt│          │  ontology)     │        │  overall /100)  │
             └───────┬───────┘          └────────────────┘        └────────┬────────┘
                     │                                                     │
                     └──────────────────────┬──────────────────────────────┘
                                            ▼
                        ┌──────────────────────────────────────────────┐
                        │  outputs/<Model>/<TaskID>/                    │
                        │    world.json validation.json metrics.json   │
                        │    report.json logs.txt                      │
                        └───────────────────────┬──────────────────────┘
                                                ▼
                        ┌──────────────────────────────────────────────┐
                        │  Reports: Markdown · JSON · HTML · Leaderboard│
                        └──────────────────────────────────────────────┘

  ── optional second artifact, graded separately ──────────────────────────

   world.json  ──►  stage-2 prompt  ──►  ModelAdapter  ──►  world.html
                    (JSON embedded                          (self-contained
                     verbatim)                                Three.js)
                                                                   │
                                                                   ▼
                                              ┌──────────────────────────────┐
                                              │  html_fidelity validator +   │
                                              │  metric — deterministic text │
                                              │  analysis, no rendering      │
                                              └──────────────┬───────────────┘
                                                              ▼
                                                 HTML fidelity score /100
                                                 (separate from overall_score)
```

Everything downstream of the `World` is deterministic: the same world always
produces the same validation report, the same metrics, and the same score.
The HTML branch is deterministic too — text/structure analysis only, never a
render or a screenshot.

---

## Installation

Requires **Python 3.12+**.

```bash
# Runtime install
pip install -e .

# With the development toolchain (pytest, ruff, mypy)
pip install -e '.[dev]'
```

Shapely depends on GEOS; on Debian/Ubuntu install `libgeos-dev` first (the
Docker image does this for you).

---

## Quickstart

```bash
# List every benchmark task WorldBench knows about
worldbench list

# Generate a world with the offline deterministic adapter and score it
worldbench run --task WC001_complete_floating_world --adapter mock

# Validate an existing world.json (schema + topology + hydrology + ecology + …)
worldbench validate path/to/world.json

# Score a world (weighted composite out of 100)
worldbench score path/to/world.json

# Render a report (Markdown / JSON / HTML) for a world.json
worldbench report path/to/world.json --format html --out report.html

# Aggregate every run into a leaderboard
worldbench leaderboard

# Check whether a world.html was actually built from a given world.json
worldbench score-html path/to/world.html --world path/to/world.json

# Score a model's whole output directory (world.json + world.html) at once
worldbench evaluate path/to/model_dir
```

The `mock` adapter needs no API keys and always returns a valid world, so the
full pipeline runs offline out of the box.

---

## Two-stage generation (JSON then HTML)

Every task is stage 1: generate `world.json`. An optional stage 2 turns that
exact JSON into a self-contained Three.js `world.html`. Both stages can run
either through a live adapter (`worldbench run`) or entirely by hand, pasting
prompts into any LLM chat website — no API key required:

```
prompts/01_json_generation_prompt_template.md   stage 1 recipe (per-task prompt, no single shared file)
prompts/02_html_generation_prompt_template.md   stage 2 template (task-agnostic, shared by every task)
prompts/<category>/<TASKID>/01_generate_json_prompt.md   a task's ready-to-paste stage-1 prompt
prompts/<category>/<TASKID>/02_generate_html_prompt.md   a task's ready-to-paste stage-2 prompt
```

Save results as `data/manual_generation/output/<model_name>/{world.json, world.html}`
and grade both with `worldbench evaluate data/manual_generation/output/<model_name>`.
See [`data/manual_generation/README.md`](data/manual_generation/README.md) for the full
walkthrough, and [`prompts/overview.md`](prompts/overview.md) for how the two
stages fit together.

HTML fidelity is graded by the `html_fidelity` validator + metric
(`benchmark/validators/html_fidelity.py`, `benchmark/metrics/html_fidelity.py`):
the HTML must embed the exact source JSON verbatim
(`<script type="application/json" id="world-data">`), the embedded id must
match, and the code must demonstrably parse and use that data rather than
leaving it inert next to a generic scene. It's excluded from `weights.yaml` and
never blended into the JSON's `overall_score` — it's its own number.

---

## The schema at a glance

A world is a single `World` object with **12 sections**. Every entity carries a
stable snake_case `id`, and all relationships are expressed as **id references**,
forming a graph the validators and metrics traverse.

| Section          | What it describes                                                            |
|------------------|------------------------------------------------------------------------------|
| `metadata`       | World identity, name, description, schema version, seed, tags                 |
| `layout`         | Global topology, edge type, bounds, sea level, named **regions**             |
| `terrain`        | Landforms (mountains, plains, cliffs, volcanoes …) with elevations           |
| `water`          | Rivers, lakes, oceans, waterfalls, springs and their **flow graph**          |
| `biomes`         | Climatic/ecological zones (temperature, moisture, elevation band, adjacency) |
| `flora`          | Plant species, their biomes, pollination mode, water needs                   |
| `fauna`          | Animal species, trophic role, locomotion, diet (flora & prey)                |
| `interactions`   | The explicit ecological web (predation, pollination, migration, symbiosis …) |
| `weather`        | Prevailing winds and per-biome climate behavior                              |
| `seasons`        | The annual cycle and per-season ecological modifiers                         |
| `natural_events` | Floods, wildfires, eruptions, migrations and what they affect                |
| `simulation`     | Declared long-term dynamics (predator–prey cycles, succession, drift)        |

The machine-readable contract lives at
[`benchmark/schemas/world_schema_v1.json`](benchmark/schemas/world_schema_v1.json)
and is regenerated from the Pydantic models with
`python -m benchmark.schemas.export_schema`. See [docs/schema.md](docs/schema.md)
for the full field reference.

---

## Scoring

The composite score (0–100) is a weighted sum of nine metrics:

| Metric                    | Weight | Measures                                                        |
|---------------------------|:------:|----------------------------------------------------------------|
| `schema_validity`         | 0.15   | Structural correctness & referential integrity                 |
| `completeness`            | 0.10   | How fully the 12 sections are populated                        |
| `terrain_correctness`     | 0.10   | Elevation coherence and landform consistency                   |
| `hydrology_correctness`   | 0.10   | Downhill flow, proper termination, source integrity            |
| `ecological_correctness`  | 0.20   | Species–biome fit and diet realism vs the knowledge graph      |
| `interaction_richness`    | 0.10   | Diversity and density of the ecological web                    |
| `spatial_coherence`       | 0.10   | Region/biome adjacency connectivity and plausibility           |
| `biodiversity`            | 0.10   | Diversity across categories, trophic roles, and biome types    |
| `creativity`              | 0.05   | Novelty proxies: biome variety, prose richness, events, tags   |

Weights are declared in
[`benchmark/metrics/weights.yaml`](benchmark/metrics/weights.yaml) and are easy
to retune. See [docs/validators.md](docs/validators.md) for what each validator
enforces.

A 10th metric, `html_fidelity`, scores the optional `world.html` companion
against its source JSON. It's deliberately **not** in `weights.yaml` and never
folds into `overall_score` — scoring an HTML artifact against a JSON reference
is a different question than judging the JSON alone, so it's reported as its
own separate number (`worldbench score-html` / `worldbench evaluate`).

---

## Model providers

Adapters call each provider's chat API over HTTP (via `httpx`) and read
credentials/endpoints from environment variables:

| Adapter     | Env vars                                             |
|-------------|------------------------------------------------------|
| `openai`    | `OPENAI_API_KEY` (optional `OPENAI_BASE_URL`)        |
| `anthropic` | `ANTHROPIC_API_KEY`                                  |
| `gemini`    | `GEMINI_API_KEY`                                     |
| `ollama`    | `OLLAMA_HOST` (defaults to `http://localhost:11434`) |
| `vllm`      | `VLLM_BASE_URL` (OpenAI-compatible server)           |
| `mock`      | none — deterministic offline adapter                 |

---

## Repository layout

```
worldbench/
├── benchmark/                 # the Python package (import name: benchmark)
│   ├── models/               # Pydantic v2 schema: World + 12 sections + graph
│   ├── schemas/              # versioned JSON Schema export
│   ├── knowledge/            # rule-based ecological ontology (YAML) + graph loader
│   ├── validators/           # 11 world validators + composite validate_world,
│   │                         #   plus html_fidelity.py (graded separately)
│   ├── metrics/              # 9 weighted metrics (score_world) + the standalone
│   │                         #   html_fidelity metric
│   ├── runner/               # task loader, orchestration, provider adapters
│   ├── reports/              # Markdown / JSON / HTML / leaderboard renderers
│   └── cli.py                # Typer CLI (worldbench …)
├── prompts/                  # benchmark tasks, grouped into 10 categories
│   ├── 01_world_layout/  …  10_stress_tests/
│   ├── <PREFIX###_slug>/     # one task folder: prompt, yaml configs, examples,
│   │                         #   plus 01_generate_json_prompt.md / 02_generate_html_prompt.md
│   ├── 01_json_generation_prompt_template.md   # stage-1 recipe (top level)
│   ├── 02_html_generation_prompt_template.md   # stage-2 shared template (top level)
│   └── overview.md           # two-stage pipeline explained + original world brief
├── data/manual_generation/         # no-API workflow: results in output/<model>/{world.json, world.html}
├── outputs/                   # generated run artifacts (per model / per task)
├── reports/                   # generated report artifacts
├── references/                # gitignored, local-only archive of prior experiments
├── docs/                      # architecture, schema, validators, guides
└── tests/                     # pytest suite for every layer
```

---

## Docker

```bash
# Build the image
docker build -t worldbench .

# Run the CLI (mounts outputs/ and reports/ back to the host)
docker compose run --rm worldbench worldbench list
docker compose run --rm worldbench worldbench run --task WC001_complete_floating_world --adapter mock
```

See `docker-compose.yml` for an optional local `ollama` service.

---

## Documentation

- [Architecture](docs/architecture.md) — components and data flow
- [Developer Guide](docs/developer_guide.md) — setup, tests, extending WorldBench
- [Schema Reference](docs/schema.md) — every section and field
- [Validator Reference](docs/validators.md) — what each validator checks
- [Task Authoring Guide](docs/task_authoring_guide.md) — writing new benchmark tasks
- [Contributing](docs/contributing.md) — workflow and standards

---

## License

MIT — see [LICENSE](LICENSE).
