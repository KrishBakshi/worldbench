# Strictly Natural World

Generate a natural world that is STRICTLY free of humans and civilization. There must be no people, villages, cities, roads, bridges, buildings, farms, harbors, politics, or economy anywhere — not in names, not in descriptions, not in tags. Every feature must be a product of nature alone: stone, water, weather, and life. Make it vivid using only natural language.

## Output format

Output MUST be a single JSON object conforming to the WorldBench `World` schema (see benchmark/schemas/world_schema_v1.json). It contains the 12 sections: metadata, layout, terrain, water, biomes, flora, fauna, interactions, weather, seasons, natural_events, simulation. Every entity needs a stable snake_case `id`; relationships are id references. This is a purely NATURAL world: no humans, civilization, cities, roads, buildings, politics, or economy. Emit ONLY the JSON — no prose, no code fences.

## What this task evaluates

This task stresses scope discipline — a compelling world containing zero civilization or anthropogenic content. The generated world is validated
deterministically and scored out of 100; see `scoring.yaml` for how this
category re-weights the metrics.
