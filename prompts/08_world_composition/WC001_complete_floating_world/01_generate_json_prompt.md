# Stage 1 — Generate the world.json

This is the **first stage** of the two-artifact WorldBench task
`WC001_complete_floating_world`. Paste everything in the fenced block below
into any LLM chat website, exactly as-is.

---

```text
SYSTEM PROMPT (send as the system message, or paste first if the chat has no separate system-message field):
"""
You are a world-generation engine for WorldBench. You produce structured, ecologically coherent NATURAL worlds as a single JSON object matching the WorldBench World schema. You never include humans, civilization, or artificial structures. You output only valid JSON.
"""

USER PROMPT:
"""
# Complete Floating World

Generate a COMPLETE floating-island world, self-contained in an infinite void. A rectangular landmass grades from northwest snow mountains through temperate highlands, dense forest, central grasslands, a flowering grove, desert, and volcanic wasteland, ringed by coastal ocean and beaches. Mountain meltwater feeds rivers that cross the biomes and pour off the cliff edges as waterfalls. Populate every section — terrain, water, biomes, flora, fauna, interactions, weather, seasons, natural events, and long-term dynamics — into one coherent, living world.

## Output format

Output MUST be a single JSON object conforming to the WorldBench `World` schema (see benchmark/schemas/world_schema_v1.json). It contains the 12 sections: metadata, layout, terrain, water, biomes, flora, fauna, interactions, weather, seasons, natural_events, simulation. Every entity needs a stable snake_case `id`; relationships are id references. This is a purely NATURAL world: no humans, civilization, cities, roads, buildings, politics, or economy. Emit ONLY the JSON — no prose, no code fences.

## What this task evaluates

This task stresses whole-world composition — every section populated and mutually consistent into one living island. The generated world is validated
deterministically and scored out of 100; see `scoring.yaml` for how this
category re-weights the metrics.
"""

TASK CONSTRAINTS (the world must also satisfy these minimums):
"""
required_topology: floating_island
min_biomes: 7
min_flora: 12
min_fauna: 12
min_interactions: 8
min_water_bodies: 6
"""

JSON SCHEMA the output must conform to (world_schema_v1.json):
"""
{
  "$defs": {
    "Biome": {
      "additionalProperties": false,
      "description": "A climatic and ecological zone of the world.",
      "properties": {
        "id": {
          "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
          "maxLength": 64,
          "minLength": 2,
          "title": "Id",
          "type": "string"
        },
        "name": {
          "maxLength": 120,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "type": {
          "$ref": "#/$defs/BiomeType"
        },
        "region_ids": {
          "description": "Layout regions this biome covers (fully or partially).",
          "items": {
            "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
            "maxLength": 64,
            "minLength": 2,
            "type": "string"
          },
          "minItems": 1,
          "title": "Region Ids",
          "type": "array"
        },
        "temperature": {
          "$ref": "#/$defs/TemperatureBand"
        },
        "moisture": {
          "$ref": "#/$defs/MoistureLevel"
        },
        "elevation_range": {
          "description": "(min, max) elevation band the biome occupies, in world units.",
          "maxItems": 2,
          "minItems": 2,
          "prefixItems": [
            {
              "type": "number"
            },
            {
              "type": "number"
            }
          ],
          "title": "Elevation Range",
          "type": "array"
        },
        "adjacent_to": {
          "description": "Ids of biomes sharing a border. Must be symmetric.",
          "items": {
            "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
            "maxLength": 64,
            "minLength": 2,
            "type": "string"
          },
          "title": "Adjacent To",
          "type": "array"
        },
        "terrain_feature_ids": {
          "description": "Terrain features lying within this biome.",
          "items": {
            "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
            "maxLength": 64,
            "minLength": 2,
            "type": "string"
          },
          "title": "Terrain Feature Ids",
          "type": "array"
        },
        "water_body_ids": {
          "description": "Water bodies within or bordering this biome.",
          "items": {
            "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
            "maxLength": 64,
            "minLength": 2,
            "type": "string"
          },
          "title": "Water Body Ids",
          "type": "array"
        },
        "description": {
          "default": "",
          "maxLength": 2000,
          "title": "Description",
          "type": "string"
        }
      },
      "required": [
        "id",
        "name",
        "type",
        "region_ids",
        "temperature",
        "moisture",
        "elevation_range"
      ],
      "title": "Biome",
      "type": "object"
    },
    "BiomeType": {
      "enum": [
        "alpine",
        "tundra",
        "snow_forest",
        "temperate_forest",
        "rainforest",
        "grassland",
        "savanna",
        "shrubland",
        "desert",
        "volcanic",
        "wetland",
        "beach",
        "coastal_ocean",
        "deep_ocean",
        "coral_reef",
        "flowering_grove",
        "highland",
        "cave"
      ],
      "title": "BiomeType",
      "type": "string"
    },
    "BiomeWeather": {
      "additionalProperties": false,
      "description": "Prevailing weather behavior for a specific biome.",
      "properties": {
        "biome_id": {
          "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
          "maxLength": 64,
          "minLength": 2,
          "title": "Biome Id",
          "type": "string"
        },
        "avg_temperature": {
          "description": "Average temperature in arbitrary but consistent units.",
          "title": "Avg Temperature",
          "type": "number"
        },
        "precipitation": {
          "$ref": "#/$defs/PrecipitationType"
        },
        "annual_precipitation": {
          "description": "Relative annual precipitation (0 for none). Must be 0 for 'none' precipitation and > 0 otherwise.",
          "minimum": 0.0,
          "title": "Annual Precipitation",
          "type": "number"
        },
        "storm_frequency": {
          "default": 0.0,
          "description": "Normalized likelihood of storms.",
          "maximum": 1.0,
          "minimum": 0.0,
          "title": "Storm Frequency",
          "type": "number"
        }
      },
      "required": [
        "biome_id",
        "avg_temperature",
        "precipitation",
        "annual_precipitation"
      ],
      "title": "BiomeWeather",
      "type": "object"
    },
    "Biomes": {
      "additionalProperties": false,
      "description": "All biomes in the world.",
      "properties": {
        "zones": {
          "items": {
            "$ref": "#/$defs/Biome"
          },
          "minItems": 1,
          "title": "Zones",
          "type": "array"
        }
      },
      "required": [
        "zones"
      ],
      "title": "Biomes",
      "type": "object"
    },
    "BoundingRegion": {
      "additionalProperties": false,
      "description": "An axis-aligned or polygonal footprint on the world plane.

A polygon (``vertices`` with 3+ points) is preferred for irregular natural
shapes; a simple axis-aligned box may be used for coarse regions.",
      "properties": {
        "min_x": {
          "title": "Min X",
          "type": "number"
        },
        "min_y": {
          "title": "Min Y",
          "type": "number"
        },
        "max_x": {
          "title": "Max X",
          "type": "number"
        },
        "max_y": {
          "title": "Max Y",
          "type": "number"
        },
        "vertices": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/Coordinate2D"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Ordered polygon vertices (closed ring implied) for an irregular footprint. When omitted, the bounding box above is used.",
          "title": "Vertices"
        }
      },
      "required": [
        "min_x",
        "min_y",
        "max_x",
        "max_y"
      ],
      "title": "BoundingRegion",
      "type": "object"
    },
    "CardinalDirection": {
      "enum": [
        "north",
        "northeast",
        "east",
        "southeast",
        "south",
        "southwest",
        "west",
        "center"
      ],
      "title": "CardinalDirection",
      "type": "string"
    },
    "ConservationTrend": {
      "enum": [
        "growing",
        "stable",
        "declining",
        "critical"
      ],
      "title": "ConservationTrend",
      "type": "string"
    },
    "Coordinate2D": {
      "additionalProperties": false,
      "description": "A location on the world's horizontal plane, in world units.",
      "properties": {
        "x": {
          "description": "Position along the west-to-east axis.",
          "title": "X",
          "type": "number"
        },
        "y": {
          "description": "Position along the south-to-north axis.",
          "title": "Y",
          "type": "number"
        }
      },
      "required": [
        "x",
        "y"
      ],
      "title": "Coordinate2D",
      "type": "object"
    },
    "DynamicType": {
      "enum": [
        "predator_prey_cycle",
        "ecological_succession",
        "migration_cycle",
        "nutrient_cycle",
        "population_boom_bust",
        "climate_drift",
        "glacial_cycle",
        "wildfire_regeneration"
      ],
      "title": "DynamicType",
      "type": "string"
    },
    "EcologicalInteraction": {
      "additionalProperties": false,
      "description": "A directed ecological relationship between two entities.

``source_id`` is the actor (predator, pollinator, migrant) and
``target_id`` the recipient (prey, flower, destination biome). Both must
reference existing flora, fauna, or biome ids as appropriate to the type.",
      "properties": {
        "id": {
          "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
          "maxLength": 64,
          "minLength": 2,
          "title": "Id",
          "type": "string"
        },
        "type": {
          "$ref": "#/$defs/InteractionType"
        },
        "source_id": {
          "description": "The acting entity id.",
          "maxLength": 64,
          "minLength": 2,
          "title": "Source Id",
          "type": "string"
        },
        "target_id": {
          "description": "The receiving entity id.",
          "maxLength": 64,
          "minLength": 2,
          "title": "Target Id",
          "type": "string"
        },
        "strength": {
          "default": 0.5,
          "description": "Relative importance of this interaction to the ecosystem.",
          "maximum": 1.0,
          "minimum": 0.0,
          "title": "Strength",
          "type": "number"
        },
        "seasonal": {
          "default": false,
          "description": "Whether the interaction only occurs in certain seasons (e.g. migration, seasonal pollination).",
          "title": "Seasonal",
          "type": "boolean"
        },
        "description": {
          "default": "",
          "maxLength": 2000,
          "title": "Description",
          "type": "string"
        }
      },
      "required": [
        "id",
        "type",
        "source_id",
        "target_id"
      ],
      "title": "EcologicalInteraction",
      "type": "object"
    },
    "EdgeType": {
      "description": "What happens at the boundary of the world.",
      "enum": [
        "ocean",
        "void",
        "ice_wall",
        "wrapping",
        "cliff"
      ],
      "title": "EdgeType",
      "type": "string"
    },
    "ElevationSample": {
      "additionalProperties": false,
      "description": "A sparse sample of the world's height field for coherence checking.",
      "properties": {
        "position": {
          "$ref": "#/$defs/Coordinate2D"
        },
        "elevation": {
          "title": "Elevation",
          "type": "number"
        }
      },
      "required": [
        "position",
        "elevation"
      ],
      "title": "ElevationSample",
      "type": "object"
    },
    "EventType": {
      "enum": [
        "flood",
        "drought",
        "wildfire",
        "volcanic_eruption",
        "storm",
        "blizzard",
        "landslide",
        "earthquake",
        "algal_bloom",
        "migration",
        "pollination_bloom"
      ],
      "title": "EventType",
      "type": "string"
    },
    "Fauna": {
      "additionalProperties": false,
      "description": "All animal species in the world.",
      "properties": {
        "species": {
          "items": {
            "$ref": "#/$defs/FaunaSpecies"
          },
          "minItems": 1,
          "title": "Species",
          "type": "array"
        }
      },
      "required": [
        "species"
      ],
      "title": "Fauna",
      "type": "object"
    },
    "FaunaCategory": {
      "enum": [
        "mammal",
        "bird",
        "reptile",
        "amphibian",
        "fish",
        "insect",
        "arachnid",
        "crustacean",
        "mollusk",
        "cephalopod"
      ],
      "title": "FaunaCategory",
      "type": "string"
    },
    "FaunaSpecies": {
      "additionalProperties": false,
      "description": "An animal species and its ecological role.",
      "properties": {
        "id": {
          "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
          "maxLength": 64,
          "minLength": 2,
          "title": "Id",
          "type": "string"
        },
        "name": {
          "maxLength": 120,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "category": {
          "$ref": "#/$defs/FaunaCategory"
        },
        "trophic_role": {
          "$ref": "#/$defs/TrophicRole"
        },
        "locomotion": {
          "description": "How the animal moves. Determines which biomes/terrain it can occupy (e.g. only 'swimming' fauna in deep ocean).",
          "items": {
            "$ref": "#/$defs/Locomotion"
          },
          "minItems": 1,
          "title": "Locomotion",
          "type": "array"
        },
        "biome_ids": {
          "description": "Biomes the species inhabits. Each must ecologically support this fauna category (checked against the knowledge base).",
          "items": {
            "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
            "maxLength": 64,
            "minLength": 2,
            "type": "string"
          },
          "minItems": 1,
          "title": "Biome Ids",
          "type": "array"
        },
        "rarity": {
          "$ref": "#/$defs/Rarity",
          "default": "common"
        },
        "population_trend": {
          "$ref": "#/$defs/ConservationTrend",
          "default": "stable"
        },
        "diet_flora_ids": {
          "description": "Flora species this animal eats. Required (non-empty) for herbivores and omnivores.",
          "items": {
            "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
            "maxLength": 64,
            "minLength": 2,
            "type": "string"
          },
          "title": "Diet Flora Ids",
          "type": "array"
        },
        "diet_fauna_ids": {
          "description": "Fauna species this animal preys on. Required for carnivores, omnivores, and apex predators. No species may appear in its own diet.",
          "items": {
            "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
            "maxLength": 64,
            "minLength": 2,
            "type": "string"
          },
          "title": "Diet Fauna Ids",
          "type": "array"
        },
        "description": {
          "default": "",
          "maxLength": 2000,
          "title": "Description",
          "type": "string"
        }
      },
      "required": [
        "id",
        "name",
        "category",
        "trophic_role",
        "locomotion",
        "biome_ids"
      ],
      "title": "FaunaSpecies",
      "type": "object"
    },
    "Flora": {
      "additionalProperties": false,
      "description": "All plant species in the world.",
      "properties": {
        "species": {
          "items": {
            "$ref": "#/$defs/FloraSpecies"
          },
          "minItems": 1,
          "title": "Species",
          "type": "array"
        }
      },
      "required": [
        "species"
      ],
      "title": "Flora",
      "type": "object"
    },
    "FloraCategory": {
      "enum": [
        "tree",
        "conifer",
        "shrub",
        "grass",
        "flower",
        "cactus",
        "succulent",
        "fern",
        "moss",
        "lichen",
        "fungus",
        "vine",
        "reed",
        "algae",
        "seagrass",
        "coral"
      ],
      "title": "FloraCategory",
      "type": "string"
    },
    "FloraSpecies": {
      "additionalProperties": false,
      "description": "A plant species and where it grows.",
      "properties": {
        "id": {
          "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
          "maxLength": 64,
          "minLength": 2,
          "title": "Id",
          "type": "string"
        },
        "name": {
          "maxLength": 120,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "category": {
          "$ref": "#/$defs/FloraCategory"
        },
        "biome_ids": {
          "description": "Biomes where the species grows. Each must ecologically support this flora category (checked against the knowledge base).",
          "items": {
            "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
            "maxLength": 64,
            "minLength": 2,
            "type": "string"
          },
          "minItems": 1,
          "title": "Biome Ids",
          "type": "array"
        },
        "rarity": {
          "$ref": "#/$defs/Rarity",
          "default": "common"
        },
        "pollination": {
          "$ref": "#/$defs/PollinationMode",
          "description": "How the species reproduces. Insect/bird/bat pollination requires a matching pollinator interaction in the world."
        },
        "water_requirement": {
          "description": "Normalized water need: 0 xerophyte, 1 aquatic.",
          "maximum": 1.0,
          "minimum": 0.0,
          "title": "Water Requirement",
          "type": "number"
        },
        "provides_food": {
          "default": false,
          "description": "Whether fauna can feed on this species (fruit, leaves, nectar, seeds).",
          "title": "Provides Food",
          "type": "boolean"
        },
        "provides_shelter": {
          "default": false,
          "description": "Whether the species offers nesting or cover for fauna.",
          "title": "Provides Shelter",
          "type": "boolean"
        },
        "max_height": {
          "description": "Typical mature height in world units.",
          "exclusiveMinimum": 0.0,
          "title": "Max Height",
          "type": "number"
        },
        "description": {
          "default": "",
          "maxLength": 2000,
          "title": "Description",
          "type": "string"
        }
      },
      "required": [
        "id",
        "name",
        "category",
        "biome_ids",
        "pollination",
        "water_requirement",
        "max_height"
      ],
      "title": "FloraSpecies",
      "type": "object"
    },
    "InteractionType": {
      "enum": [
        "predation",
        "herbivory",
        "pollination",
        "seed_dispersal",
        "migration",
        "symbiosis",
        "parasitism",
        "competition",
        "decomposition",
        "nesting",
        "camouflage_host"
      ],
      "title": "InteractionType",
      "type": "string"
    },
    "Interactions": {
      "additionalProperties": false,
      "description": "The full ecological interaction web.",
      "properties": {
        "edges": {
          "items": {
            "$ref": "#/$defs/EcologicalInteraction"
          },
          "title": "Edges",
          "type": "array"
        }
      },
      "title": "Interactions",
      "type": "object"
    },
    "Locomotion": {
      "enum": [
        "walking",
        "climbing",
        "flying",
        "swimming",
        "burrowing",
        "gliding",
        "amphibious"
      ],
      "title": "Locomotion",
      "type": "string"
    },
    "LongTermDynamic": {
      "additionalProperties": false,
      "description": "A declared long-run ecological process.",
      "properties": {
        "id": {
          "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
          "maxLength": 64,
          "minLength": 2,
          "title": "Id",
          "type": "string"
        },
        "name": {
          "maxLength": 120,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "type": {
          "$ref": "#/$defs/DynamicType"
        },
        "period_years": {
          "anyOf": [
            {
              "exclusiveMinimum": 0.0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Cycle period in years, for periodic dynamics.",
          "title": "Period Years"
        },
        "involves_ids": {
          "description": "Ids of species, biomes, interactions, or events this dynamic operates on.",
          "items": {
            "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
            "maxLength": 64,
            "minLength": 2,
            "type": "string"
          },
          "minItems": 1,
          "title": "Involves Ids",
          "type": "array"
        },
        "description": {
          "default": "",
          "maxLength": 2000,
          "title": "Description",
          "type": "string"
        }
      },
      "required": [
        "id",
        "name",
        "type",
        "involves_ids"
      ],
      "title": "LongTermDynamic",
      "type": "object"
    },
    "MoistureLevel": {
      "enum": [
        "arid",
        "semi_arid",
        "moderate",
        "humid",
        "saturated"
      ],
      "title": "MoistureLevel",
      "type": "string"
    },
    "NaturalEvent": {
      "additionalProperties": false,
      "description": "A recurring or one-off natural disturbance and what it affects.",
      "properties": {
        "id": {
          "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
          "maxLength": 64,
          "minLength": 2,
          "title": "Id",
          "type": "string"
        },
        "name": {
          "maxLength": 120,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "type": {
          "$ref": "#/$defs/EventType"
        },
        "severity": {
          "$ref": "#/$defs/Severity",
          "default": "moderate"
        },
        "recurrence_years": {
          "anyOf": [
            {
              "exclusiveMinimum": 0.0,
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Average years between occurrences. Null for one-off events.",
          "title": "Recurrence Years"
        },
        "affected_region_ids": {
          "description": "Layout regions the event affects.",
          "items": {
            "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
            "maxLength": 64,
            "minLength": 2,
            "type": "string"
          },
          "title": "Affected Region Ids",
          "type": "array"
        },
        "affected_biome_ids": {
          "description": "Biomes the event affects.",
          "items": {
            "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
            "maxLength": 64,
            "minLength": 2,
            "type": "string"
          },
          "title": "Affected Biome Ids",
          "type": "array"
        },
        "triggers": {
          "description": "Ids of terrain/water entities that cause this event (e.g. a volcano triggering an eruption, a river triggering a flood).",
          "items": {
            "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
            "maxLength": 64,
            "minLength": 2,
            "type": "string"
          },
          "title": "Triggers",
          "type": "array"
        },
        "description": {
          "default": "",
          "maxLength": 2000,
          "title": "Description",
          "type": "string"
        }
      },
      "required": [
        "id",
        "name",
        "type"
      ],
      "title": "NaturalEvent",
      "type": "object"
    },
    "NaturalEvents": {
      "additionalProperties": false,
      "description": "All natural events in the world.",
      "properties": {
        "events": {
          "items": {
            "$ref": "#/$defs/NaturalEvent"
          },
          "title": "Events",
          "type": "array"
        }
      },
      "title": "NaturalEvents",
      "type": "object"
    },
    "PollinationMode": {
      "enum": [
        "wind",
        "insect",
        "bird",
        "bat",
        "water",
        "self",
        "spore",
        "none"
      ],
      "title": "PollinationMode",
      "type": "string"
    },
    "PrecipitationType": {
      "enum": [
        "none",
        "rain",
        "snow",
        "sleet",
        "hail",
        "mist",
        "ash"
      ],
      "title": "PrecipitationType",
      "type": "string"
    },
    "Rarity": {
      "enum": [
        "abundant",
        "common",
        "uncommon",
        "rare",
        "keystone"
      ],
      "title": "Rarity",
      "type": "string"
    },
    "Region": {
      "additionalProperties": false,
      "description": "A coarse named area of the world referenced by other entities.",
      "properties": {
        "id": {
          "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
          "maxLength": 64,
          "minLength": 2,
          "title": "Id",
          "type": "string"
        },
        "name": {
          "maxLength": 120,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "description": {
          "default": "",
          "maxLength": 2000,
          "title": "Description",
          "type": "string"
        },
        "footprint": {
          "$ref": "#/$defs/BoundingRegion",
          "description": "Spatial extent of the region on the world plane."
        },
        "direction": {
          "$ref": "#/$defs/CardinalDirection",
          "description": "Approximate position of the region relative to the world center."
        },
        "adjacent_to": {
          "description": "Ids of regions sharing a border with this one. Adjacency must be symmetric: if A lists B, B must list A.",
          "items": {
            "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
            "maxLength": 64,
            "minLength": 2,
            "type": "string"
          },
          "title": "Adjacent To",
          "type": "array"
        }
      },
      "required": [
        "id",
        "name",
        "footprint",
        "direction"
      ],
      "title": "Region",
      "type": "object"
    },
    "Season": {
      "additionalProperties": false,
      "description": "One phase of the world's annual cycle.",
      "properties": {
        "id": {
          "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
          "maxLength": 64,
          "minLength": 2,
          "title": "Id",
          "type": "string"
        },
        "name": {
          "maxLength": 120,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "order": {
          "description": "Position in the annual cycle, starting at 0.",
          "minimum": 0,
          "title": "Order",
          "type": "integer"
        },
        "length_fraction": {
          "description": "Fraction of the full year this season occupies. Season length_fractions across the world must sum to ~1.0.",
          "exclusiveMinimum": 0.0,
          "maximum": 1.0,
          "title": "Length Fraction",
          "type": "number"
        },
        "temperature_modifier": {
          "default": 0.0,
          "description": "Additive offset applied to biome average temperatures.",
          "title": "Temperature Modifier",
          "type": "number"
        },
        "precipitation_modifier": {
          "default": 1.0,
          "description": "Multiplier applied to biome annual precipitation.",
          "minimum": 0.0,
          "title": "Precipitation Modifier",
          "type": "number"
        },
        "triggers_event_ids": {
          "description": "Natural event ids that characteristically occur this season (e.g. spring floods, dry-season wildfires).",
          "items": {
            "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
            "maxLength": 64,
            "minLength": 2,
            "type": "string"
          },
          "title": "Triggers Event Ids",
          "type": "array"
        },
        "description": {
          "default": "",
          "maxLength": 2000,
          "title": "Description",
          "type": "string"
        }
      },
      "required": [
        "id",
        "name",
        "order",
        "length_fraction"
      ],
      "title": "Season",
      "type": "object"
    },
    "Seasons": {
      "additionalProperties": false,
      "description": "The full seasonal cycle of the world.",
      "properties": {
        "cycle": {
          "description": "Ordered seasons. A world with no seasonality may declare a single perpetual season.",
          "items": {
            "$ref": "#/$defs/Season"
          },
          "minItems": 1,
          "title": "Cycle",
          "type": "array"
        }
      },
      "required": [
        "cycle"
      ],
      "title": "Seasons",
      "type": "object"
    },
    "Severity": {
      "enum": [
        "minor",
        "moderate",
        "major",
        "catastrophic"
      ],
      "title": "Severity",
      "type": "string"
    },
    "Simulation": {
      "additionalProperties": false,
      "description": "Declared long-term dynamics of the world.",
      "properties": {
        "stability_index": {
          "default": 0.5,
          "description": "Generator's self-assessed ecosystem stability (0 fragile, 1 highly resilient).",
          "maximum": 1.0,
          "minimum": 0.0,
          "title": "Stability Index",
          "type": "number"
        },
        "dynamics": {
          "items": {
            "$ref": "#/$defs/LongTermDynamic"
          },
          "title": "Dynamics",
          "type": "array"
        }
      },
      "title": "Simulation",
      "type": "object"
    },
    "TemperatureBand": {
      "enum": [
        "polar",
        "cold",
        "temperate",
        "warm",
        "hot"
      ],
      "title": "TemperatureBand",
      "type": "string"
    },
    "Terrain": {
      "additionalProperties": false,
      "description": "All landforms in the world plus a sparse elevation field.",
      "properties": {
        "features": {
          "items": {
            "$ref": "#/$defs/TerrainFeature"
          },
          "minItems": 1,
          "title": "Features",
          "type": "array"
        },
        "elevation_samples": {
          "description": "Optional sparse height-field samples validators use to cross-check feature elevations and river flow directions.",
          "items": {
            "$ref": "#/$defs/ElevationSample"
          },
          "title": "Elevation Samples",
          "type": "array"
        }
      },
      "required": [
        "features"
      ],
      "title": "Terrain",
      "type": "object"
    },
    "TerrainFeature": {
      "additionalProperties": false,
      "description": "A single landform anchored to a region.",
      "properties": {
        "id": {
          "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
          "maxLength": 64,
          "minLength": 2,
          "title": "Id",
          "type": "string"
        },
        "name": {
          "maxLength": 120,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "type": {
          "$ref": "#/$defs/TerrainType"
        },
        "region_id": {
          "description": "Id of the layout region this feature primarily occupies.",
          "maxLength": 64,
          "minLength": 2,
          "title": "Region Id",
          "type": "string"
        },
        "footprint": {
          "$ref": "#/$defs/BoundingRegion"
        },
        "base_elevation": {
          "description": "Elevation of the feature's base in world units.",
          "title": "Base Elevation",
          "type": "number"
        },
        "peak_elevation": {
          "description": "Elevation of the feature's highest point. Must be >= base_elevation.",
          "title": "Peak Elevation",
          "type": "number"
        },
        "slope": {
          "default": 0.5,
          "description": "Normalized average steepness: 0 flat, 1 vertical.",
          "maximum": 1.0,
          "minimum": 0.0,
          "title": "Slope",
          "type": "number"
        },
        "volcanic_activity": {
          "anyOf": [
            {
              "$ref": "#/$defs/VolcanicActivity"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Required for 'volcano' features; must be null otherwise."
        },
        "connected_to": {
          "description": "Ids of physically contiguous terrain features (e.g. peaks within a range, a cliff bounding a plateau).",
          "items": {
            "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
            "maxLength": 64,
            "minLength": 2,
            "type": "string"
          },
          "title": "Connected To",
          "type": "array"
        },
        "description": {
          "default": "",
          "maxLength": 2000,
          "title": "Description",
          "type": "string"
        }
      },
      "required": [
        "id",
        "name",
        "type",
        "region_id",
        "footprint",
        "base_elevation",
        "peak_elevation"
      ],
      "title": "TerrainFeature",
      "type": "object"
    },
    "TerrainType": {
      "enum": [
        "mountain",
        "mountain_range",
        "hill",
        "plateau",
        "plain",
        "valley",
        "canyon",
        "cliff",
        "dune_field",
        "mesa",
        "volcano",
        "crater",
        "glacier",
        "cave_system",
        "basin",
        "floating_fragment"
      ],
      "title": "TerrainType",
      "type": "string"
    },
    "TrophicRole": {
      "enum": [
        "producer_consumer",
        "herbivore",
        "omnivore",
        "carnivore",
        "apex_predator",
        "scavenger",
        "decomposer",
        "pollinator",
        "filter_feeder"
      ],
      "title": "TrophicRole",
      "type": "string"
    },
    "VolcanicActivity": {
      "enum": [
        "extinct",
        "dormant",
        "active",
        "erupting"
      ],
      "title": "VolcanicActivity",
      "type": "string"
    },
    "WaterBody": {
      "additionalProperties": false,
      "description": "A single water body participating in the world's flow graph.",
      "properties": {
        "id": {
          "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
          "maxLength": 64,
          "minLength": 2,
          "title": "Id",
          "type": "string"
        },
        "name": {
          "maxLength": 120,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "type": {
          "$ref": "#/$defs/WaterBodyType"
        },
        "quality": {
          "$ref": "#/$defs/WaterQuality",
          "default": "fresh"
        },
        "region_ids": {
          "description": "Layout regions this body passes through or occupies.",
          "items": {
            "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
            "maxLength": 64,
            "minLength": 2,
            "type": "string"
          },
          "minItems": 1,
          "title": "Region Ids",
          "type": "array"
        },
        "footprint": {
          "anyOf": [
            {
              "$ref": "#/$defs/BoundingRegion"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Extent for area bodies (lakes, oceans, wetlands). Linear bodies should use 'path' instead."
        },
        "path": {
          "anyOf": [
            {
              "items": {
                "$ref": "#/$defs/Coordinate2D"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Ordered course for linear bodies (rivers, streams), from source to mouth.",
          "title": "Path"
        },
        "surface_elevation": {
          "description": "Elevation of the water surface at the body's source (for flowing bodies) or overall (for still bodies).",
          "title": "Surface Elevation",
          "type": "number"
        },
        "mouth_elevation": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Elevation where a flowing body ends. Must be <= surface_elevation (water flows downhill).",
          "title": "Mouth Elevation"
        },
        "source_ids": {
          "description": "Ids of terrain features or water bodies feeding this one (e.g. a glacier, spring, or upstream river).",
          "items": {
            "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
            "maxLength": 64,
            "minLength": 2,
            "type": "string"
          },
          "title": "Source Ids",
          "type": "array"
        },
        "flows_to": {
          "anyOf": [
            {
              "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
              "maxLength": 64,
              "minLength": 2,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Id of the downstream water body. Required for flowing types unless the body exits the world at a void/cliff edge (set exits_world instead).",
          "title": "Flows To"
        },
        "exits_world": {
          "default": false,
          "description": "True when the body plunges off the world edge (floating worlds). Mutually exclusive with flows_to.",
          "title": "Exits World",
          "type": "boolean"
        },
        "description": {
          "default": "",
          "maxLength": 2000,
          "title": "Description",
          "type": "string"
        }
      },
      "required": [
        "id",
        "name",
        "type",
        "region_ids",
        "surface_elevation"
      ],
      "title": "WaterBody",
      "type": "object"
    },
    "WaterBodyType": {
      "enum": [
        "ocean",
        "sea",
        "lake",
        "pond",
        "river",
        "stream",
        "waterfall",
        "spring",
        "hot_spring",
        "glacier_melt",
        "lagoon",
        "wetland",
        "oasis"
      ],
      "title": "WaterBodyType",
      "type": "string"
    },
    "WaterQuality": {
      "enum": [
        "fresh",
        "brackish",
        "salt",
        "mineral",
        "glacial"
      ],
      "title": "WaterQuality",
      "type": "string"
    },
    "WaterSystems": {
      "additionalProperties": false,
      "description": "All water bodies in the world.",
      "properties": {
        "bodies": {
          "items": {
            "$ref": "#/$defs/WaterBody"
          },
          "minItems": 1,
          "title": "Bodies",
          "type": "array"
        }
      },
      "required": [
        "bodies"
      ],
      "title": "WaterSystems",
      "type": "object"
    },
    "Weather": {
      "additionalProperties": false,
      "description": "Global winds and per-biome climate patterns.",
      "properties": {
        "prevailing_winds": {
          "items": {
            "$ref": "#/$defs/WindPattern"
          },
          "title": "Prevailing Winds",
          "type": "array"
        },
        "biome_weather": {
          "items": {
            "$ref": "#/$defs/BiomeWeather"
          },
          "minItems": 1,
          "title": "Biome Weather",
          "type": "array"
        }
      },
      "required": [
        "biome_weather"
      ],
      "title": "Weather",
      "type": "object"
    },
    "WindPattern": {
      "additionalProperties": false,
      "description": "A prevailing wind affecting weather and pollination/migration.",
      "properties": {
        "id": {
          "description": "Stable, lowercase snake_case identifier unique within the world (e.g. 'mtn_frostspire', 'river_glass_creek'). Used as the sole reference mechanism for graph relationships between entities.",
          "maxLength": 64,
          "minLength": 2,
          "title": "Id",
          "type": "string"
        },
        "name": {
          "maxLength": 120,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "direction": {
          "description": "Cardinal/intercardinal bearing the wind blows toward (e.g. 'northeast').",
          "title": "Direction",
          "type": "string"
        },
        "strength": {
          "description": "Normalized wind strength.",
          "maximum": 1.0,
          "minimum": 0.0,
          "title": "Strength",
          "type": "number"
        }
      },
      "required": [
        "id",
        "name",
        "direction",
        "strength"
      ],
      "title": "WindPattern",
      "type": "object"
    },
    "WorldLayout": {
      "additionalProperties": false,
      "description": "Global spatial structure of the world.",
      "properties": {
        "topology": {
          "$ref": "#/$defs/WorldTopology"
        },
        "edge_type": {
          "$ref": "#/$defs/EdgeType",
          "description": "Boundary behavior. Floating topologies must use 'void' or 'cliff'; grounded topologies typically use 'ocean'."
        },
        "bounds": {
          "$ref": "#/$defs/BoundingRegion",
          "description": "Overall extent of the world in world units. All entity coordinates must fall inside these bounds."
        },
        "sea_level": {
          "default": 0.0,
          "description": "Elevation of nominal sea level. Water bodies of type 'ocean' sit at this elevation.",
          "title": "Sea Level",
          "type": "number"
        },
        "regions": {
          "description": "Named coarse areas that partition the world.",
          "items": {
            "$ref": "#/$defs/Region"
          },
          "minItems": 1,
          "title": "Regions",
          "type": "array"
        }
      },
      "required": [
        "topology",
        "edge_type",
        "bounds",
        "regions"
      ],
      "title": "WorldLayout",
      "type": "object"
    },
    "WorldMetadata": {
      "additionalProperties": false,
      "description": "Identity and provenance for a generated world.",
      "properties": {
        "id": {
          "description": "Unique identifier for this world.",
          "maxLength": 64,
          "minLength": 2,
          "title": "Id",
          "type": "string"
        },
        "name": {
          "description": "Human-readable world name (e.g. 'The Shattered Verdance').",
          "maxLength": 120,
          "minLength": 1,
          "title": "Name",
          "type": "string"
        },
        "description": {
          "description": "Prose summary of the world's character and defining features.",
          "maxLength": 4000,
          "minLength": 1,
          "title": "Description",
          "type": "string"
        },
        "schema_version": {
          "default": "1.0.0",
          "description": "WorldBench schema version this document conforms to.",
          "title": "Schema Version",
          "type": "string"
        },
        "seed": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Optional deterministic seed the generator claims to have used.",
          "title": "Seed"
        },
        "tags": {
          "description": "Freeform descriptive tags (e.g. 'floating', 'archipelago', 'volcanic').",
          "items": {
            "type": "string"
          },
          "maxItems": 32,
          "title": "Tags",
          "type": "array"
        }
      },
      "required": [
        "id",
        "name",
        "description"
      ],
      "title": "WorldMetadata",
      "type": "object"
    },
    "WorldTopology": {
      "description": "The global shape of the world.",
      "enum": [
        "continent",
        "island",
        "archipelago",
        "floating_island",
        "floating_archipelago",
        "ring",
        "cavern"
      ],
      "title": "WorldTopology",
      "type": "string"
    }
  },
  "additionalProperties": false,
  "description": "A complete WorldBench world.",
  "properties": {
    "metadata": {
      "$ref": "#/$defs/WorldMetadata"
    },
    "layout": {
      "$ref": "#/$defs/WorldLayout"
    },
    "terrain": {
      "$ref": "#/$defs/Terrain"
    },
    "water": {
      "$ref": "#/$defs/WaterSystems"
    },
    "biomes": {
      "$ref": "#/$defs/Biomes"
    },
    "flora": {
      "$ref": "#/$defs/Flora"
    },
    "fauna": {
      "$ref": "#/$defs/Fauna"
    },
    "interactions": {
      "$ref": "#/$defs/Interactions"
    },
    "weather": {
      "$ref": "#/$defs/Weather"
    },
    "seasons": {
      "$ref": "#/$defs/Seasons"
    },
    "natural_events": {
      "$ref": "#/$defs/NaturalEvents"
    },
    "simulation": {
      "$ref": "#/$defs/Simulation"
    }
  },
  "required": [
    "metadata",
    "layout",
    "terrain",
    "water",
    "biomes",
    "flora",
    "fauna",
    "weather",
    "seasons"
  ],
  "title": "WorldBench World",
  "type": "object",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://worldbench.dev/schemas/world_schema_v1.json",
  "x-worldbench-schema-version": "1.0.0"
}
"""
```

---

## Notes for you (not part of the prompt)

- Ask the model to output ONLY the JSON object — no prose, no code fences.
- Save its response as `manual_generation/output/<your_model_name>/world.json`
  (strip any ```` ```json ``` ```` fences first — WorldBench expects raw JSON).
- `<your_model_name>` is a folder you choose, e.g. `claude_opus_4_8` — one per
  model/run you want to compare.
- Then move on to `02_generate_html_prompt.md` for stage 2, or jump straight to
  scoring with `worldbench evaluate manual_generation/output/<your_model_name>`.
