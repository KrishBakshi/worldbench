# TG001_volcanic_highlands — Volcanic Highlands Terrain

**Category:** `03_terrain_generation`  ·  **Difficulty:** medium

Generate dramatic terrain with coherent elevations, mountain ranges, and at least one active volcano.

## Goal

This task stresses terrain — coherent elevations (peaks above bases), connected landforms, and a genuine active volcano.

## Scoring

The world is validated by the shared WorldBench validators plus this task's
`validator.py`, then scored with the metric emphasis in `scoring.yaml`
(defaults live in `benchmark/metrics/weights.yaml`).

## Running

```bash
worldbench run --task TG001_volcanic_highlands --adapter mock
worldbench validate examples/valid/world.json
```

## Examples

- `examples/valid/world.json` — a complete, coherent world that passes every
  validator for this task.
- `examples/invalid/world.json` — the volcano is downgraded to a plain mountain, so the required `volcano` terrain type is absent. It is included so
  authors can see exactly what this task is designed to catch.
