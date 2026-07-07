# WorldBench Task Authoring Guide

A **task** is a self-contained benchmark unit: a prompt asking a model to
generate a world (or part of one), plus the configuration and examples needed to
score it. Tasks live under `prompts/`, grouped into ten categories.

## Categories

```
prompts/
├── 01_world_layout/
├── 02_biome_generation/
├── 03_terrain_generation/
├── 04_water_systems/
├── 05_flora_population/
├── 06_fauna_population/
├── 07_ecosystem_interactions/
├── 08_world_composition/
├── 09_constraints/
└── 10_stress_tests/
```

Each category holds one or more **task folders**.

## Naming convention

A task folder is named `<PREFIX><NNN>_<slug>`:

- `PREFIX` — a short uppercase category code (e.g. `WL` world_layout, `BG` biome,
  `TG` terrain, `WS` water, `FL` flora, `FA` fauna, `EI` ecosystem interactions,
  `WC` world composition, `CN` constraints, `ST` stress test).
- `NNN` — a zero-padded sequence number (`001`, `002`, …).
- `slug` — a lowercase snake_case description.

Example: `prompts/08_world_composition/WC001_complete_floating_world/`.

## Required files

Every task folder contains:

```
<TASK>/
├── prompt.md            # the instruction shown to the model
├── metadata.yaml        # task identity: id, title, category, difficulty, author, tags
├── task.yaml            # what to generate, which schema sections are in scope
├── constraints.yaml     # machine-checkable requirements (min counts, required types, forbidden terms)
├── scoring.yaml         # metric weights / pass thresholds for this task
├── expected_schema.json # the schema (or task-scoped subset) the output must satisfy
├── validator.py         # task-specific checks, composing the shared validators
├── README.md            # human notes: intent, rationale, what "good" looks like
├── examples/
│   ├── valid/           # ≥1 world.json that should PASS
│   └── invalid/         # ≥1 world.json that should FAIL (document why)
└── assets/              # optional supporting files
```

## What each YAML file contains

**`metadata.yaml`**

```yaml
id: WC001_complete_floating_world
title: Complete Floating World
category: 08_world_composition
difficulty: hard            # easy | medium | hard | stress
author: WorldBench
tags: [floating, full-world, ecosystem]
```

**`task.yaml`**

```yaml
objective: >
  Generate a complete, coherent floating natural world with all 12 schema
  sections populated and a self-consistent ecosystem.
schema_sections: [metadata, layout, terrain, water, biomes, flora, fauna,
                  interactions, weather, seasons, natural_events, simulation]
output: single World JSON document
```

**`constraints.yaml`** — consumed by the constraint validator:

```yaml
min_biomes: 4
min_flora: 6
min_fauna: 6
min_interactions: 5
required_biome_types: [alpine, desert, temperate_forest]
required_features: [waterfall]
forbidden_terms: [city, village, road]   # merged with the universal scope ban
```

**`scoring.yaml`** — optional per-task reweighting/thresholds:

```yaml
weights:                # overrides benchmark/metrics/weights.yaml for this task
  ecological_correctness: 0.25
  hydrology_correctness: 0.15
pass_threshold: 70      # overall score required to "pass" the task
```

## Writing `validator.py`

A task validator composes the shared validators and adds task-specific checks.
Keep it thin — most logic should live in the shared library.

```python
"""Task validator for WC001: complete floating world."""

from __future__ import annotations

from benchmark.models import World
from benchmark.results import Finding, Severity, ValidationResult
from benchmark.validators import validate_world


def validate(world: World, constraints: dict | None = None) -> ValidationResult:
    # Run the full shared suite (returns a ValidationReport).
    report = validate_world(world, constraints=constraints)

    findings: list[Finding] = list(report.all_findings)
    checks = sum(r.checks_run for r in report.results)

    # Task-specific rule: a floating world must have at least one body that
    # exits the world edge as a waterfall into the void.
    if not any(b.exits_world for b in world.water.bodies):
        findings.append(
            Finding(
                code="WC001-001",
                severity=Severity.ERROR,
                message="A complete floating world must have water exiting the edge.",
            )
        )
        checks += 1

    return ValidationResult.build("WC001", findings, checks)
```

## How examples are used

- **`examples/valid/`** — each `world.json` must parse and pass the task
  validator. They double as fixtures and as a reference for prompt authors.
- **`examples/invalid/`** — each must **fail** for the reason documented in the
  task README (e.g. "river flows uphill", "cactus placed in a rainforest",
  "region named 'Harbor Town' trips the scope scanner"). Invalid examples pin
  down exactly what the task is testing.

The test suite loads valid examples and asserts they pass, and loads invalid
examples and asserts they fail — so broken examples surface immediately.

## Checklist for a new task

- [ ] Folder named `<PREFIX><NNN>_<slug>` under the right category
- [ ] All eight required files present
- [ ] `constraints.yaml` requirements are actually checkable by the validator
- [ ] At least one passing and one failing example, with the failure documented
- [ ] `validator.py` reuses `validate_world` rather than re-implementing checks
- [ ] `worldbench validate examples/valid/world.json` passes; the invalid one fails
