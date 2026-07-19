type Node = {
  id: string;
  label: string;
  x: number;
  y: number;
  w: number;
  h: number;
  isolated?: boolean;
  note?: string;
};

type EdgeKind = "water" | "water-alt" | "causal";

type Edge = {
  from: [number, number];
  to: [number, number];
  kind?: EdgeKind;
  label?: string;
  labelAt?: [number, number];
};

const nodes: Node[] = [
  { id: "mountains", label: "Snow Mountains", x: 40, y: 20, w: 180, h: 50 },
  { id: "forest", label: "Snowy Conifer Forest", x: 40, y: 110, w: 180, h: 50 },
  { id: "highlands", label: "Highlands", x: 40, y: 200, w: 180, h: 50 },
  { id: "jungle", label: "Dense Jungle", x: 40, y: 290, w: 180, h: 50 },
  { id: "grove", label: "Flowering Grove", x: 300, y: 290, w: 180, h: 50 },
  { id: "swamp", label: "Backwater Swamp", x: 40, y: 380, w: 180, h: 50 },
  { id: "grassland", label: "Grassland Plateau", x: 300, y: 380, w: 180, h: 50 },
  { id: "delta", label: "Coastal Delta / Ocean", x: 160, y: 470, w: 220, h: 50 },
  {
    id: "desert",
    label: "Desert Basin",
    x: 580,
    y: 110,
    w: 180,
    h: 50,
    isolated: true,
    note: "rain-shadow, no through-river",
  },
  {
    id: "volcano",
    label: "Volcano",
    x: 580,
    y: 290,
    w: 180,
    h: 50,
    isolated: true,
    note: "isolated, lava not water",
  },
];

const edges: Edge[] = [
  { from: [130, 70], to: [130, 110] },
  { from: [130, 160], to: [130, 200] },
  { from: [130, 250], to: [120, 290] },
  { from: [220, 240], to: [300, 300] },
  { from: [120, 340], to: [120, 380] },
  { from: [200, 320], to: [300, 400] },
  { from: [360, 430], to: [330, 470] },
  // grove's other feed: "highland slope and/or plains"; grassland is the alt source
  {
    from: [390, 380],
    to: [390, 340],
    kind: "water-alt",
    label: "and/or",
    labelAt: [415, 362],
  },
  // stated causal rule: lava meeting water quenches to obsidian; incidental
  // contact, not a through-river, so it's drawn distinctly from the flow
  {
    from: [220, 245],
    to: [580, 305],
    kind: "causal",
    label: "water + lava → obsidian",
    labelAt: [400, 258],
  },
];

const strokeFor: Record<EdgeKind, string> = {
  water: "var(--color-glow)",
  "water-alt": "var(--color-glow)",
  causal: "#d9822b",
};

const dashFor: Record<EdgeKind, string | undefined> = {
  water: undefined,
  "water-alt": "6 4",
  causal: "2 4",
};

const markerFor: Record<EdgeKind, string> = {
  water: "url(#biome-arrow)",
  "water-alt": "url(#biome-arrow)",
  causal: "url(#biome-arrow-causal)",
};

export default function BiomeGraph() {
  return (
    <div className="not-prose my-4 w-full overflow-x-auto rounded-lg border border-line p-4">
      <svg
        viewBox="0 0 800 560"
        className="h-auto w-full min-w-[640px]"
        role="img"
        aria-label="Diagram of biome placement and water-flow relationships"
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
          return (
            <g key={i}>
              <line
                x1={edge.from[0]}
                y1={edge.from[1]}
                x2={edge.to[0]}
                y2={edge.to[1]}
                stroke={strokeFor[kind]}
                strokeWidth={kind === "water" ? 1.5 : 1.2}
                strokeDasharray={dashFor[kind]}
                markerEnd={markerFor[kind]}
              />
              {edge.label && edge.labelAt && (
                <text
                  x={edge.labelAt[0]}
                  y={edge.labelAt[1]}
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
              x={node.x}
              y={node.y}
              width={node.w}
              height={node.h}
              rx={8}
              fill="var(--color-void-deep)"
              stroke={node.isolated ? "var(--color-mist)" : "var(--color-line)"}
              strokeWidth={1.5}
              strokeDasharray={node.isolated ? "4 4" : undefined}
            />
            <text
              x={node.x + node.w / 2}
              y={node.y + node.h / 2 + (node.note ? -3 : 5)}
              textAnchor="middle"
              fontSize="13"
              fill="var(--color-mist-bright)"
            >
              {node.label}
            </text>
            {node.note && (
              <text
                x={node.x + node.w / 2}
                y={node.y + node.h / 2 + 14}
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
          Water flow (required)
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
            style={{ borderColor: "#d9822b" }}
          />
          Causal contact, not a river
        </li>
      </ul>
    </div>
  );
}
