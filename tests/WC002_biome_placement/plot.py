"""graph.json for the website + graph.svg for a local click-to-open preview.

Same node positions as worldbench-web/components/about/BiomeGraph.tsx.
Outlines use the NetworkX colors: green = ok, red = fail.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))

from extract import BIOME_LABELS
from llm import CheckResult, ExtractedGraph

OK = "#2ecc71"
FAIL = "#e74c3c"
EDGE = "#95a5a6"

# cx, cy, w, h — copied from BiomeGraph.tsx
LAYOUT = {
    "mountains": {"cx": 340, "cy": 52, "w": 176, "h": 46},
    "forest": {"cx": 340, "cy": 145, "w": 190, "h": 46},
    "highlands": {"cx": 130, "cy": 172, "w": 168, "h": 46},
    "jungle": {"cx": 362, "cy": 252, "w": 168, "h": 46},
    "swamp": {"cx": 95, "cy": 322, "w": 168, "h": 46},
    "grove": {"cx": 250, "cy": 438, "w": 168, "h": 46},
    "grassland": {"cx": 372, "cy": 372, "w": 180, "h": 46},
    "delta": {"cx": 348, "cy": 512, "w": 200, "h": 46},
    "desert": {"cx": 652, "cy": 330, "w": 180, "h": 46, "isolated": True},
    "volcano": {"cx": 662, "cy": 128, "w": 168, "h": 46, "isolated": True},
}

VIEWBOX = {"width": 800, "height": 560}


def graph_payload(graph: ExtractedGraph, result: CheckResult) -> dict:
    found = result.details.get("found", {})
    missing = result.details.get("missing", {})
    by_id = {n.id: n for n in graph.nodes}

    nodes = []
    seen = set()
    for bid, label in BIOME_LABELS.items():
        node = by_id.get(bid)
        neighbors = list(node.neighbors) if node else []
        for n in neighbors:
            seen.add(tuple(sorted((bid, n))))
        passed = bid in found
        nodes.append({
            "id": bid,
            "label": label,
            "neighbors": neighbors,
            "evidence": node.evidence if node else "",
            "passed": passed,
            "reason": found.get(bid) or missing.get(bid) or "missing from graph",
            **LAYOUT[bid],
        })

    return {
        "viewBox": VIEWBOX,
        "score": result.details.get("score", 0),
        "max_score": result.details.get("max_score", 10),
        "passed": result.passed,
        "elevation_order": list(graph.elevation_order),
        "nodes": nodes,
        "edges": [{"from": a, "to": b} for a, b in sorted(seen)],
    }


def _border(a: dict, b: dict, pad: float = 4) -> tuple[float, float]:
    dx, dy = b["cx"] - a["cx"], b["cy"] - a["cy"]
    hw, hh = a["w"] / 2, a["h"] / 2
    sx = math.inf if abs(dx) < 1e-6 else hw / abs(dx)
    sy = math.inf if abs(dy) < 1e-6 else hh / abs(dy)
    scale = min(sx, sy)
    length = math.hypot(dx, dy) or 1
    return a["cx"] + dx * scale + (dx / length) * pad, a["cy"] + dy * scale + (dy / length) * pad


def write_svg(payload: dict, path: str | Path) -> Path:
    path = Path(path)
    by_id = {n["id"]: n for n in payload["nodes"]}
    w, h = payload["viewBox"]["width"], payload["viewBox"]["height"]
    score, max_score = payload["score"], payload["max_score"]

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        '<rect width="100%" height="100%" fill="#0b0b0c"/>',
        f'<text x="16" y="28" fill="#f0f0f2" font-size="14" font-family="system-ui,sans-serif">'
        f'WC002  {score}/{max_score}  green=ok  red=fail</text>',
    ]
    for edge in payload["edges"]:
        a, b = by_id.get(edge["from"]), by_id.get(edge["to"])
        if not a or not b:
            continue
        x1, y1 = _border(a, b)
        x2, y2 = _border(b, a)
        lines.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{EDGE}" stroke-width="1.5"/>'
        )
    for n in payload["nodes"]:
        x, y = n["cx"] - n["w"] / 2, n["cy"] - n["h"] / 2
        dash = ' stroke-dasharray="4 4"' if n.get("isolated") else ""
        stroke = OK if n["passed"] else FAIL
        lines.append(
            f'<rect x="{x}" y="{y}" width="{n["w"]}" height="{n["h"]}" rx="8" '
            f'fill="#060607" stroke="{stroke}" stroke-width="2.5"{dash}/>'
        )
        lines.append(
            f'<text x="{n["cx"]}" y="{n["cy"] + 5}" text-anchor="middle" fill="#f0f0f2" '
            f'font-size="13" font-family="system-ui,sans-serif">{escape(n["label"])}</text>'
        )
    lines.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_graph(graph: ExtractedGraph, result: CheckResult, json_path: str | Path, svg_path: str | Path | None = None) -> dict:
    json_path = Path(json_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = graph_payload(graph, result)
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    out = {"graph": json_path.name}
    if svg_path is not None:
        write_svg(payload, svg_path)
        out["plot"] = Path(svg_path).name
    return out
