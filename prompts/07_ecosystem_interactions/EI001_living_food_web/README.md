# EI001_living_food_web — Living Food Web

**Category:** `07_ecosystem_interactions`  ·  **Difficulty:** hard

Generate a rich, acyclic ecological web: predation, herbivory, pollination, migration, symbiosis, decomposition.

## Goal

This task stresses the ecological web — a rich, varied, acyclic set of interactions binding species together.

## Scoring

The world is validated by the shared WorldBench validators plus this task's
`validator.py`, then scored with the metric emphasis in `scoring.yaml`
(defaults live in `benchmark/metrics/weights.yaml`).

## Running

```bash
worldbench run --task EI001_living_food_web --adapter mock
worldbench validate examples/valid/world.json
```

## Examples

- `examples/valid/world.json` — a complete, coherent world that passes every
  validator for this task.
- `examples/invalid/world.json` — a reef fish is made to prey on the shark that eats it, creating an impossible trophic cycle. It is included so
  authors can see exactly what this task is designed to catch.
