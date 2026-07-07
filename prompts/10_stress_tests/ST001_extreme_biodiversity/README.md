# ST001_extreme_biodiversity — Extreme Biodiversity Stress Test

**Category:** `10_stress_tests`  ·  **Difficulty:** hard

Stress-test scale and coherence: many biomes, dense flora/fauna, and a large interaction web that still validates.

## Goal

This task stresses scale under coherence — a large, dense, biodiverse world that remains fully valid and internally consistent.

## Scoring

The world is validated by the shared WorldBench validators plus this task's
`validator.py`, then scored with the metric emphasis in `scoring.yaml`
(defaults live in `benchmark/metrics/weights.yaml`).

## Running

```bash
worldbench run --task ST001_extreme_biodiversity --adapter mock
worldbench validate examples/valid/world.json
```

## Examples

- `examples/valid/world.json` — a complete, coherent world that passes every
  validator for this task.
- `examples/invalid/world.json` — the interaction web is trimmed below the required minimum, failing the density constraint. It is included so
  authors can see exactly what this task is designed to catch.
