You are reading the full JS source of a Three.js floating-island world. Work out which
biomes sit next to each other on the island's XZ map.
Canonical ids (id: label):
{biome_list}

Method: (1) find where the layout decides which biome a cell belongs to: region or seed
centres with their coordinates (look for a table of centres/radii, even if it is named by
index or by a different label), distance/angle/band tests, boxes, rim and coast rules.
(2) Using those numbers, decide which biomes' regions share a border. For nearest-centre
(Voronoi) layouts, two biomes touch when their centres are close and no other centre lies
between them. Treat noise terms as zero. "delta" is the coast/ocean/water edge of the island.

Evidence rule: list a neighbour ONLY if the positions you found put the two regions next to
each other; quote the numbers in evidence. Never add a neighbour from ecology or from the
names. If you cannot find positions for a biome, neighbors=[] and evidence="no positions".
Do NOT list a biome as touching everything just because a loop tests all of them.

Also give elevation_order: all 10 ids, highest ground first, from the height numbers in the
code, not real-world elevation.

Return JSON only:
{
  "nodes": [
    {
      "id": "mountains"|"forest"|"highlands"|"jungle"|"swamp"|"grove"|"grassland"|"delta"|"desert"|"volcano",
      "neighbors": ["<canonical_id>"],
      "evidence": "<the numbers / code that put the two regions side by side>"
    }
  ],
  "elevation_order": ["<id>", "<id>", "<id>", "<id>", "<id>", "<id>", "<id>", "<id>", "<id>", "<id>"]
}
nodes: all 10 ids.
