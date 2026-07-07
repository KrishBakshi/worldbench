# CN001_natural_only — Strictly Natural World

**Category:** `09_constraints`  ·  **Difficulty:** easy

Generate a world that strictly excludes all humans, civilization, and artificial structures.

## Goal

This task stresses scope discipline — a compelling world containing zero civilization or anthropogenic content.

## Scoring

The world is validated by the shared WorldBench validators plus this task's
`validator.py`, then scored with the metric emphasis in `scoring.yaml`
(defaults live in `benchmark/metrics/weights.yaml`).

## Running

```bash
worldbench run --task CN001_natural_only --adapter mock
worldbench validate examples/valid/world.json
```

## Examples

- `examples/valid/world.json` — a complete, coherent world that passes every
  validator for this task.
- `examples/invalid/world.json` — a coastal region is renamed 'Harbor Town Shore', injecting forbidden civilization terms. It is included so
  authors can see exactly what this task is designed to catch.
