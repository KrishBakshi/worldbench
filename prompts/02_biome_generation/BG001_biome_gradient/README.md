# BG001_biome_gradient — Biome Climate Gradient

**Category:** `02_biome_generation`  ·  **Difficulty:** medium

Generate a believable gradient of biomes with climate bands that match each biome's ecological requirements.

## Goal

This task stresses biome placement — each biome's temperature and moisture must satisfy its ecological requirements.

## Scoring

The world is validated by the shared WorldBench validators plus this task's
`validator.py`, then scored with the metric emphasis in `scoring.yaml`
(defaults live in `benchmark/metrics/weights.yaml`).

## Running

```bash
worldbench run --task BG001_biome_gradient --adapter mock
worldbench validate examples/valid/world.json
```

## Examples

- `examples/valid/world.json` — a complete, coherent world that passes every
  validator for this task.
- `examples/invalid/world.json` — the desert biome is marked `polar`, an impossible climate for a desert. It is included so
  authors can see exactly what this task is designed to catch.
