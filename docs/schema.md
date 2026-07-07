# WorldBench Schema Reference

The schema is defined by Pydantic v2 models in `benchmark/models/` and exported
to `benchmark/schemas/world_schema_v1.json`. Current schema version: **1.0.0**
(`benchmark.models.SCHEMA_VERSION`).

## Conventions

- **Every entity has a stable `id`** — a lowercase snake_case string, 2–64
  characters, starting with a letter (regex `^[a-z][a-z0-9_]{1,63}$`). Ids must
  be unique within the world.
- **Relationships are id references, not nesting.** A river's `flows_to` is the
  id of another water body; a biome's `adjacent_to` is a list of biome ids. This
  turns the world into a graph (`build_world_graph`).
- **Coordinates are abstract world units** on a bounded plane defined by
  `layout.bounds`. Elevation is a signed float; `0.0` is nominal sea level (or
  the base of a floating landmass).
- **Models forbid unknown fields.** Extra keys cause a structural validation
  error, so malformed model output fails loudly.
- **Local vs. cross-section validation.** The models enforce only local
  invariants (shapes, ranges, per-entity rules such as "a volcano must declare
  volcanic activity"). Cross-section checks (do referenced ids exist? does water
  flow downhill globally?) live in the validators.

## The `World` object

```jsonc
{
  "metadata":       { ... },   // identity & provenance
  "layout":         { ... },   // topology, bounds, regions
  "terrain":        { ... },   // landforms + elevation samples
  "water":          { ... },   // water bodies + flow graph
  "biomes":         { ... },   // ecological zones
  "flora":          { ... },   // plant species
  "fauna":          { ... },   // animal species
  "interactions":   { ... },   // ecological web (optional, defaults empty)
  "weather":        { ... },   // winds + per-biome climate
  "seasons":        { ... },   // annual cycle
  "natural_events": { ... },   // disturbances (optional, defaults empty)
  "simulation":     { ... }    // long-term dynamics (optional, defaults empty)
}
```

`interactions`, `natural_events`, and `simulation` default to empty containers,
but leaving them empty costs completeness, interaction-richness, and creativity
points.

---

## 1. `metadata`

| Field            | Type        | Notes                                             |
|------------------|-------------|---------------------------------------------------|
| `id`             | id          | Unique id for the world                           |
| `name`           | string      | Human-readable name                               |
| `description`    | string      | Prose summary of the world                        |
| `schema_version` | string      | Defaults to the current schema version            |
| `seed`           | int \| null | Optional deterministic seed the generator claims  |
| `tags`           | string[]    | Freeform tags (e.g. `floating`, `volcanic`)       |

## 2. `layout`

| Field       | Type                | Notes                                                        |
|-------------|---------------------|--------------------------------------------------------------|
| `topology`  | enum `WorldTopology`| `continent`, `island`, `archipelago`, `floating_island`, `floating_archipelago`, `ring`, `cavern` |
| `edge_type` | enum `EdgeType`     | `ocean`, `void`, `ice_wall`, `wrapping`, `cliff`. Floating topologies must use `void`/`cliff` |
| `bounds`    | BoundingRegion      | World extent; all coordinates must fall inside               |
| `sea_level` | float               | Nominal sea-level elevation (default `0.0`)                  |
| `regions`   | Region[]            | ≥1 named coarse areas partitioning the world                 |

**Region**: `id`, `name`, `description`, `footprint` (BoundingRegion),
`direction` (cardinal), `adjacent_to` (region ids — adjacency must be
**symmetric**).

**BoundingRegion**: `min_x`, `min_y`, `max_x`, `max_y`, and optional `vertices`
(a polygon ring of `Coordinate2D`, ≥3 points) for irregular footprints.

## 3. `terrain`

`features` (≥1 `TerrainFeature`) plus optional `elevation_samples` (sparse
height-field points for coherence checking).

**TerrainFeature**: `id`, `name`, `type` (enum `TerrainType`: mountain,
mountain_range, hill, plateau, plain, valley, canyon, cliff, dune_field, mesa,
volcano, crater, glacier, cave_system, basin, floating_fragment), `region_id`,
`footprint`, `base_elevation`, `peak_elevation` (≥ base), `slope` (0–1),
`volcanic_activity` (required on volcanoes, forbidden elsewhere), `connected_to`
(ids of contiguous features).

## 4. `water`

`bodies` (≥1 `WaterBody`). Hydrology is a directed flow graph.

**WaterBody**: `id`, `name`, `type` (enum `WaterBodyType`: ocean, sea, lake,
pond, river, stream, waterfall, spring, hot_spring, glacier_melt, lagoon,
wetland, oasis), `quality`, `region_ids` (≥1), `footprint` **or** `path`
(ordered `Coordinate2D` course for linear bodies), `surface_elevation`,
`mouth_elevation` (≤ surface — water flows downhill), `source_ids` (feeding
terrain/water), `flows_to` (downstream body id) **or** `exits_world` (true when
the body pours off a floating edge; mutually exclusive with `flows_to`).

