# worldbench

**A benchmark for 3D world generation in Three.js: can a language model build a living world from one description?**

worldbench gives a model a single prompt: a detailed description of a floating voxel island with ten biomes, rivers, weather, wildlife, a day/night cycle and seasons. The model has to answer with **one self-contained HTML file** that renders that world in 3D with **Three.js**: the library imported from a CDN, with no build step and no separate asset files. The file has to open in a browser and just run, with a free camera to orbit, zoom and pan around the island. worldbench then checks, piece by piece, how much of the described world actually exists, looks right and behaves right.

<!-- Hero image goes here. -->

## What kind of benchmark this is

worldbench is an **execution-based, rubric-graded code-generation benchmark**: a text-to-3D *program synthesis* task, where the output is a program, not a mesh or an image, and it is judged by what that program does when it runs.

- **The model under test** is scored on a single artifact. It can be produced **one-shot**, or through a bounded **agentic repair loop** (generate → run in a headless browser → read the errors → patch with tools, for a fixed number of rounds). Either way, only the final `world.html` is graded. worldbench measures the world a model can build, not how well the model acts as an agent.
- **The evaluator is multimodal and partly agentic.** Grading combines four kinds of judge:
  - **LLM-as-a-judge** over the source code;
  - **VLM-as-a-judge** over frames of the running world;
  - **agent-as-a-judge** components: a browser-navigating agent that frames each biome, and a tool-using code-search agent that re-checks disputed items;
  - **deterministic metrics** on pixels and structure.
- **Scoring is criterion-referenced.** A fixed rubric of roughly two hundred weighted items, with a fixed maximum per test, so scores are absolute rather than relative to other models.

## Why this task

Most coding benchmarks ask for a function that passes unit tests. That measures correctness in the small, and says little about whether a model can carry a large, open-ended build from description to working artifact. Building a world is a better stress test because it asks for several things at once, all in one file, with nothing to lean on:

- **Holding a large spec in mind.** The prompt has well over a hundred concrete requirements, from "snow sits on the tree canopies, not only on the ground" to "where water meets lava, the rock becomes obsidian". Small details are where careful and careless models separate.
- **Spatial reasoning.** The biomes are described by their relationships, not coordinates: the snow forest sits in front of the mountains, the swamp lies on the jungle's far side, the desert has its own sandstone peaks and is never the volcano. The model has to hold a mental map and build to it.
- **Causal reasoning.** The world has to make ecological sense. Water runs from mountain melt through the jungle to the plains and out to a delta; the desert stays dry; rivers never flow into the volcano. A model that decorates instead of reasoning gets the pieces but not the logic.
- **Code that works, not code that looks right.** Thousands of lines of Three.js have to run, render and animate without crashing. A plausible-looking program that paints the ocean over empty space, or never moves its clouds, fails here even if its source reads well.
- **A world that is alive over time.** Rain falls, rivers flow, clouds drift, the sun crosses the sky, the seasons turn. Getting a static scene right is a different skill from getting a simulation right, and the prompt asks for both.

A model that does well has to be a competent engineer, a careful reader and a good spatial thinker in the same answer. That combination is what worldbench is trying to measure.

## What it tests

Every world is scored on the same five-step ladder, 280 points in total. The maximums are fixed, so totals compare directly across models. Test IDs read WC001–WC005, where WC stands for *World Check*: each test checks one property of the generated world.

| Test | Points | What it asks | Why it matters |
| --- | --- | --- | --- |
| [WC001 Voxel island](tests/WC001_voxel_world/README.md) | 40 | Is it the thing that was asked for: a cube-built island floating in a void, water resting on solid ground, and no visible rendering bugs? | The baseline. Before any detail counts, the world has to be the right kind of world and hold together physically. |
| [WC002 Coverage and placement](tests/WC002_biome_placement/Readme.md) | 20 | Is every one of the ten biomes built, and does each sit next to the right neighbours at the right height? | Spatial reasoning: turning a relational description into a coherent map. |
| [WC003 Micro-contents](tests/WC003_biome_micro_contents/README.md) | 100 | Does each biome contain what makes it that biome: cacti on the desert flats, mangroves in the swamp, a glowing crater on the volcano? | Depth of instruction following. This is where most of the prompt's detail lives. |
| [WC004 Physics](tests/WC004_biome_rendering/README.md) | 100 | Do things look right and move the right way: rain falls, rivers flow, clouds drift, lava glows? | Behaviour, not just appearance. A world can be well furnished and still be dead. |
| [WC005 Temporal cycles](tests/WC005_day_night_seasons/README.md) | 20 | Do the day/night cycle and the seasons actually change the world, rather than only a label on screen? | Stateful simulation: the world has to change over time for real. |

