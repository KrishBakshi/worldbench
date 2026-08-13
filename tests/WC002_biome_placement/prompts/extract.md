This is per-biome layout JS from a Three.js island.
Canonical ids (id: label):
{biome_list}

For each biome with present=true, use placement_code and elevation_code only.
For present=false: neighbors=[], evidence="not in source". Do not invent from ecology.

Return JSON only:
{
  "nodes": [
    {
      "id": "mountains"|"forest"|"highlands"|"jungle"|"swamp"|"grove"|"grassland"|"delta"|"desert"|"volcano",
      "neighbors": ["<canonical_id>"],
      "evidence": "<code / coordinate / generation clue>"
    }
  ],
  "elevation_order": ["<id>", "<id>", "<id>", "<id>", "<id>", "<id>", "<id>", "<id>", "<id>", "<id>"]
}

Rules:
- nodes: all 10 ids. neighbors = biomes that touch in XZ (boxes, centers, region edges).
- elevation_order: all 10 ids, highest altitude to lowest, from elevation_code numbers — not real-world elevation.
- present=false ids go last in elevation_order.
