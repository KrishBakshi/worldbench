<p align="center">
  <img src="public/world.png" alt="WorldBench: a generated floating natural world" width="612">
</p>

# worldbench

A single prompt for generating a self-contained Three.js `world.html` of a
floating biome island, plus a small site for browsing and interacting with
what different models produce from it.

There is no scoring, no schema, no CLI, just the prompt and your own eyes.

The model only ever sees the natural-language prompt. It is never shown
[`outputs/create.html`](outputs/create.html). That file is a hand-tuned
**ideal world** for humans: a qualitative target when judging outputs and
when refining the prompt. Models invent their own scale and layout; a
result can differ or be better if the ecological relationships and climate
logic hold.

## Running the site

```bash
npm install
npm run dev
```

Three pages:
- **Home**: a minimal floating-island animation, then "See Recent Tests"
  (up to 4 pinned tests).
- **About**: what worldbench is, the reasoning it tests, the biome legend
  image, and a placement graph of how the biomes relate to each other.
- **View Tests**: a grid of every test, each opening into its own page with
  an intro clip and the live, interactive `world.html` embedded below it.

## Adding a test

Drop a new folder in `public/tests/<slug>/` with:
- `meta.mdx`: frontmatter (`title`, `model`, `date`, `pinned`, `legacyPrompt`)
  plus optional notes
- `world.html`: the model's raw output
- optionally `intro.mp4` / `intro.webm` / `intro.gif`

No code changes needed, the site reads `public/tests/` at build time.

> The tests currently on the site were generated from an earlier, free-form
> version of the prompt (see each test's "legacy prompt" badge). They
> predate the live [`prompts/prompt.md`](prompts/prompt.md) and are
> placeholders until fresh outputs are generated against it.

## Using the prompt yourself

1. Open [`prompts/prompt.md`](prompts/prompt.md) (see also
   [`prompts/README.md`](prompts/README.md)).
2. Copy the entire file and paste it into a model.
3. Save the raw output (no surrounding prose) as `world.html`.
4. Open it in a browser and look around.
5. Optionally open `outputs/create.html` yourself as a qualitative reference.
6. Repeat with other models and compare the results side by side.
