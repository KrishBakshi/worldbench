# WorldBench Knowledge Base

A rule-based ecological ontology. Each YAML file describes one **concept** (a
terrain type, water type, or biome type) and the relationships it participates
in. The loader (`graph.py`) assembles every file into a single directed
`networkx` graph that validators and metrics query to check ecological realism
without hand-coding rules in Python.

## File format

```yaml
concept: forest            # unique concept key
kind: biome                # one of: terrain | water | biome | climate
aliases: [temperate_forest, rainforest]   # schema enum values mapping to this concept

supports:                  # entities/categories this concept can sustain
  flora: [tree, shrub, fern, moss, flower, vine]
  fauna: [mammal, bird, insect, amphibian, reptile]
  features: [river_source, shade]

requires:                  # conditions this concept needs to exist
  moisture: [moderate, humid, saturated]
  temperature: [cold, temperate, warm]

adjacent_to: [grassland, wetland, alpine]   # concepts that plausibly border it
flows_to: [lake, ocean, wetland]            # (water concepts) valid downstream targets
incompatible_with: [desert]                 # concepts that should not directly border it
```

Only the keys relevant to a concept need to be present. The loader is tolerant
of missing keys.

## Relationship semantics

| relation           | meaning                                                        |
|--------------------|----------------------------------------------------------------|
| `supports.flora`   | flora categories that can grow in this concept                 |
| `supports.fauna`   | fauna categories that can live in this concept                 |
| `supports.features`| natural features the concept can host (e.g. `river_source`)    |
| `requires`         | climate constraints (moisture / temperature bands)             |
| `adjacent_to`      | concepts that may plausibly share a border                     |
| `flows_to`         | valid downstream water concepts (water only)                   |
| `incompatible_with`| concepts that should *not* be directly adjacent                |

Validators treat violations of `supports`/`requires` as **errors** and
violations of `adjacent_to`/`incompatible_with` as **warnings**, since natural
transitions are sometimes abrupt.