Each test's own README explains exactly how it is scored.

## How it checks, in brief

1. **Structural gate.** The file must exist, be non-empty and actually be a Three.js / WebGL page. A missing or wrong file fails fast with a reason, instead of scoring zero item by item.
2. **Instrumented capture.** The world runs in headless Chromium with its randomness seeded, so every reload builds the same island. A small, guarded patch to the world's *own* clock lets time of day and season be pinned. From that controlled run the capture records:
   - fixed camera views (overview, four orbit directions, four times of day, four seasons);
   - a **VLM navigator agent** that uses the world's legend and camera controls to frame each biome;
   - short **frame bursts** per biome, so motion can be measured;
   - a **blind identification** pass: an unlabeled VLM check that each saved frame really shows the biome it claims to.
3. **Dual-evidence judging, per rubric item.**
   - **Code half:** an LLM reads the source and must cite the exact lines that build the item. Each citation is **verified verbatim against the file**, which makes the judging *grounded*: a hallucinated quote earns nothing.
   - **Visual half:** a VLM judges the captured frames.
   - **Dynamics** (motion, day/night brightness, seasonal tint) are measured from the pixels themselves (frame differencing, luminance, chromaticity) rather than asked of the VLM.
   - **Disputes:** in the micro-contents test, when the frames show an item the code half missed, a **tool-using agent** searches a read-only, sandboxed copy of the source (grep, line reads, text pipelines) to settle it. Its quote is verified the same way.
4. **Aggregation.** Items are weighted into each test's fixed maximum. One cross-test rule applies: an ocean spilling over the void costs the physics test its coastal biome. Every verdict, quote and frame is saved alongside the score, so any result can be audited.

## Why the scores can be trusted

A benchmark is only as useful as its grading. worldbench is built around a few rules, most of them learned from checks that turned out to be fooled:

- **Evidence, not impressions.** Whenever a judge says "the code builds this", it must quote the lines that do it, and the quote is checked against the actual file. A judge cannot award points for code that isn't there.
- **Two witnesses.** Most items are judged twice: once from the source code and once from screenshots of the running world. Code can look right and render wrong; a screenshot can be framed on the wrong region. Requiring both catches each kind of mistake.
- **No keyword matching.** An early version counted biome keywords in the source. Every model scored full marks, and so did a one-line file containing nothing but the keywords. Checks keyed to names or phrasing were removed, because renaming a variable should never change a score.
- **Motion is measured, not assumed.** "It moves" only counts if consecutive frames actually differ, and "the lighting changes" only counts if the measured brightness does.
- **The same pipeline for every model.** Randomness in the world is seeded so every reload builds the same island, time of day is pinned, and every world goes through the same capture and the same judges. When the pipeline changes, every scored world is re-run.
- **Everything is recorded.** Each score keeps the quotes, frames and reasons behind it, so any result can be audited after the fact.

## Running it

Put a model's output at `inputs/<model>/world.html`, then:

```bash
uv run python -m eval.run <model>                      # the full ladder
uv run python -m eval.run <model> --test WC001,WC002   # a subset; other scores are kept
```

Results land in `outputs/<model>/validation.json`, with every test's evidence beside it. Screenshots are captured once per world and reused until the world changes. Capturing needs Node (it drives a headless browser).

To generate a world rather than supply one, `harness/generate.py` asks a model for `world.html` and gives it a few rounds to fix crashes and syntax errors before grading.

Judge settings (which model does which job, rate limits, retries) live in `eval/judge.yaml`; `.env` holds only API keys.

## Layout

```
prompts/prompt.md   the world description every model receives
inputs/<model>/     each model's world.html
outputs/<model>/    captured screenshots, per-test evidence and scores
tests/WC00N_*/      one folder per test, with its own README
eval/               grading: capture, judges, scoring
harness/            generation: prompt a model, then debug and fix its output
```
