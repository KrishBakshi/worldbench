From SOURCE (inline JS of a Three.js island), judge **global cyclic time** only: day/night orbit and season loops.

This is NOT per-biome climate (that is WC004). Do not score jungle rain or desert sandstorm here unless it is *scaled by a season multiplier* or tied to the day clock.

The generation prompt requires a square sun, day/night, seasons, land darkening, and a **black void**. It never names a moon. It **bans** stars and an atmosphere/sky dome. Score those two facts separately:

- **moon** (entity): extra-reasoning credit. looks_ok if a real 3D moon mesh exists (box/sphere/disc in the scene). Stars, HUD moon emoji, or comments do **not** count. moves_ok if it tracks opposite the sun, orbits, or toggles visibility/opacity with night.
- **stars_or_atmosphere_dome** (leak): found true **deducts**. Star Points, starfield, twinkling sky dots, Sky/skybox, or an atmosphere/sky dome mesh wrapping the world. NOT weather `THREE.Points` (rain/snow/ash/sand). NOT `scene.background = Color(0x000000)` or a comment that says "no stars".

TEMPLATES (JSON — every entity id below must appear in your response):
{TEMPLATES}

Return JSON only:
{
  "biome": "cycle",
  "aliases": ["SOURCE_TOKEN"],
  "entities": {
    "<id>": {
      "looks_ok": true|false,
      "moves_ok": true|false,
      "axis": "n/a|cyclic|pulsing|still",
      "look_evidence": "<verbatim spawn/setup JS, else \"not in cycle scope\">",
      "motion_evidence": "<verbatim animate/update JS that advances the cycle>"
    }
  },
  "must_not_present": {
    "<id>": {
      "found": true|false,
      "evidence": "<verbatim leak JS if present, else \"not in cycle scope\">"
    }
  }
}

Rules:
- Emit every id in TEMPLATES.entities and TEMPLATES.must_not_present. Never omit.
- Copy the **smallest** verbatim snippet. No paraphrase. Do not invent code.
- All cycle items have requires_motion true: look_evidence (sun mesh, season table, cloud group, moon mesh) MUST differ from motion_evidence (animate loop).
- axis is **cyclic** when the value repeats with time (orbit, % 4 seasons, wrap clouds, moon opposite sun). pulsing is acceptable for intensity oscillation. n/a is wrong for these items.
- Judge **behavior**, not API names. `sun.position.set(cos(a), sin(a), …)`, `elev=Math.sin(ang)`, `yr=t/80%4`, `seasonProgress +=`, `clouds.position.x += dt`, `moon.position.copy(sunDir).multiplyScalar(-1)` all count. Helper names differ.
- Season HUD (`textContent = seasons[i]`) is NOT season_world_tint and NOT season_modulates_weather. Those need lighting, fog, terrain color, or weather multipliers.
- NEVER looks_ok true for: comments; legend `{ id, label, weather }`; HUD-only strings; a sun created once with no later position update (that fails moves_ok).
- moon: looks_ok only for a mesh added to the scene. Clock strings / unicode sun-moon glyphs are HUD, not a moon. A starfield is not a moon (and is a leak).
- stars_or_atmosphere_dome: found true if SOURCE actually builds stars or a sky/atmosphere dome. found false if the void is a flat black `scene.background` Color, or if Points are rain/snow/ash/sand weather.
- If day/night or seasons are absent, looks_ok/moves_ok false with evidence "not in cycle scope".

SOURCE:
{SOURCE}
