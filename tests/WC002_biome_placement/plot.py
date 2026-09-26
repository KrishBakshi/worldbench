"""graph.json for the website + graph.svg for a local click-to-open preview.

Same node positions as worldbench-web/components/about/BiomeGraph.tsx.
Three node states: green = covered and placed right, red = covered but
misplaced, grey dashed = not covered (the biome is not built at all, so it is
shown absent rather than flattened into an ordinary fail).
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
UNCOVERED = "#5f6570"

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
    cards = result.details.get("scorecard", {}).get("biomes", {})
    covered = {bid: cards.get(bid, {}).get("covered", True) for bid in BIOME_LABELS}
    by_id = {n.id: n for n in graph.nodes}

    nodes = []
    seen = set()
    for bid, label in BIOME_LABELS.items():
        node = by_id.get(bid) if covered[bid] else None
        neighbors = [n for n in (node.neighbors if node else []) if covered.get(n)]
        for n in neighbors:
            seen.add(tuple(sorted((bid, n))))
        passed = bid in found
        state = "ok" if passed else ("fail" if covered[bid] else "not_covered")
        nodes.append({
            "id": bid,
            "label": label,
            "neighbors": neighbors,
            "evidence": node.evidence if node else "",
            "passed": passed,
            "covered": covered[bid],
            "state": state,
            "score": cards.get(bid, {}).get("score", 0),
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
        f'WC002  {score}/{max_score}  green=placed  red=misplaced  grey=not covered</text>',
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
        state = n.get("state", "ok" if n["passed"] else "fail")
        dash = ' stroke-dasharray="4 4"' if n.get("isolated") or state == "not_covered" else ""
        stroke = {"ok": OK, "fail": FAIL, "not_covered": UNCOVERED}[state]
        text_fill = "#f0f0f2" if state != "not_covered" else "#8a9099"
        lines.append(
            f'<rect x="{x}" y="{y}" width="{n["w"]}" height="{n["h"]}" rx="8" '
            f'fill="#060607" stroke="{stroke}" stroke-width="2.5"{dash}/>'
        )
        label_y = n["cy"] + (0 if state == "not_covered" else 5)
        lines.append(
            f'<text x="{n["cx"]}" y="{label_y}" text-anchor="middle" fill="{text_fill}" '
            f'font-size="13" font-family="system-ui,sans-serif">{escape(n["label"])}</text>'
        )
        if state == "not_covered":
            lines.append(
                f'<text x="{n["cx"]}" y="{n["cy"] + 15}" text-anchor="middle" fill="{UNCOVERED}" '
                f'font-size="10" font-family="system-ui,sans-serif">not covered</text>'
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
