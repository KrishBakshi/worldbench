# Prompt — generate a self-contained Three.js world.html

This is the only prompt in this repo. Paste it into a model, save the raw
output as `world.html`, open it in a browser, and look at it. Run the same
prompt across different models and compare the resulting HTML files side by
side — that's the entire workflow.

---

```text
Build a single, self-contained HTML file that renders the world described
below as an explorable 3D scene using Three.js (CDN import is fine — no
build step, no separate asset files). It must just open in a browser and
run, with a free camera (e.g. OrbitControls) so a visitor can orbit, zoom,
and pan around the whole world.

Output ONLY the complete HTML file — no prose, no commentary, no code fences.

────────────────────────────────────────────────────────
THE WORLD
────────────────────────────────────────────────────────

# Floating Biome Island with Ocean — World Description

## Overview

A floating landmass hangs motionless in an infinite black void.
The island is viewed from a high isometric perspective, revealing nearly
its entire surface. Give each biome room to read clearly from orbit —
spread the NW→SE sequence so mountains, jungle, plains, desert, volcano,
and conifer forest are distinct regions with visible transitions, not a
tight cluster. Flora and fauna should still feel alive within each biome,
without overcrowding the whole island into one muddled mass.

Unlike a traditional floating continent, much of the outer perimeter is
bordered by a shallow coastal ocean and sandy beaches before the terrain
rises inland into distinct biomes. Elevations are exaggerated and
dramatic: peaks climb high, valleys cut deep, and cliffs drop sharply.
The ocean itself is suspended with the island, ending at dramatic cliff
edges where countless waterfalls plunge into darkness.

## World Layout

The island is approximately rectangular with naturally eroded edges.

From northwest to southeast the terrain gradually transitions through
multiple ecosystems:

1.  Snow Mountains
2.  Temperate Highlands
3.  Dense Jungle / Rainforest
4.  Central Grasslands
5.  Flowering Grove
6.  Desert
7.  Volcanic Wasteland
8.  Snowy Conifer Forest
9.  Coastal Ocean and Beaches surrounding much of the southern and
    western edges

## Scale and Density (important)

-   Prefer a clearly legible island with generous landmass: biomes spaced
    so each reads as its own region from a high orbit.
-   Avoid collapsing adjacent biomes into one muddled mass — especially
    grassland vs flowering grove, and desert vs volcanic mountain.
-   Within each biome, flora and fauna should feel abundant.
-   Mountains and the volcano should dominate the skyline; desert flats
    and plains sit in the bowls between them.

## Ecological reasoning (core of the test)

Layout and systems must follow ecological logic, not decoration:

-   Water stays in the wet corridor: mountain melt → highlands →
    weave through jungle → grasslands → coastal delta / ocean.
-   Flowering grove is a moist offshoot of the plains — not a stop on
    the way into the desert.
-   Desert is arid: a vast flat basin with its own sandstone desert
    mountains; cacti and life spread across the flats (not clustered
    away from the sand); only fading dry washes; no through-rivers
    into the volcano.
-   Volcano is a separate tall cone with visible lava tributaries and
    lava pools on volcanic ground. Where water meets lava, rock
    quenches to obsidian.
-   Rain falls downward from moving cloud decks over wet biomes; snow
    falls from moving clouds over alpine / conifer terrain.
-   Snowy trees carry snow on their canopies, not only on the ground.

## Biomes

### 1. Snow Mountain Range

-   Tall alpine peaks (high relief — not gentle hills)
-   Snow-covered ridges and steep rocky cliffs
-   Low clouds hugging mountains
-   Meltwater streams feeding the river network
-   Active blizzard / snowstorm weather: drifting snow particles,
    wind streaks, occasional whiteout gusts along ridges

### 2. Temperate Highlands

-   Rocky hills and elevated plateaus
-   Sparse scrub and hardy vegetation
-   Primary river sources and early tributaries
-   Occasional mist and light rain

### 3. Dense Jungle / Rainforest

-   Thick emerald canopy, layered undergrowth
-   Large mature trees packed closely together
-   Rocky clearings, inland ponds, major waterfall
-   Persistent jungle rain: visible rainfall shafts, wet canopy sheen,
    rising mist / water evaporation columns after showers
-   Cycle of rain → surface water → evaporation mist → rain again

### 4. Central Grasslands

-   Open green plains, clearly distinct from the flowering grove
-   Dense winding river network with many tributaries
-   Scattered woodland copses and yellow/white wildflowers
-   Not pink — keep meadow color green/olive

### 5. Flowering Grove

-   Separated from the grasslands (e.g. its own moist basin)
-   Dense pink flowering canopy and pink-tinted meadow floor
-   Small streams fed from the plains moisture corridor
-   Visually different from grassland at a glance

### 6. Desert

-   Mostly flat arid land (low relief dunes / hardpan)
-   Distinct desert mountains / sandstone peaks rising from that flat
    floor — these are NOT the volcano
-   Dry washes that fade out; no perennial river through to the volcano
-   Rock spires, sparse cactus, oasis only if ecologically justified
-   Living desert weather: desert winds, sandstorm / dust storm

### 7. Volcanic Wasteland

-   A proper tall stratovolcano cone with glowing crater — not a flat
    lava puddle or a collapsed desert plateau
-   Lava tributaries flowing down the cone into lower lava pools on
    volcanic ground only
-   Black basalt fields, ash plumes, periodic eruptions

### 8. Snowy Conifer Forest

-   Dense pine stands with snow ON the tree canopies as well as ground
-   Patchy snow, cold cloud deck directly above the forest
-   Snowstorm weather shared with the alpine zone

## Coastal Ocean

The southern and western edges are surrounded by brilliant turquoise
coastal waters.

Features include:

-   Shallow lagoons and deep blue offshore water
-   Rocky shoreline, small islands and reefs
-   Calm wave patterns and natural coves
-   Multiple river mouths and a visible delta where channels
    braid, fan out, and mix into the surrounding ocean
-   Freshwater visibly meeting and blending into saltwater at
    the mouths

## Beaches

The coastline transitions naturally from grasslands and forests into
beaches.

Beach characteristics:

-   Bright white sand, curved bays
-   Palm trees in warm regions
-   Rocky headlands, gentle shoreline
-   Clear shallow water and coastal vegetation

## Rivers and Hydrology

Build a rich branching system that obeys ecological law:

-   Mountain meltwater and highland springs feed many headwaters.
-   Tributaries weave evenly through the jungle canopy (not skirting
    past it toward desert), then continue into grasslands.
-   Rivers widen toward the coast and form a distributary delta before
    entering the suspended ocean.
-   Grove receives a moist feeder from the plains — not a desert route.
-   Desert stays dry aside from fading washes; no river into the volcano.
-   Show the water cycle: rain and melt feed rivers; jungle/coast heat
    drives evaporation mist; moisture returns as rain or snow.

## Climate, Clouds, Seasons, and Sun

-   Rain, snow, mist, sandstorm, ash, and cloud decks should arrive in
    natural cyclic bursts — fade in, hold, fade out, then clear for a
    quiet gap — staggered by biome so weather is not permanently on.
-   Snow/blizzard falls from drifting cloud decks over mountain and
    conifer terrain — clouds hug those biomes, not the empty void.
-   Desert: winds and sandstorm across a vast sandy basin. Volcano:
    eruptions, ash, lava rivers into clear lava pools; water+lava
    contact becomes obsidian.
-   Implement a reliable seasonal cycle (spring → summer → autumn →
    winter) that clearly modulates rain/snow intensity and light tint.
-   Include a visible square sun that orbits on a cyclic day pattern.

## Cliffs and Underside

-   Vertical rock walls around the perimeter
-   Tall stone foundation matching the heightened elevations above
-   Numerous waterfalls
-   Floating rock fragments beneath the island
-   Blue glowing mineral seams in places

## Color Palette

  Region      Colors
  ----------- ----------------------------
  Ocean       Turquoise, deep blue, cyan
  Beaches     White, cream, tan
  Jungle      Emerald, dark green, mist grey
  Plains      Green, olive
  Mountains   White, blue-grey
  Desert      Gold, ochre, dust haze
  Volcano     Black, orange, crimson, ash grey
  Rivers      Cyan
  Weather     Soft rain blue, snow white, sand tan, ash grey

## Lighting

-   Square sun drives cyclic daylight; seasonal tint modulates warmth
-   Local weather tinting (cooler in storms, ember glow near volcano)
-   Crisp terrain shadows when weather is clear
-   High visibility of the whole island from a comfortable orbit
-   Black void background with no stars or atmosphere dome

## Visual Composition

A large, ecologically reasoned floating continent: distinct biomes with
breathing room; wet-corridor rivers weaving the jungle into a coastal
delta; flat desert with its own sandstone mountains separated from a
tall erupting volcano; grassland vs pink grove clearly differentiated;
cloud-sourced rain and snow; snow-laden conifers; a square sun and a
reliable seasonal cycle. The ocean borders the land before plunging over
cliff edges into the void.
```
