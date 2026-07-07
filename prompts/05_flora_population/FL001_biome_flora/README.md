# FL001_biome_flora — Biome-Appropriate Flora

**Category:** `05_flora_population`  ·  **Difficulty:** medium

Populate each biome with plant species that can actually grow there, with coherent pollination.

## Goal

This task stresses flora placement — every plant species must be able to grow in each biome it is assigned to.

## Scoring

The world is validated by the shared WorldBench validators plus this task's
`validator.py`, then scored with the metric emphasis in `scoring.yaml`
(defaults live in `benchmark/metrics/weights.yaml`).

## Running

```bash
worldbench run --task FL001_biome_flora --adapter mock
worldbench validate examples/valid/world.json
```

## Examples

- `examples/valid/world.json` — a complete, coherent world that passes every
  validator for this task.
- `examples/invalid/world.json` — a sun cactus is planted in the temperate forest, which cannot support cacti. It is included so
  authors can see exactly what this task is designed to catch.
