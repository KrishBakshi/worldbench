# WL001_layout_floating_archipelago — Floating World Layout

**Category:** `01_world_layout`  ·  **Difficulty:** easy

Generate the spatial skeleton of a floating natural world: topology, bounds, and adjacent regions.

## Goal

This task stresses the global layout — a coherent floating landmass partitioned into named, correctly-adjacent regions.

## Scoring

The world is validated by the shared WorldBench validators plus this task's
`validator.py`, then scored with the metric emphasis in `scoring.yaml`
(defaults live in `benchmark/metrics/weights.yaml`).

## Running

```bash
worldbench run --task WL001_layout_floating_archipelago --adapter mock
worldbench validate examples/valid/world.json
```

## Examples

- `examples/valid/world.json` — a complete, coherent world that passes every
  validator for this task.
- `examples/invalid/world.json` — topology changed to `continent`, violating the required floating topology. It is included so
  authors can see exactly what this task is designed to catch.
