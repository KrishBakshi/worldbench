# worldbench — repo guide for Claude

This repo is just one prompt: `prompts/generate_world_html.md` asks a model
to generate a self-contained Three.js `world.html` of a floating biome
island directly (no JSON intermediate, no schema, no scoring). Outputs are
compared visually, by opening each model's `world.html` in a browser.

## Layout
- `prompts/generate_world_html.md` — the only prompt in the repo.
- `old/` — gitignored, local-only archive of the prior benchmark-era work
  (validators, schema, scored outputs, prior prompt pipeline). Not part of
  the live project; kept for reference only.

## Conventions
- No build step, no dependencies, no tests. Keep it that way — the whole
  point of this repo is to stay this simple.
