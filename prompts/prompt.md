Build a single, self-contained HTML file that renders the world described
below as an explorable 3D scene using Three.js (CDN import is fine — no
build step, no separate asset files). It must just open in a browser and
run, with a free camera (e.g. OrbitControls) so a visitor can orbit, zoom,
and pan around the whole world.

Output ONLY the complete HTML file — no prose, no commentary, no code fences.

Choose your own overall scale. What matters is relative placement,
ecological causality, and clear visual reading from orbit — not any
particular absolute size or fixed elevation numbers.

────────────────────────────────────────────────────────
THE WORLD
────────────────────────────────────────────────────────

# Floating Biome Island with Ocean — World Description

## Visual style (required)

Minecraft-like voxel / block aesthetic throughout:

-   Terrain, cliffs, water, lava, trees, flora, and structures are built
    from chunky axis-aligned cubes and blocky stacked forms — not smooth
    organic meshes, not photoreal terrain, not low-poly “soft” stylization.
-   Flat, solid face colors (Lambert / unlit-friendly); no PBR gloss, no
    detailed textures required. Pixel-chunk readability from orbit.
-   Trees and plants are stacked blocks / simple voxel silhouettes
    (trunk + canopy cubes), not billboards or smooth cones.
-   Weather and particles can be simple quads or small cubes, but the
    landmass itself must read as a voxel island.

## Overview

A floating landmass hangs motionless in an infinite black void.
Viewed from a high orbit, nearly the entire surface should be readable at
once. Each biome needs room to read as its own region — distinct
transitions, not a muddled cluster. Flora and fauna should feel alive
inside each biome without overcrowding the whole island.

Much of the outer perimeter is bordered by shallow coastal ocean and sandy
beaches before terrain rises inland. Elevations are exaggerated and
dramatic relative to each other: peaks dominate, shelves sit mid-height,
plains are low and open, cliffs drop sharply. The ocean is suspended with
the island and ends at cliff edges where waterfalls plunge into darkness.

## World layout (relationships)

Compose a coherent ecological sequence. Relative placement should feel
like this (adapt freely as long as the relationships hold):

1.  Snow mountains occupy the far / behind end of the island — the final
    alpine massif at the cold edge.
2.  Snowy conifer forest sits as elevated foothills in front of those
    mountains (between the peaks and the rest of the island).
3.  Highlands occupy an elevated plain to the side of the snow forest —
    between the mountain flank and the back side of the flowering grove —
    then slope gently down into that pink grove.
4.  Dense jungle is a large wet canopy region, with a backwater / swamp
    marsh on the jungle's far side (away from the main plains outlet).
5.  Flat grassland plateau is the open river plain that receives wet-
    corridor drainage and leads toward the coast.
6.  Flowering grove is a moist pink basin off the plains / below the
    highland slope — visually separate from green grassland.
7.  Desert is a vast arid basin (south / rain-shadow side) with its own
    sandstone desert mountains — never the volcano.
