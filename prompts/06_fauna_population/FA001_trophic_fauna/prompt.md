# Trophic Fauna Population

Populate a world with FAUNA spanning herbivores, omnivores, carnivores, an apex predator, pollinators, scavengers, and decomposers. Each animal must live only in biomes that support its kind, and its diet must be complete for its trophic role: herbivores eat real plants, carnivores have real prey, nothing preys on itself. Include the flora needed to feed the herbivores.

## Output format

Output MUST be a single JSON object conforming to the WorldBench `World` schema (see benchmark/schemas/world_schema_v1.json). It contains the 12 sections: metadata, layout, terrain, water, biomes, flora, fauna, interactions, weather, seasons, natural_events, simulation. Every entity needs a stable snake_case `id`; relationships are id references. This is a purely NATURAL world: no humans, civilization, cities, roads, buildings, politics, or economy. Emit ONLY the JSON — no prose, no code fences.

## What this task evaluates

This task stresses fauna — animals in habitats that support them, with complete, valid diets for their trophic roles. The generated world is validated
deterministically and scored out of 100; see `scoring.yaml` for how this
category re-weights the metrics.
