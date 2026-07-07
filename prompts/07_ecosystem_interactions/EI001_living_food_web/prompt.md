# Living Food Web

Generate a world with a rich ECOSYSTEM of INTERACTIONS: predation and herbivory forming an acyclic food web with producers at the base and an apex predator at the top, plus pollination, seed dispersal, seasonal migration, symbiosis, nesting, and decomposition. The trophic graph must contain no impossible cycles (nothing ends up eating its own predator).

## Output format

Output MUST be a single JSON object conforming to the WorldBench `World` schema (see benchmark/schemas/world_schema_v1.json). It contains the 12 sections: metadata, layout, terrain, water, biomes, flora, fauna, interactions, weather, seasons, natural_events, simulation. Every entity needs a stable snake_case `id`; relationships are id references. This is a purely NATURAL world: no humans, civilization, cities, roads, buildings, politics, or economy. Emit ONLY the JSON — no prose, no code fences.

## What this task evaluates

This task stresses the ecological web — a rich, varied, acyclic set of interactions binding species together. The generated world is validated
deterministically and scored out of 100; see `scoring.yaml` for how this
category re-weights the metrics.
