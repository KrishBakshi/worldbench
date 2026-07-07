# Complete Floating World

Generate a COMPLETE floating-island world, self-contained in an infinite void. A rectangular landmass grades from northwest snow mountains through temperate highlands, dense forest, central grasslands, a flowering grove, desert, and volcanic wasteland, ringed by coastal ocean and beaches. Mountain meltwater feeds rivers that cross the biomes and pour off the cliff edges as waterfalls. Populate every section — terrain, water, biomes, flora, fauna, interactions, weather, seasons, natural events, and long-term dynamics — into one coherent, living world.

## Output format

Output MUST be a single JSON object conforming to the WorldBench `World` schema (see benchmark/schemas/world_schema_v1.json). It contains the 12 sections: metadata, layout, terrain, water, biomes, flora, fauna, interactions, weather, seasons, natural_events, simulation. Every entity needs a stable snake_case `id`; relationships are id references. This is a purely NATURAL world: no humans, civilization, cities, roads, buildings, politics, or economy. Emit ONLY the JSON — no prose, no code fences.

## What this task evaluates

This task stresses whole-world composition — every section populated and mutually consistent into one living island. The generated world is validated
deterministically and scored out of 100; see `scoring.yaml` for how this
category re-weights the metrics.
