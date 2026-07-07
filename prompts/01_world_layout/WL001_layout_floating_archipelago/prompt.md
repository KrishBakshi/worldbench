# Floating World Layout

Design the LAYOUT of a floating natural world suspended in a void. Establish the world topology (a floating landmass), its bounds, sea level, and a set of named regions that tile the world from the high interior to the coastal edge. Region adjacency must be symmetric and spatially plausible. Then populate the remaining sections so the world is complete and alive.

## Output format

Output MUST be a single JSON object conforming to the WorldBench `World` schema (see benchmark/schemas/world_schema_v1.json). It contains the 12 sections: metadata, layout, terrain, water, biomes, flora, fauna, interactions, weather, seasons, natural_events, simulation. Every entity needs a stable snake_case `id`; relationships are id references. This is a purely NATURAL world: no humans, civilization, cities, roads, buildings, politics, or economy. Emit ONLY the JSON — no prose, no code fences.

## What this task evaluates

This task stresses the global layout — a coherent floating landmass partitioned into named, correctly-adjacent regions. The generated world is validated
deterministically and scored out of 100; see `scoring.yaml` for how this
category re-weights the metrics.
