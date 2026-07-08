# data/manual_generation — evaluate any LLM without an API key

Generate a WorldBench world by hand (paste prompts into any chat website),
then score it locally. No adapters, no API keys, no live `worldbench run` — the
CLI only ever grades files that already exist on disk.

This folder holds only your **results** (`output/`). The prompts themselves
live in one place — inside each task's own folder under `prompts/` — so
there's a single source of truth instead of a second copy in here.

## Layout

```
prompts/08_world_composition/WC001_complete_floating_world/
├── prompt.md, task.yaml, constraints.yaml, ...   the canonical task definition
├── 01_generate_json_prompt.md                     stage 1: paste this, get world.json back
└── 02_generate_html_prompt.md                     stage 2: paste your JSON into this, get world.html back

data/manual_generation/
├── README.md                                     this file
└── output/                                       one directory per model/run you test
    ├── claude_opus_4_8/
    │   ├── world.json
    │   └── world.html
    ├── deepseek_v4_expert/
    │   └── world.json                             (html not generated yet — that's fine)
    └── ...
```

## Quick start

Full walkthrough lives in
`prompts/08_world_composition/WC001_complete_floating_world/README.md`
("Manual generation" section). The short version:

1. Paste `prompts/08_world_composition/WC001_complete_floating_world/01_generate_json_prompt.md`
   into an LLM → save its reply as `output/<your_model_name>/world.json`.
2. Paste `prompts/08_world_composition/WC001_complete_floating_world/02_generate_html_prompt.md`
   (with your JSON inserted) into an LLM → save its reply as
   `output/<your_model_name>/world.html`.
3. Score both at once:
   ```bash
   .venv/bin/worldbench evaluate data/manual_generation/output/<your_model_name>
   ```

## Why `output/` isn't the same as the repo's `outputs/`

- `data/manual_generation/output/<model>/` — the **raw artifacts** you produced by
  hand (`world.json`, `world.html`). This is what you create and what
  `worldbench evaluate` reads.
- `outputs/<adapter>__<model>/<task_id>/` (repo root) — the **scored bundle
  format** `worldbench leaderboard` scans (`report.json` + friends). Getting a
  manual result onto the leaderboard means writing into that structure
  separately; `evaluate` doesn't do this automatically today.
