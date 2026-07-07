# FA001_trophic_fauna — Trophic Fauna Population

**Category:** `06_fauna_population`  ·  **Difficulty:** hard

Populate biomes with animals whose habitats and diets are ecologically valid across trophic roles.

## Goal

This task stresses fauna — animals in habitats that support them, with complete, valid diets for their trophic roles.

## Scoring

The world is validated by the shared WorldBench validators plus this task's
`validator.py`, then scored with the metric emphasis in `scoring.yaml`
(defaults live in `benchmark/metrics/weights.yaml`).

## Running

```bash
worldbench run --task FA001_trophic_fauna --adapter mock
worldbench validate examples/valid/world.json
```

## Examples

- `examples/valid/world.json` — a complete, coherent world that passes every
  validator for this task.
- `examples/invalid/world.json` — a carnivorous lizard is left with an empty diet, an impossible trophic role. It is included so
  authors can see exactly what this task is designed to catch.
