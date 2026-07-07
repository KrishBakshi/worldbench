# WorldBench Architecture

This document describes how WorldBench is put together and how data flows through
it, from a benchmark task to a leaderboard entry.

## Design principles

1. **The world is the artifact.** A model under test emits exactly one JSON
   document conforming to the `World` schema. Everything else — validation,
   scoring, reporting — is deterministic post-processing of that document.
2. **Structure over aesthetics.** WorldBench never renders or judges images. It
   reasons about a typed graph of natural entities.
3. **Rules, not references.** There is no golden world. Correctness is defined by
   natural laws (hydrology, ecology, topology) encoded as validators and an
   ontology, not by similarity to an answer key.
4. **Everything is a graph.** Entities carry stable `id`s and refer to one
   another by id. `benchmark/models/graph.py` projects a `World` into a
   `networkx` graph so validators and metrics can traverse relationships
   directly.

## Component map

```
benchmark/
├── models/        Pydantic v2 schema. World + 12 sections. Local validation only
│                  (shapes, ranges, per-entity invariants). graph.py builds the
│                  world relationship graph; food_web() extracts the trophic subgraph.
├── schemas/       export_schema.py emits world_schema_v1.json from the models.
├── knowledge/     YAML ontology (one file per concept) + KnowledgeGraph loader.
│                  The single source of ecological truth (what supports/flows/borders what).
├── results.py     Shared, dependency-light result types: Finding, ValidationResult,
│                  ValidationReport, MetricResult, ScoreReport. Every layer agrees on these.
├── validators/    11 validators (schema, topology, hydrology, biome, flora, fauna,
│                  ecology, interaction, constraint, weather, simulation) + composite
│                  validate_world(). Each returns a ValidationResult of Findings.
├── metrics/       9 metrics + weighted overall score_world(). Decoupled from validators:
│                  score_world optionally consumes a pre-computed ValidationReport.
├── runner/        loader.py finds and parses task folders; adapters/ call model
│                  providers; runner.py orchestrates the full pipeline and writes outputs.
├── reports/       Renderers for Markdown, JSON, HTML, and the cross-run leaderboard.
└── cli.py         Typer app exposing list / run / validate / score / report / leaderboard.
```

## Data flow

```
task folder (prompts/<category>/<TASK>/)
   prompt.md · task.yaml · constraints.yaml · scoring.yaml · expected_schema.json
        │
        │  runner.loader loads the task
        ▼
ModelAdapter.generate(prompt)  ──►  raw JSON string
        │
        │  parse + structural validation
        ▼
World  (Pydantic)  ──►  build_world_graph(world)  /  food_web(world)
        │
        ├──►  validators.validate_world(world, constraints)  ──►  ValidationReport
        │            (consults knowledge.KnowledgeGraph)
        │
        └──►  metrics.score_world(world, report)             ──►  ScoreReport
                     (consults knowledge.KnowledgeGraph; reuses the report's pass-rates)
        │
        ▼
outputs/<Model>/<TaskID>/
   world.json · validation.json · metrics.json · report.json · logs.txt
        │
        ▼
reports/  (Markdown · JSON · HTML)   and   leaderboard  (aggregated across runs)
```

## Why validators and metrics are separate

Validators answer a **boolean-ish** question ("does this world break a natural
law?") and emit typed `Finding`s at `error` / `warning` / `info` severity.
Metrics answer a **graded** question ("how good is this world, 0–100?").

They share the `results.py` contract but not their logic. `score_world` accepts
an optional `ValidationReport` so the runner can validate once and let the
metrics reuse those pass-rates — but metrics can also stand alone, computing
what they need directly from the world and the knowledge graph. This keeps the
two layers independently testable and lets you rescore without re-validating (or
vice versa).

## The knowledge graph

`benchmark/knowledge/` holds one YAML file per ecological **concept** (a biome,
terrain, or water type). Each file declares what that concept `supports` (flora
and fauna categories), what climate it `requires`, which concepts it may be
`adjacent_to` or is `incompatible_with`, and — for water — where it `flows_to`.
Enum values from the schema (e.g. the biome type `temperate_forest`) map onto
concepts (`forest`) via each file's `aliases`. The loader assembles everything
into a cached `KnowledgeGraph` exposing queries like `supports_flora(biome,
category)`, `may_flow_to(a, b)`, and `may_be_adjacent(a, b)`. Adding ecological
knowledge is a matter of editing YAML, not Python.

## Extension points

| To add …            | Do this …                                                                 |
|---------------------|---------------------------------------------------------------------------|
| a schema field      | edit the relevant `benchmark/models/*.py`, then regenerate the JSON Schema |
| ecological rules    | add or edit a YAML file in `benchmark/knowledge/`                          |
| a validator         | add a module in `benchmark/validators/` and register it in `composite.py` |
| a metric            | add a module in `benchmark/metrics/`, register it, and set its weight      |
| a model provider    | add an adapter in `benchmark/runner/adapters/` implementing the interface  |
| a benchmark task    | add a task folder under `prompts/<category>/` (see the task authoring guide)|
| a report format     | add a renderer in `benchmark/reports/`                                     |

See the [Developer Guide](developer_guide.md) for step-by-step instructions.
