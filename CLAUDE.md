# worldbench — repo guide for Claude

This repo is just one prompt: `prompts/prompt.md` asks a model to generate
a self-contained Three.js `world.html` of a floating biome island directly
(no JSON intermediate, no schema, no scoring). Outputs are compared
visually, by opening each model's `world.html` in a browser.

**Models never see reference files.** Paste only `prompts/prompt.md`.
`outputs/create.html` is a hand-tuned ideal world for humans — to judge
results and to distill ecological / relational intent back into that
prompt. Never bake absolute dimensions, coordinates, or “copy this file”
language into the model-facing text.

## Layout
- `prompts/prompt.md` — the only model-facing prompt (copy-paste as-is).
- `prompts/README.md` — human notes for that prompt.
- `outputs/create.html` — ideal-world reference (human / qualitative only).
- `old/` — gitignored, local-only archive of the prior benchmark-era work
  (validators, schema, scored outputs, prior prompt pipeline). Not part of
  the live project; kept for reference only.

## Conventions
- No build step, no dependencies, no tests. Keep it that way — the whole
  point of this repo is to stay this simple.
