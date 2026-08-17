From SOURCE (inline JS of a Three.js island), judge **physical rendering and motion** for Snow Mountains entities only.

Canonical biome id: mountains
Snow Mountains source aliases (any count as mountains scope):
mountain, mountains, snow_mountain, snow_rock, alpine, peak, SMT, PEAK, MOUNT, Snow Mountains

TEMPLATES (JSON — every entity id below must appear in your response):
{TEMPLATES}

Return JSON only:
{
  "biome": "mountains",
  "aliases": ["SOURCE_TOKEN"],
  "entities": {
    "<id>": {
      "looks_ok": true|false,
      "moves_ok": true|false,
      "axis": "n/a|falling|blowing|rising|still|flowing|grounded|pulsing",
      "look_evidence": "<verbatim constructor/placement JS, else \"not in mountains scope\">",
      "motion_evidence": "<verbatim animate/update JS for motion items; empty string for static items>"
    }
  },
  "must_not_present": {
    "<id>": {
      "found": true|false,
      "evidence": "<verbatim leak JS in mountains scope if present, else \"not in mountains scope\">"
    }
  }
}

Rules:
- Emit every id in TEMPLATES.entities and TEMPLATES.must_not_present. Never omit.
- Search ONLY mountains scope: biome return/case/id for aliases above, plus mountains-tagged weather/flora/fauna/water constructors.
- A hit in a different biome's branch does NOT count.
- Copy the **smallest** verbatim snippet that proves each claim. No paraphrase. Do not invent code not in SOURCE.
- Each TEMPLATES.entities item has `"requires_motion": true|false`. Follow it exactly.

**Static items (`requires_motion: false`)** — terrain, flora, still water, surface recipe, biome tint/colormap:
- looks_ok true only if look_evidence is real placement/geometry/color/height code in this biome.
- Climate identity is visual: arid sand tint, swamp olive water, jungle lime foliage, snow-over-stone, sand-over-sandstone. A legend color is not a tint.
- Set moves_ok true, axis "n/a", motion_evidence "" (empty string). Do NOT write "not in scope" for motion on static items.
- If absent: looks_ok false, look_evidence "not in mountains scope", motion_evidence "".

**Motion items (`requires_motion: true`)** — weather, flowing water, fauna, pulsing glow:
- looks_ok AND moves_ok must be true.
- look_evidence = spawn/placement/config **for this biome's system** (scatter bounds, particle create, river channel, fauna spawn).
- motion_evidence = **different** lines from animate/update that integrate that system over time (any style: dt, time, position.+=, position.x=, velocities[], attributes.position, updateWeather branch, forEach wander).
- Name the **dominant** axis honestly. If unsure horizontal vs falling, set moves_ok false.
  - falling: rain/snow down (y dominates negative)
  - blowing: sandstorm/blizzard horizontal (x/z dominate)
  - rising: ash/steam up (y dominates positive)
  - still: mist/haze hang (minimal drift)
  - flowing: river/foam along channel
  - grounded: fauna y from terrain each frame or wander on ground
  - pulsing: glow/intensity/crater oscillation
- Precipitation type is climate: desert sandstorm must not be rain; peaks blizzard/snow not jungle rain; jungle rain not snow.

**Behavior, not API names.** Sandstorm must blow, not fall like rain. Blizzard blows on peaks, not gentle snowfall. Spawn-only fauna (fixed y, no update) is looks_ok at best — moves_ok false.

NEVER looks_ok true for: comments; legend/enum rows (`{ id, label, color, weather }` or `DESERT: { id...}`); bare biome-id token; lone waypoint; config row **without** any particle/mesh placement elsewhere for that weather system.

Shared helpers (makeTree, updateWeather, WeatherSystem): copy **this biome's arguments** (colors, velocity init, bounds, type branch) — not the generic signature alone.

must_not_present: found true = wrong look/motion leak inside mountains scope.

If the whole biome is absent: aliases [], every looks_ok/moves_ok false, look_evidence "not in mountains scope".

SOURCE:
{SOURCE}