Flowing types (`river`, `stream`, `waterfall`, `glacier_melt`) must reach a
terminal type (`ocean`, `sea`, `lake`, `lagoon`, `wetland`, `pond`, `oasis`) or
set `exits_world`.

## 5. `biomes`

`zones` (≥1 `Biome`).

**Biome**: `id`, `name`, `type` (enum `BiomeType`: alpine, tundra, snow_forest,
temperate_forest, rainforest, grassland, savanna, shrubland, desert, volcanic,
wetland, beach, coastal_ocean, deep_ocean, coral_reef, flowering_grove,
highland, cave), `region_ids` (≥1), `temperature` (polar…hot), `moisture`
(arid…saturated), `elevation_range` (`[min, max]`), `adjacent_to` (biome ids,
symmetric), `terrain_feature_ids`, `water_body_ids`.

## 6. `flora`

`species` (≥1 `FloraSpecies`).

**FloraSpecies**: `id`, `name`, `category` (tree, conifer, shrub, grass, flower,
cactus, succulent, fern, moss, lichen, fungus, vine, reed, algae, seagrass,
coral), `biome_ids` (≥1 — each must ecologically support the category),
`rarity`, `pollination` (wind, insect, bird, bat, water, self, spore, none),
`water_requirement` (0–1), `provides_food`, `provides_shelter`, `max_height`.

## 7. `fauna`

`species` (≥1 `FaunaSpecies`).

**FaunaSpecies**: `id`, `name`, `category` (mammal, bird, reptile, amphibian,
fish, insect, arachnid, crustacean, mollusk, cephalopod), `trophic_role`
(producer_consumer, herbivore, omnivore, carnivore, apex_predator, scavenger,
decomposer, pollinator, filter_feeder), `locomotion` (≥1 of walking, climbing,
flying, swimming, burrowing, gliding, amphibious), `biome_ids` (≥1),
`population_trend`, `diet_flora_ids` (required non-empty for herbivores/
omnivores), `diet_fauna_ids` (required for carnivores/omnivores/apex; no
self-predation).

## 8. `interactions`

`edges` (list of `EcologicalInteraction`, may be empty).

**EcologicalInteraction**: `id`, `type` (predation, herbivory, pollination,
seed_dispersal, migration, symbiosis, parasitism, competition, decomposition,
nesting, camouflage_host), `source_id` (the actor), `target_id` (the recipient;
must differ from source), `strength` (0–1), `seasonal`.

## 9. `weather`

`prevailing_winds` (WindPattern: `id`, `name`, `direction`, `strength`) and
`biome_weather` (≥1 `BiomeWeather`).

**BiomeWeather**: `biome_id`, `avg_temperature`, `precipitation` (none, rain,
snow, sleet, hail, mist, ash), `annual_precipitation` (0 iff precipitation is
`none`), `storm_frequency` (0–1).

## 10. `seasons`

`cycle` (≥1 `Season`).

**Season**: `id`, `name`, `order` (contiguous from 0), `length_fraction`
(fractions across the cycle sum to ~1.0), `temperature_modifier`,
`precipitation_modifier`, `triggers_event_ids`.

## 11. `natural_events`

`events` (list of `NaturalEvent`, may be empty).

**NaturalEvent**: `id`, `name`, `type` (flood, drought, wildfire,
volcanic_eruption, storm, blizzard, landslide, earthquake, algal_bloom,
migration, pollination_bloom), `severity`, `recurrence_years`,
`affected_region_ids`, `affected_biome_ids` (must affect at least one),
`triggers` (terrain/water ids that cause it).

## 12. `simulation`

`stability_index` (0–1) and `dynamics` (list of `LongTermDynamic`).

**LongTermDynamic**: `id`, `name`, `type` (predator_prey_cycle,
ecological_succession, migration_cycle, nutrient_cycle, population_boom_bust,
climate_drift, glacial_cycle, wildfire_regeneration), `period_years`,
`involves_ids` (≥1 species/biome/interaction/event ids the dynamic operates on).

---

## Annotated example (fragment)

```jsonc
{
  "metadata": { "id": "world_aetheris", "name": "Aetheris", "description": "…", "tags": ["floating"] },
  "layout": {
    "topology": "floating_island",
    "edge_type": "void",                    // floating → void/cliff required
    "bounds": { "min_x": 0, "min_y": 0, "max_x": 1000, "max_y": 800 },
    "sea_level": 0.0,
    "regions": [
      { "id": "reg_north", "name": "Northern Range", "direction": "north",
        "footprint": { "min_x": 0, "min_y": 500, "max_x": 1000, "max_y": 800 },
        "adjacent_to": ["reg_central"] }    // symmetric with reg_central
    ]
  },
  "water": {
    "bodies": [
      { "id": "riv_glass", "name": "Glass Creek", "type": "river",
        "region_ids": ["reg_north"], "surface_elevation": 900,
        "mouth_elevation": 40, "source_ids": ["mtn_frost"],
        "flows_to": "lake_mirror" }         // flowing body must terminate somewhere
    ]
  }
}
```

Regenerate the canonical schema any time the models change:

```bash
python -m benchmark.schemas.export_schema
```
