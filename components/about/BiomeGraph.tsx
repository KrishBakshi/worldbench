type Node = {
  id: string;
  label: string;
  /** Node centre, in SVG units. Rects are derived from this so edges can be
   *  clipped to the border toward their neighbour. */
  cx: number;
  cy: number;
  w: number;
  h: number;
  isolated?: boolean;
  note?: string;
};

// water      : the required perennial corridor (solid).
// water-alt  : an "and/or" feed — a second valid source for the same biome.
// dry        : an ephemeral dry wash that fades out — a real link, but not a
//              through-river. This is how the desert relates to the wet system.
// causal     : an incidental causal contact (lava meeting water), not a river.
type EdgeKind = "water" | "water-alt" | "dry" | "causal";

type Edge = {
  from: string;
  to: string;
  kind?: EdgeKind;
  label?: string;
  /** Nudge the label off the edge midpoint when the default would collide. */
  labelOffset?: [number, number];
};

const nodes: Node[] = [
  { id: "mountains", label: "Snow Mountains", cx: 340, cy: 52, w: 176, h: 46 },
  { id: "forest", label: "Snowy Conifer Forest", cx: 340, cy: 145, w: 190, h: 46 },
  { id: "highlands", label: "Highlands", cx: 130, cy: 172, w: 168, h: 46 },
  { id: "jungle", label: "Dense Jungle", cx: 362, cy: 252, w: 168, h: 46 },
  { id: "swamp", label: "Backwater Swamp", cx: 95, cy: 322, w: 168, h: 46 },
  { id: "grove", label: "Flowering Grove", cx: 250, cy: 438, w: 168, h: 46 },
  { id: "grassland", label: "Grassland Plateau", cx: 372, cy: 372, w: 180, h: 46 },
  { id: "delta", label: "Coastal Delta / Ocean", cx: 348, cy: 512, w: 200, h: 46 },
  {
    id: "desert",
    label: "Desert Basin",
    cx: 652,
    cy: 330,
    w: 180,
    h: 46,
    isolated: true,
    note: "arid — only fading dry washes",
  },
  {
    id: "volcano",
    label: "Volcano",
    cx: 662,
    cy: 128,
    w: 168,
    h: 46,
    isolated: true,
    note: "isolated — lava, not water",
  },
];

const edges: Edge[] = [
  // The required wet corridor: mountain melt weaves down to the coast in one
  // continuous, perennial line.
  { from: "mountains", to: "forest" },
  { from: "forest", to: "highlands" },
  { from: "highlands", to: "jungle" },
  { from: "jungle", to: "grassland" },
  { from: "grassland", to: "delta" },
  // The jungle's stagnant backwater — connected to its wet side, but a dead end,
  // not part of the corridor's throughflow.
  { from: "jungle", to: "swamp" },
  // The grove has two valid sources, which makes it the graph's one cycle:
  // straight down the highland slope, and/or across from the plains.
  { from: "highlands", to: "grove", kind: "water-alt" },
  { from: "grassland", to: "grove", kind: "water-alt", label: "and/or", labelOffset: [18, -2] },
  // Desert is linked to the plains only by dry washes that fade before they
  // arrive — related, but never a through-river.
  {
    from: "grassland",
    to: "desert",
    kind: "dry",
    label: "dry washes — fade out",
    labelOffset: [-18, -8],
  },
  // The one rule that still reaches the volcano: lava meeting water quenches to
  // obsidian. Incidental contact, drawn distinctly from any flow.
  {
    from: "jungle",
    to: "volcano",
    kind: "causal",
    label: "water + lava → obsidian",
    labelOffset: [0, -8],
  },
];

const strokeFor: Record<EdgeKind, string> = {
  water: "var(--color-glow)",
  "water-alt": "var(--color-glow)",
  dry: "#c9a15a",
  causal: "#d9822b",
};

const dashFor: Record<EdgeKind, string | undefined> = {
  water: undefined,
  "water-alt": "6 4",
  dry: "1 5",
  causal: "2 4",
};

const widthFor: Record<EdgeKind, number> = {
  water: 1.6,
  "water-alt": 1.2,
  dry: 1.2,
  causal: 1.2,
};

const opacityFor: Record<EdgeKind, number> = {
  water: 1,
  "water-alt": 1,
  dry: 0.75,
  causal: 1,
};

const markerFor: Record<EdgeKind, string> = {
  water: "url(#biome-arrow)",
  "water-alt": "url(#biome-arrow)",
  dry: "url(#biome-arrow-dry)",
  causal: "url(#biome-arrow-causal)",
};

const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));

