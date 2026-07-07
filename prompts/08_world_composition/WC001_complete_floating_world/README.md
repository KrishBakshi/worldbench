# WC001_complete_floating_world — Complete Floating World

**Category:** `08_world_composition`  ·  **Difficulty:** hard

Generate a complete, self-contained floating island world across all 12 schema sections.

## Goal

This task stresses whole-world composition — every section populated and mutually consistent into one living island.

## Scoring

The world is validated by the shared WorldBench validators plus this task's
`validator.py`, then scored with the metric emphasis in `scoring.yaml`
(defaults live in `benchmark/metrics/weights.yaml`).

## Running

```bash
worldbench run --task WC001_complete_floating_world --adapter mock
worldbench validate examples/valid/world.json
```

## Examples

- `examples/valid/world.json` — a complete, coherent world that passes every
  validator for this task.
- `examples/invalid/world.json` — weather coverage for the forest biome is dropped, leaving a biome with no climate. It is included so
  authors can see exactly what this task is designed to catch.
