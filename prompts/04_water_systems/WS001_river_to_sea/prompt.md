# River-to-Sea Hydrology

Generate a world with a complete WATER system. Mountain meltwater and springs must feed rivers; rivers must flow strictly downhill, merge, widen, and terminate — reaching a lake, the sea, or spilling off the world's edge. No river may flow uphill or dangle with nowhere to go. Include still bodies (lakes, an oasis) and make the whole network hydrologically sound.

## Output format

Output MUST be a single JSON object conforming to the WorldBench `World` schema (see benchmark/schemas/world_schema_v1.json). It contains the 12 sections: metadata, layout, terrain, water, biomes, flora, fauna, interactions, weather, seasons, natural_events, simulation. Every entity needs a stable snake_case `id`; relationships are id references. This is a purely NATURAL world: no humans, civilization, cities, roads, buildings, politics, or economy. Emit ONLY the JSON — no prose, no code fences.

## What this task evaluates

This task stresses hydrology — a connected flow network where every flowing body runs downhill and terminates properly. The generated world is validated
deterministically and scored out of 100; see `scoring.yaml` for how this
category re-weights the metrics.