/** Point where the ray from a node's centre toward `target` crosses its border,
 *  pushed out by `pad` so arrowheads sit just clear of the box. */
function borderPoint(node: Node, target: Node, pad = 4) {
  const dx = target.cx - node.cx;
  const dy = target.cy - node.cy;
  const hw = node.w / 2;
  const hh = node.h / 2;
  const scale = Math.min(
    Math.abs(dx) < 1e-6 ? Infinity : hw / Math.abs(dx),
    Math.abs(dy) < 1e-6 ? Infinity : hh / Math.abs(dy),
  );
  const len = Math.hypot(dx, dy) || 1;
  return {
    x: node.cx + dx * scale + (dx / len) * pad,
    y: node.cy + dy * scale + (dy / len) * pad,
  };
}

export default function BiomeGraph() {
  return (
    <div className="not-prose my-4 w-full overflow-x-auto rounded-lg border border-line p-4">
      <svg
        viewBox="0 0 800 560"
        className="h-auto w-full min-w-[640px]"
        role="img"
        aria-label="Ecological relationship graph of the prompt's biomes: the required water corridor, the flowering grove's alternate feeds, the desert's ephemeral dry washes, and the volcano's obsidian contact"
      >
        <defs>
          <marker
            id="biome-arrow"
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M0 0L10 5L0 10z" fill="var(--color-glow)" />
          </marker>
          <marker
            id="biome-arrow-dry"
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M0 0L10 5L0 10z" fill="#c9a15a" opacity="0.75" />
          </marker>
          <marker
            id="biome-arrow-causal"
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M0 0L10 5L0 10z" fill="#d9822b" />
          </marker>
        </defs>

        {edges.map((edge, i) => {
          const kind = edge.kind ?? "water";
          const a = byId[edge.from];
          const b = byId[edge.to];
          const p1 = borderPoint(a, b);
          const p2 = borderPoint(b, a);
          const mid: [number, number] = [(p1.x + p2.x) / 2, (p1.y + p2.y) / 2];
          const off = edge.labelOffset ?? [0, 0];
          return (
            <g key={i}>
              <line
                x1={p1.x}
                y1={p1.y}
                x2={p2.x}
                y2={p2.y}
                stroke={strokeFor[kind]}
                strokeWidth={widthFor[kind]}
                strokeDasharray={dashFor[kind]}
                strokeOpacity={opacityFor[kind]}
                markerEnd={markerFor[kind]}
              />
              {edge.label && (
                <text
                  x={mid[0] + off[0]}
                  y={mid[1] + off[1]}
                  textAnchor="middle"
                  fontSize="10"
                  fill={strokeFor[kind]}
                >
                  {edge.label}
                </text>
              )}
            </g>
          );
        })}

        {nodes.map((node) => (
          <g key={node.id}>
            <rect
              x={node.cx - node.w / 2}
              y={node.cy - node.h / 2}
              width={node.w}
              height={node.h}
              rx={8}
              fill="var(--color-void-deep)"
              stroke={node.isolated ? "var(--color-mist)" : "var(--color-line)"}
              strokeWidth={1.5}
              strokeDasharray={node.isolated ? "4 4" : undefined}
            />
            <text
              x={node.cx}
              y={node.cy + (node.note ? -3 : 5)}
              textAnchor="middle"
              fontSize="13"
              fill="var(--color-mist-bright)"
            >
              {node.label}
            </text>
            {node.note && (
              <text
                x={node.cx}
                y={node.cy + 14}
                textAnchor="middle"
                fontSize="9"
                fill="var(--color-mist)"
              >
                {node.note}
              </text>
            )}
          </g>
        ))}
      </svg>

      <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-xs text-mist">
        <li className="flex items-center gap-2">
          <span className="inline-block h-0.5 w-5" style={{ background: "var(--color-glow)" }} />
          Water flow (required corridor)
        </li>
        <li className="flex items-center gap-2">
          <span
            className="inline-block h-0 w-5 border-t-2 border-dashed"
            style={{ borderColor: "var(--color-glow)" }}
          />
          Water flow (and/or, optional)
        </li>
        <li className="flex items-center gap-2">
          <span
            className="inline-block h-0 w-5 border-t-2 border-dotted"
            style={{ borderColor: "#c9a15a" }}
          />
          Dry wash (ephemeral, fades out)
        </li>
        <li className="flex items-center gap-2">
          <span
            className="inline-block h-0 w-5 border-t-2 border-dotted"
            style={{ borderColor: "#d9822b" }}
          />
          Causal contact, not a river
        </li>
      </ul>
    </div>
  );
}
