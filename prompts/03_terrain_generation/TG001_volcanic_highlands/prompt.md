# Volcanic Highlands Terrain

Generate a world with dramatic TERRAIN: snow-capped mountain ranges, high plateaus, eroded mesas, coastal cliffs, and at least one ACTIVE volcano. Elevations must be internally coherent — every feature's peak sits above its base, ranges connect, and a sparse elevation field agrees with the landforms. Fill out the rest of the world so it lives and breathes.

## Output format

Output MUST be a single JSON object conforming to the WorldBench `World` schema (see benchmark/schemas/world_schema_v1.json). It contains the 12 sections: metadata, layout, terrain, water, biomes, flora, fauna, interactions, weather, seasons, natural_events, simulation. Every entity needs a stable snake_case `id`; relationships are id references. This is a purely NATURAL world: no humans, civilization, cities, roads, buildings, politics, or economy. Emit ONLY the JSON — no prose, no code fences.

## What this task evaluates

This task stresses terrain — coherent elevations (peaks above bases), connected landforms, and a genuine active volcano. The generated world is validated
deterministically and scored out of 100; see `scoring.yaml` for how this
category re-weights the metrics.
