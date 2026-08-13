From SOURCE (inline JS of a Three.js island), extract biome-layout code.

Canonical ids (every key required):
mountains, forest, highlands, jungle, swamp, grove, grassland, delta, desert, volcano

Return JSON only:
{
  "biomes": {
    "<id>": {
      "present": true|false,
      "aliases": ["SOURCE_TOKEN"],
      "placement_code": "<verbatim JS that places this biome in XZ>",
      "elevation_code": "<verbatim JS that sets this biome's height>"
    }
  }
}

Rules:
- Emit all 10 keys. Never omit.
- present false → aliases [], both code fields "".
- Copy lines only, no paraphrase. No neighbors. No scene/lights/trees/colors.
- ocean/beach/coast → delta. conifer/pine/taiga → forest. plains → grassland.