8.  Volcano is a separate tall cone on volcanic ground only (far from
    the desert's river path).
9.  Coastal ocean and beaches wrap much of the southern and western edge.

## Scale and density (qualitative)

-   Prefer a clearly legible island: biomes spaced so each reads as its
    own region from high orbit.
-   Avoid collapsing adjacent biomes — especially grassland vs flowering
    grove, desert vs volcano, snow forest vs alpine peaks.
-   Within each biome, flora and fauna should feel abundant for that
    climate (dense jungle canopy; cactus across desert flats; pines in
    the snow forest; sparse scrub on highlands).
-   Mountains and the volcano dominate the skyline; desert flats and the
    grassland plateau sit lower between them.

## Ecological reasoning

Layout and systems must follow ecological logic, not decoration:

-   Water stays in the wet corridor: mountain melt → through / past the
    snow-forest foothills and wet highlands → weave through jungle →
    flat grasslands → coastal delta / ocean.
-   Flowering grove is a moist offshoot below the highland slope / plains
    moisture — not a stop on the way into the desert.
-   Desert is arid: vast flat basin with sandstone desert mountains;
    cacti across the flats; only fading dry washes; no through-rivers
    into the volcano; no perennial river cutting the desert core.
-   Volcano is a separate tall cone with lava tributaries and lava pools
    on volcanic ground. Where water meets lava, rock quenches to
    obsidian.
-   Rain falls downward from moving cloud decks over wet biomes.
-   Snowfall comes from cloud decks over the snowy conifer forest.
-   Blizzard / white windstorm lives on the behind face of the snow
    mountains (the far alpine side), not as a front-slope decoration
    facing the forest alone.
-   Snowy trees carry snow on their canopies, not only on the ground.
-   Highlands are genuinely elevated relative to plains and grove, with
    a gentle downslope into the pink forest.

## Biomes

### 1. Snow Mountain Range (far / behind)

-   Tall alpine peaks — high relief, not gentle hills
-   Snow on summits and upper ridges; rock on lower slopes
-   Meltwater feeding the wet corridor
-   Active blizzard on the behind mountain face: fast whitish wind
    sheets (sandstorm motion, white instead of brown), spanning a wide
    strip of that rear alpine tape

### 2. Snowy Conifer Forest (foothills in front of the peaks)

-   Elevated shelf / foothill band in front of the snow mountains
-   Dense pines with snow on canopies as well as ground
-   Cloud deck directly above the forest that drops snowfall onto it
-   Distinct from both bare alpine rock and lowland plains

### 3. Temperate Highlands (elevated plain beside the snow forest)

-   Sit to the side of the snow forest, between mountain influence and
    the back of the flowering grove — an elevated open highland plain
-   Higher than grasslands and grove; rocky hills, scrub, hardy plants
-   Gentle slope down into the pink flowering grove
-   Occasional mist and light rain

### 4. Dense Jungle / Rainforest

-   Thick emerald canopy, layered undergrowth, densely packed trees
-   Rocky clearings, inland ponds, major waterfall
-   On the jungle's backside (away from the plains outlet): a backwater
    / swamp ecosystem — murky standing pools, mangroves or similar,
    low mist, stagnant channels (not a desert river)
-   Persistent jungle rain: rainfall shafts, wet canopy, rising mist
    after showers

### 5. Central Grasslands (flat river plateau)

-   Open flat green plain — clearly not the pink grove
-   Dense winding river network with many tributaries
-   Scattered woodland copses and yellow/white wildflowers
-   Meadow color green/olive, not pink

### 6. Flowering Grove

-   Moist basin receiving the highland downslope and/or plains moisture
-   Dense pink flowering canopy and pink-tinted meadow floor
-   Small streams; visually different from grassland at a glance

### 7. Desert

-   Mostly flat arid land
-   Distinct desert mountains / sandstone peaks on that flat floor —
    these are NOT the volcano
-   Dry washes that fade out; no perennial river through desert core
    or into the volcano
-   Cacti and life spread across the flats
-   Desert winds and sandstorm / dust storm

### 8. Volcanic Wasteland

-   Tall stratovolcano cone with glowing crater — not a flat puddle
-   Lava tributaries into lava pools on volcanic ground only
-   Black basalt, ash plumes, periodic eruptions
-   Water + lava contact becomes obsidian

## Coastal Ocean

Southern and western edges surrounded by turquoise coastal waters:

-   Shallow lagoons and deeper offshore water
-   Rocky shoreline, small islands and reefs
-   Multiple river mouths and a visible braided delta into the ocean
-   Freshwater mixing into saltwater at the mouths

## Beaches

Natural transition from grasslands and forests into beaches:

-   Bright sand, curved bays, warm-region palms where fitting
-   Rocky headlands, clear shallow water, coastal vegetation

## Rivers and Hydrology

A rich branching system that obeys ecological law:

-   Mountain melt and highland moisture feed headwaters.
-   Flow weaves the wet corridor through jungle into the flat grassland
    plateau, then widens into a coastal delta.
-   Grove receives a moist feeder from highland slope and/or plains —
    not a desert route.
-   Desert stays dry aside from fading washes; no river into the volcano.
-   Swamp holds stagnant backwater connected to the jungle wet side.
-   Show the water cycle: rain and melt feed rivers; heat drives
    evaporation mist; moisture returns as rain or snow.

## Climate, Clouds, Seasons, and Sun

-   Rain, snow, mist, sandstorm, ash, and cloud decks arrive in cyclic
    bursts — fade in, hold, fade out, quiet gap — staggered by biome.
-   Snowfall: cloud deck over the conifer foothill forest.
-   Blizzard: whitish high-altitude wind sheets on the behind alpine
    face of the snow mountains.
-   Desert: winds and sandstorm. Volcano: eruptions, ash, lava pools;
    water+lava → obsidian.
-   Reliable seasonal cycle (spring → summer → autumn → winter)
    modulating rain/snow intensity and light tint.
-   Visible square sun on a cyclic day pattern.

## Cliffs and Underside

-   Vertical rock walls around the perimeter
-   Tall stone foundation matching heightened elevations above
-   Numerous waterfalls; floating rock fragments beneath
-   Blue glowing mineral seams in places

## Color Palette

  Region       Colors
  ------------ -----------------------------
  Ocean        Turquoise, deep blue, cyan
  Beaches      White, cream, tan
  Jungle       Emerald, dark green, mist grey
  Swamp        Murky olive, dark water
  Plains       Green, olive
  Grove        Pink blossoms, soft meadow
  Highlands    Grey-green scrub
  Mountains    White summits, blue-grey rock
  Conifers     Dark pine, snow-capped canopy
  Desert       Gold, ochre, dust haze
  Volcano      Black, orange, crimson, ash
  Rivers       Cyan (murkier in swamp)
  Weather      Rain blue, snow white, sand tan, ash grey

## Lighting

-   Square sun drives cyclic daylight; seasonal tint modulates warmth
-   Local weather tinting (cooler in storms, ember glow near volcano)
-   Crisp terrain shadows when weather is clear
-   High visibility of the whole island from a comfortable orbit
-   Black void background with no stars or atmosphere dome

## Visual Composition

A Minecraft-style voxel floating continent: far snow mountains with a
behind-face blizzard; elevated snow-forest foothills under snowfall
clouds; highlands on an elevated plain sloping into a pink grove; a large
dense jungle with a backwater swamp on its far side; a flat grassland
river plateau; arid desert with its own sandstone mountains separated
from a tall erupting volcano; wet-corridor rivers to a coastal delta;
cyclic weather; square sun and seasons. The ocean borders the land before
plunging over cliff edges into the void.

Success is ecological clarity, vivid living systems, and a coherent
blocky voxel look — invent your own scale; make it as strong or stronger
as this description allows.
