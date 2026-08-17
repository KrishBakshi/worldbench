From SOURCE (inline JS of a Three.js island), judge Highlands micro-contents only.

Canonical biome id: highlands
Highlands source aliases (any of these count as highlands scope):
highland, highlands, HIGHLAND, HIGHLANDS, HIG, HIGH, upland, Temperate Highlands

REQUIREMENTS (JSON):
{REQUIREMENTS}

Return JSON only:
{
  "biome": "highlands",
  "aliases": ["SOURCE_TOKEN"],
  "must_present": {
    "<id>": {
      "found": true|false,
      "evidence": "<verbatim implementing JS, else \"not in highlands scope\">"
    }
  },
  "must_not_present": {
    "<id>": {
      "found": true|false,
      "evidence": "<verbatim implementing JS in highlands scope if the leak is there, else \"not in highlands scope\">"
    }
  }
}

Rules:
- Emit every id in REQUIREMENTS.must_present and REQUIREMENTS.must_not_present. Never omit.
- Search ONLY highlands scope: biome return/case/id for the aliases above, plus highlands-tagged weather/flora/fauna constructors.
- A keyword hit in a different biome's case/branch does NOT count.
- Copy evidence lines only. No paraphrase. Do not invent fauna/flora that is not in SOURCE.
- REQUIREMENTS include characteristic biome contents a reasoned world should have built — missing them is found false, even if SOURCE never names the word.
- found true ONLY if the copied evidence mutates the visible world in this biome: height or surface/voxel color assignment, or a function that places boxes/meshes/particles/animals. Helper names differ by world — copy whatever SOURCE uses. Do not require a particular API. An if/case with no body does not count.
- NEVER found true for: a `//` comment; a legend/enum `{ id, label, color, weather }`; a bare biome-id token; a lone `{ x, z }` waypoint; a `{ count, color, spread }` config row with no placing call.
- Random darts over the whole map (`Math.random() * GRID` then continue if wrong biome) do NOT count as flora/fauna. Placement into this biome's own cells, or a biome-tagged place/spawn helper, does count.
- If the feature is absent, found must be false and evidence must be "not in highlands scope". Never set found true with that evidence.
- must_present: found true is good. must_not_present: found true is a leak (forbidden thing is inside highlands's own flora/terrain/weather branch).
- Weather counts only as particles actually placed on this biome's cells (copy the scatter/points call, not a legend `weather:` string or a config row). Flora counts only as boxes/meshes placed in this biome. Fauna counts only as a spawn/place call in this biome — an allow-list of ids is not a spawn.
- If the highlands biome itself is missing, set aliases [] and every found false with evidence "not in highlands scope".

SOURCE:
{SOURCE}
