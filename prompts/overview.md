# prompts/ — two-stage generation pipeline

WorldBench generates two artifacts per world, in two stages:

- **Stage 1 — JSON.** Task-specific, one per task. Each
  `prompts/NN_category/<TASKID>/` folder is stage 1 in full: `prompt.md` +
  `task.yaml`'s system prompt describe the world to generate as JSON. Tasks
  that support manual (no-API) generation also bundle a ready-to-paste
  `01_generate_json_prompt.md` right in that same folder. There is no single
  prompt that works for every task (the world asked for differs per task), so
  instead of a shared prompt, `prompts/01_json_generation_prompt_template.md`
  documents the assembly recipe every task's stage-1 prompt follows, plus a
  pointer to a ready-made example.
- **Stage 2 — HTML.** Task-agnostic, one shared file:
  `prompts/02_html_generation_prompt_template.md`. It takes whatever JSON
  stage 1 produced and turns it into a self-contained Three.js `world.html`.
  Every task's own `02_generate_html_prompt.md` is that same template with a
  `<PASTE world.json HERE>` slot.

Stage 1's output is graded on its own (`worldbench validate`/`score`); stage
2's output is graded separately, against stage 1's JSON as ground truth
(`worldbench score-html`, or both at once via `worldbench evaluate`). See
`data/manual_generation/README.md` for the full walkthrough of running both stages
by hand.

------------------------------------------------------------------------

# Floating Biome Island with Ocean --- World Description

The section below is the original creative brief the benchmark's canonical
sample world and several tasks' prompts were derived from — kept as reference
for anyone writing new task prompts, not itself one of the two pipeline
stages above.

## Overview

A massive floating landmass hangs motionless in an infinite black void.
The island is viewed from a high isometric perspective, revealing nearly
its entire surface. Unlike a traditional floating continent, much of the
outer perimeter is bordered by a shallow coastal ocean and sandy beaches
before the terrain rises inland into distinct biomes. The ocean itself
is suspended with the island, ending at dramatic cliff edges where
countless waterfalls plunge into darkness.

------------------------------------------------------------------------

# World Layout

The island is approximately rectangular with naturally eroded edges.

From northwest to southeast the terrain gradually transitions through
multiple ecosystems:

1.  Snow Mountains
2.  Temperate Highlands
3.  Dense Forest
4.  Central Grasslands
5.  Flowering Grove
6.  Desert
7.  Volcanic Wasteland
8.  Snowy Conifer Forest
9.  Coastal Ocean and Beaches surrounding much of the southern and
    western edges

------------------------------------------------------------------------

# Biomes

## 1. Snow Mountain Range

-   Tall alpine peaks
-   Snow-covered ridges
-   Rocky cliffs
-   Low clouds hugging mountains
-   Meltwater streams

------------------------------------------------------------------------

## 2. Temperate Highlands

-   Rocky hills
-   Sparse vegetation
-   Elevated plateaus
-   River sources

------------------------------------------------------------------------

## 3. Dense Forest

-   Thick emerald canopy
-   Large mature trees
-   Rocky clearings
-   Major waterfall
-   Small inland ponds

------------------------------------------------------------------------

## 4. Central Grasslands

-   Rolling green plains
-   Winding rivers
-   Stone mesas
-   Gentle hills
-   Scattered woodland patches

------------------------------------------------------------------------

## 5. Flowering Grove

-   Pink flowering trees
-   Small streams
-   Decorative meadow
-   Transitional ecosystem

------------------------------------------------------------------------

## 6. Desert

-   Golden sand
-   Sandstone formations
-   Dry riverbeds
-   Rock spires
-   Small oasis lakes

------------------------------------------------------------------------

## 7. Volcanic Wasteland

-   Active volcanoes
-   Lava rivers
-   Black basalt
-   Smoke plumes
-   Cracked glowing ground

------------------------------------------------------------------------

## 8. Snowy Conifer Forest

-   Pine trees
-   Patchy snow
-   Frozen creeks
-   Rocky terrain

------------------------------------------------------------------------

# Coastal Ocean

The southern and western edges are surrounded by brilliant turquoise
coastal waters.

Features include:

-   Shallow lagoons
-   Deep blue offshore water
-   Rocky shoreline
-   Small islands and reefs
-   Calm wave patterns
-   Natural coves
-   River mouths entering the sea

------------------------------------------------------------------------

# Beaches

The coastline transitions naturally from grasslands and forests into
beaches.

Beach characteristics:

-   Bright white sand
-   Curved bays
-   Palm trees in warm regions
-   Rocky headlands
-   Gentle shoreline
-   Clear shallow water
-   Coastal vegetation

------------------------------------------------------------------------

# Rivers

-   Mountain meltwater feeds rivers.
-   Tributaries merge through the plains.
-   Rivers widen approaching the coast.
-   Water enters the suspended ocean.
-   Ocean spills over cliff edges as waterfalls.

------------------------------------------------------------------------

# Cliffs and Underside

-   Vertical rock walls around the perimeter
-   Massive stone foundation
-   Numerous waterfalls
-   Floating rock fragments beneath island
-   Blue glowing mineral seams in places

------------------------------------------------------------------------

# Color Palette

  Region      Colors
  ----------- ----------------------------
  Ocean       Turquoise, deep blue, cyan
  Beaches     White, cream, tan
  Forest      Emerald, dark green
  Plains      Green, olive
  Mountains   White, blue-grey
  Desert      Gold, ochre
  Volcano     Black, orange, crimson
  Rivers      Cyan

------------------------------------------------------------------------

# Lighting

-   Clear daylight
-   Strong sunlight from upper-left
-   Crisp terrain shadows
-   High visibility
-   Black void background with no stars or atmosphere

------------------------------------------------------------------------

# Visual Composition

The ocean creates a natural border around the floating continent while
preserving the dramatic cliff edges. Sandy beaches soften the transition
between land and water, contrasting with forests, snowy peaks, deserts,
and volcanic terrain. Rivers connect nearly every biome before reaching
the suspended sea, giving the world the appearance of a complete
self-contained ecosystem.

------------------------------------------------------------------------

# Intended Applications

-   Procedural world generation
-   Open-world game concept
-   Ecology simulation
-   RTS overworld
-   Survival sandbox
-   Fantasy map design
-   AI environment benchmark
-   Worldbuilding reference
