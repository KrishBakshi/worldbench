# Extreme Biodiversity Stress Test

Stress-test WORLD SCALE. Generate a maximally biodiverse world: many biomes, a dense roster of flora and fauna across every trophic level, and a large web of ecological interactions — while keeping EVERYTHING coherent. Every species must still belong where it lives, every river must still reach the sea, and the food web must remain acyclic. Breadth must not break consistency.

## Output format

Output MUST be a single JSON object conforming to the WorldBench `World` schema (see benchmark/schemas/world_schema_v1.json). It contains the 12 sections: metadata, layout, terrain, water, biomes, flora, fauna, interactions, weather, seasons, natural_events, simulation. Every entity needs a stable snake_case `id`; relationships are id references. This is a purely NATURAL world: no humans, civilization, cities, roads, buildings, politics, or economy. Emit ONLY the JSON — no prose, no code fences.

## What this task evaluates

This task stresses scale under coherence — a large, dense, biodiverse world that remains fully valid and internally consistent. The generated world is validated
deterministically and scored out of 100; see `scoring.yaml` for how this
category re-weights the metrics.
