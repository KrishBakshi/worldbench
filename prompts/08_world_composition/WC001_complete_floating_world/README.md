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

## Manual generation (no API key)

Two ready-to-paste prompts live right in this folder, for generating this
task's world by hand in any LLM chat website instead of via a live adapter:

- `01_generate_json_prompt.md` — stage 1. Bundles the system message,
  `prompt.md`, `constraints.yaml`, and the full JSON Schema into one paste.
  Save the reply as `manual_generation/output/<model_name>/world.json`.
- `02_generate_html_prompt.md` — stage 2. Paste your stage-1 JSON into it, get
  back a self-contained Three.js `world.html`. Save it next to the JSON, same
  model folder.

Then score both together in one shot:
```bash
worldbench evaluate manual_generation/output/<model_name>
```
See `manual_generation/README.md` at the repo root for the full walkthrough.

## Examples

- `examples/valid/world.json` — a complete, coherent world that passes every
  validator for this task.
- `examples/invalid/world.json` — weather coverage for the forest biome is dropped, leaving a biome with no climate. It is included so
  authors can see exactly what this task is designed to catch.
