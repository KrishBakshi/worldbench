# WS001_river_to_sea — River-to-Sea Hydrology

**Category:** `04_water_systems`  ·  **Difficulty:** medium

Generate a hydrology network where meltwater becomes rivers that flow downhill and terminate in the sea.

## Goal

This task stresses hydrology — a connected flow network where every flowing body runs downhill and terminates properly.

## Scoring

The world is validated by the shared WorldBench validators plus this task's
`validator.py`, then scored with the metric emphasis in `scoring.yaml`
(defaults live in `benchmark/metrics/weights.yaml`).

## Running

```bash
worldbench run --task WS001_river_to_sea --adapter mock
worldbench validate examples/valid/world.json
```

## Examples

- `examples/valid/world.json` — a complete, coherent world that passes every
  validator for this task.
- `examples/invalid/world.json` — the main river's outlet is removed (flows_to null, exits_world false), so it dangles. It is included so
  authors can see exactly what this task is designed to catch.
