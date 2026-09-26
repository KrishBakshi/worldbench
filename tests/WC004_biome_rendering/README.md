# WC004 Physics

WC003 asks *whether* a thing is there. This test asks whether it *looks* like that thing and *moves* on the right axis: blizzard blows on peaks, sandstorms blow, rain falls, fish swim, lava sits.

![Probe then grade](graph.svg)

Same ten-biome map as WC002. The strip is the check: probe look and motion per biome, then grade.

## Flow

```mermaid
flowchart TD
    html["world.html"]
    html --> strip["strip to inline JS"]
    strip --> probe["code probe (LLM) x 10 biomes: look + motion + axis"]
    html --> cap["shared capture: same frames WC000 judged"]
    cap --> vis["visual judge (VLM): does it look like looks_like?"]
    probe --> grade["still entity: half code look, half seen\nmoving entity: half code motion, half look"]
    vis --> grade
    grade --> score["10 points per biome, max 100"]
    score --> gate["WC000 no seabed: drop delta points"]
```

1. The code probe works as before: each biome's `prompts/<id>/prompt.md` plus `templates.json` returns look evidence, motion evidence and an axis. Both quotes must really appear in the source.
2. The visual judge checks each entity against its `looks_like` on the biome's frame and the overview.
3. A still entity's points are split: half for the code's look, half for being seen. A moving entity puts half on motion from the code (a time update on a compatible axis, not spawn-only, not evidence reused from another entity). The other half is split between the code's look and the frames. A still frame can't show which way rain falls, so motion is never judged visually.
4. Forbidden entities found by either the code or the frames subtract. A biome absent from both scores 0. An entity may carry a `weight`; the default is 1.

If WC000's source judge puts `water_bed` or `water_physics` below 0.5, or its bug-hunt sees `ocean_void`, the Coastal Delta / Ocean points are removed from this total.

Axes the grader accepts: falling, blowing, rising, still, flowing, grounded, pulsing, n/a. Close aliases map (down → falling, wind → blowing).

Re-score a saved probe:

```bash
uv run python tests/WC004_biome_rendering/main.py --regrade path/to/rendering.json
```

## Run

```bash
uv run python -m eval.run fable --test WC004
uv run python tests/WC004_biome_rendering/main.py path/to/world.html out_dir
```
