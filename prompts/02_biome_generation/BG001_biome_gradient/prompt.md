# Biome Climate Gradient

Generate a world whose BIOMES form a coherent climatic gradient, from cold alpine interiors through temperate forest and grassland to hot desert and volcanic zones, ending at coastal beaches and shallows. Each biome must declare a temperature band and moisture level consistent with what that biome type can actually support. Neighboring biomes must transition plausibly.

## Output format

Output MUST be a single JSON object conforming to the WorldBench `World` schema (see benchmark/schemas/world_schema_v1.json). It contains the 12 sections: metadata, layout, terrain, water, biomes, flora, fauna, interactions, weather, seasons, natural_events, simulation. Every entity needs a stable snake_case `id`; relationships are id references. This is a purely NATURAL world: no humans, civilization, cities, roads, buildings, politics, or economy. Emit ONLY the JSON — no prose, no code fences.

## What this task evaluates

This task stresses biome placement — each biome's temperature and moisture must satisfy its ecological requirements. The generated world is validated
deterministically and scored out of 100; see `scoring.yaml` for how this
category re-weights the metrics.
