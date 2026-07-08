# Stage 2 — Build a Three.js visualization from a world.json

This is the **second stage** of a two-artifact WorldBench task. Stage 1
generates `world.json` (see the task's own `prompt.md`). This template is the
prompt for stage 2: turning that exact JSON into a self-contained, explorable
3D visualization.

This stage is task-agnostic — the same prompt works for any `world.json` that
conforms to the WorldBench `World` schema. Paste the target world's JSON where
indicated below.

---

```text
You are given a complete WorldBench world as a single JSON object below. Build
a self-contained, single HTML file that renders this EXACT world as an
explorable 3D scene using Three.js, so a visitor can move the camera freely and
see the terrain, water, biomes, flora, and fauna this JSON actually describes.

REQUIREMENTS (all are hard requirements, not suggestions):

1. EMBED THE JSON VERBATIM. Include the exact JSON below, unmodified, inside
   the HTML in this exact form:
   <script type="application/json" id="world-data">
   ...the JSON, verbatim...
   </script>

2. READ IT BACK PROGRAMMATICALLY. Your rendering code must read that same
   script tag at runtime (e.g. via
   `JSON.parse(document.getElementById('world-data').textContent)`) and build
   the entire scene FROM that parsed object — not from hardcoded values you
   write separately. If a person swapped the embedded JSON for a different
   world, your code should render that different world correctly without any
   other changes.

3. USE THE ACTUAL DATA. At minimum, your scene must derive from the parsed
   object:
   - terrain shape from `terrain.features` (elevations, footprints, types)
   - water bodies from `water.bodies` (type, path/footprint, elevations)
   - biome zones from `biomes.zones` (type, region, footprint/elevation range)
   - flora and fauna placed within the biomes from `flora.species` /
     `fauna.species`
   Don't invent a different world, and don't build a generic scene that
   ignores the specifics of this JSON (mismatched names, ids, or layout will
   fail fidelity checks).

4. THREE.JS, SINGLE FILE. Use Three.js (CDN import map or script tag is fine)
   inside one `.html` file with a `<canvas>` to render into. No build step, no
   separate asset files — it must just open in a browser and run.

5. FREE CAMERA. Let the viewer orbit, zoom, and pan around the whole world
   (e.g. OrbitControls). Keep on-screen text minimal.

Output ONLY the complete HTML file — no prose, no commentary, no code fences.

────────────────────────────────────────────────────────
THE WORLD (paste the target world.json below, verbatim)
────────────────────────────────────────────────────────
<PASTE world.json HERE>
```

---

## Notes for you (not part of the prompt)

- Requirement 1 exists so the benchmark has ground truth to check
  deterministically: `worldbench score-html` looks for exactly this
  `id="world-data"` script tag, parses it, and confirms its `metadata.id`
  matches the source `world.json` you're grading against.
- Requirement 2 exists so a model can't pass by embedding the JSON inertly
  while actually rendering a generic, hardcoded scene — the checker also looks
  for evidence the code reads the blob back out (`getElementById`/
  `querySelector` + `JSON.parse`) and that it references the schema's actual
  section keys and entity ids outside the embedded blob.
- This does **not** replace stage 1's own JSON scoring (`worldbench validate` /
  `score`) — the HTML gets its own separate fidelity score
  (`worldbench score-html`), it is not blended into the JSON's `/100`.
