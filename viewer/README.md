# WorldBench Viewer (optional — placeholder in v1)

The viewer is an **optional** companion to WorldBench. The benchmark itself is
the primary deliverable and is fully functional without it. This directory is a
**placeholder scaffold in v1**: it documents the intended design but ships no
application code.

## Purpose

Give humans an intuitive way to *inspect* a generated `world.json` — not to
score it. Scoring is always the job of the deterministic validators and metrics.
The viewer is a debugging and demonstration aid: load a world and see its
terrain, biomes, water, and ecological graph.

## Intended stack

- **Next.js** — app shell and routing
- **React Three Fiber** (`@react-three/fiber`) — declarative Three.js in React
- **Three.js** — 3D rendering
- **@react-three/drei** — camera controls, helpers

## Intended architecture

```
world.json ──► loader ──► React state
                              │
                              ├─ TerrainMesh    heightfield from terrain features
                              │                 + elevation_samples, colored by biome
                              ├─ WaterLayer     rivers as ribbons along `path`,
                              │                 lakes/oceans as planes at surface_elevation,
                              │                 waterfalls at `exits_world` edges
                              ├─ BiomeOverlay   translucent regions tinted by biome type
                              ├─ EntityMarkers  flora/fauna placed within their biomes
                              └─ EcologyGraph   2D overlay of the interaction web
                                                (predation, pollination, migration)
```

The viewer would consume the same `World` schema the benchmark uses
(`benchmark/schemas/world_schema_v1.json`), so it never needs its own data model.

## Status

Not implemented in v1. The `package.json` here lists the intended dependencies
so a future contributor can `npm install` and begin, but there is no `pages/`,
`app/`, or component source yet. Building it is tracked as future work.

## Getting started (when implemented)

```bash
cd viewer
npm install
npm run dev        # would serve the viewer at http://localhost:3000
```
