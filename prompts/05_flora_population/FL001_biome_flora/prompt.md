# Biome-Appropriate Flora

Populate a world with FLORA. Every plant species must be placed only in biomes that can support it: cacti and succulents in deserts, canopy trees and ferns in forests, reeds in wetlands, kelp and coral in the sea. Give each species a pollination mode; insect- and bird-pollinated plants should have matching pollinators elsewhere in the world.

## Output format

Output MUST be a single JSON object conforming to the WorldBench `World` schema (see benchmark/schemas/world_schema_v1.json). It contains the 12 sections: metadata, layout, terrain, water, biomes, flora, fauna, interactions, weather, seasons, natural_events, simulation. Every entity needs a stable snake_case `id`; relationships are id references. This is a purely NATURAL world: no humans, civilization, cities, roads, buildings, politics, or economy. Emit ONLY the JSON — no prose, no code fences.

## What this task evaluates

This task stresses flora placement — every plant species must be able to grow in each biome it is assigned to. The generated world is validated
deterministically and scored out of 100; see `scoring.yaml` for how this
category re-weights the metrics.
