"""Write the README diagrams. Same dark node style as WC002 plot.py.

    uv run python scripts/write_readme_graphs.py
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

REPO = Path(__file__).resolve().parent.parent

OK = "#2ecc71"
EDGE = "#95a5a6"
BG = "#0b0b0c"
FG = "#f0f0f2"
BOX = "#060607"
ALT = "#5dade2"
DRY = "#c9a227"
MUTED = "#95a5a6"

BIOME_LABELS = {
    "mountains": "Snow Mountains",
    "forest": "Snowy Conifer Forest",
    "highlands": "Highlands",
    "jungle": "Dense Jungle",
    "swamp": "Backwater Swamp",
    "grove": "Flowering Grove",
    "grassland": "Grassland Plateau",
    "delta": "Coastal Delta / Ocean",
    "desert": "Desert Basin",
    "volcano": "Volcano",
}

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


def _border(a: dict, b: dict, pad: float = 4) -> tuple[float, float]:
    dx, dy = b["cx"] - a["cx"], b["cy"] - a["cy"]
    hw, hh = a["w"] / 2, a["h"] / 2
    sx = float("inf") if abs(dx) < 1e-6 else hw / abs(dx)
    sy = float("inf") if abs(dy) < 1e-6 else hh / abs(dy)
    scale = min(sx, sy)
    length = (dx * dx + dy * dy) ** 0.5 or 1
    return a["cx"] + dx * scale + (dx / length) * pad, a["cy"] + dy * scale + (dy / length) * pad


def _svg(w: int, h: int, body: list[str]) -> str:
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        f'<rect width="100%" height="100%" fill="{BG}"/>',
        *[line for line in body if line],
        "</svg>",
        "",
    ]
    return "\n".join(lines)


def _text(x: float, y: float, label: str, *, size: int = 13, anchor: str = "middle", fill: str = FG) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" fill="{fill}" '
        f'font-size="{size}" font-family="system-ui,sans-serif">{escape(label)}</text>'
    )


def _rect(x: float, y: float, w: float, h: float, stroke: str, *, dashed: bool = False, rx: int = 8) -> str:
    dash = ' stroke-dasharray="4 4"' if dashed else ""
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" '
        f'fill="{BOX}" stroke="{stroke}" stroke-width="2.5"{dash}/>'
    )


def _line(x1: float, y1: float, x2: float, y2: float, stroke: str = EDGE, *, dashed: bool = False, width: float = 1.5) -> str:
    dash = ' stroke-dasharray="5 4"' if dashed else ""
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{stroke}" stroke-width="{width}"{dash}/>'
    )


def _write(path: Path, svg: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg, encoding="utf-8")
    print(path)


def _node_box(n: dict, stroke: str) -> list[str]:
    x, y = n["cx"] - n["w"] / 2, n["cy"] - n["h"] / 2
    return [
        _rect(x, y, n["w"], n["h"], stroke, dashed=bool(n.get("isolated"))),
        _text(n["cx"], n["cy"] + 5, n["label"]),
    ]


def biome_nodes() -> dict[str, dict]:
    out = {}
    for bid, label in BIOME_LABELS.items():
        out[bid] = {"id": bid, "label": label, **LAYOUT[bid]}
    return out


def write_wc002(path: Path) -> None:
    """Expected wet corridor. Same layout the grader and the website use."""
    by_id = biome_nodes()
    w, h = VIEWBOX["width"], VIEWBOX["height"]
    edges = [
        ("mountains", "forest", EDGE, False),
        ("forest", "highlands", EDGE, False),
        ("highlands", "jungle", EDGE, False),
        ("jungle", "grassland", EDGE, False),
        ("grassland", "delta", EDGE, False),
        ("jungle", "swamp", EDGE, False),
        ("highlands", "grove", ALT, True),
        ("grassland", "grove", ALT, True),
        ("grassland", "desert", DRY, True),
    ]
    body = [_text(16, 28, "WC002  expected placement  solid=wet corridor  dashed=and/or or dry", size=14, anchor="start")]
    for src, dst, color, dashed in edges:
        a, b = by_id[src], by_id[dst]
        x1, y1 = _border(a, b)
        x2, y2 = _border(b, a)
        body.append(_line(x1, y1, x2, y2, color, dashed=dashed))
    for n in by_id.values():
        body.extend(_node_box(n, OK))
    _write(path, _svg(w, h, body))


def write_wc001(path: Path) -> None:
    by_id = biome_nodes()
    w, h = VIEWBOX["width"], VIEWBOX["height"]
    body = [_text(16, 28, "WC001  ten biomes must appear in executable JS, not a legend", size=14, anchor="start")]
    for n in by_id.values():
        body.extend(_node_box(n, OK))
    _write(path, _svg(w, h, body))


def write_wc000(path: Path) -> None:
    w, h = 800, 520
    lattice = [
        ("cube_primitive", "Cube primitive", 2),
        ("bulk_placement", "Bulk placement", 2),
        ("discrete_grid", "Discrete grid", 2),
        ("stacked_columns", "Stacked columns", 2),
        ("cube_terrain", "Cube terrain", 2),
        ("grid_aligned", "Grid aligned", 2),
        ("unit_voxels", "Unit voxels", 2),
    ]
    physics = [
        ("contained_water", "Water exists", 4),
        ("water_physics", "Held or falling", 6),
        ("water_bed", "Seafloor under still water", 10),
        ("grounded_props", "Props on the land", 4),
    ]
    body = [_text(16, 28, "WC000  lattice is 2 pts each. Island physics carries the score.", size=14, anchor="start")]
    body.append(_text(200, 64, "Lattice  14", size=13, fill=MUTED))
    body.append(_text(600, 64, "Island physics  24", size=13, fill=MUTED))
    for i, (_id, label, pts) in enumerate(lattice):
        y = 88 + i * 54
        body.append(_rect(40, y, 320, 44, EDGE))
        body.append(_text(200, y + 28, f"{label}  {pts}", size=13))
    for i, (_id, label, pts) in enumerate(physics):
        y = 88 + i * 78
        stroke = OK if _id != "water_bed" else "#f1c40f"
        body.append(_rect(440, y, 320, 62, stroke))
        body.append(_text(600, y + 38, f"{label}  {pts}", size=13))
    body.append(_text(400, 500, "Missing seafloor drops Coastal Delta / Ocean points on WC003 and WC004.", size=12, fill=MUTED))
    # connector from lattice column to physics
    body.append(_line(360, 250, 440, 250, EDGE))
    _write(path, _svg(w, h, body))


def write_probe_flow(path: Path, title: str, grade_label: str) -> None:
    """Shared WC003/WC004 pipeline: one world, ten biome probes, then grade."""
    w, h = 800, 640
    by_id = biome_nodes()
    body = [_text(16, 28, title, size=14, anchor="start")]
    steps = [
        (90, 70, 140, 44, "world.html"),
        (310, 70, 160, 44, "LLM probe / biome"),
        (540, 70, 140, 44, grade_label),
        (710, 70, 70, 44, "score"),
    ]
    for x, y, bw, bh, label in steps:
        body.append(_rect(x - bw / 2, y - bh / 2, bw, bh, ALT))
        body.append(_text(x, y + 5, label, size=12))
    body.append(_line(160, 70, 230, 70, EDGE, width=1.8))
    body.append(_line(390, 70, 470, 70, EDGE, width=1.8))
    body.append(_line(610, 70, 675, 70, EDGE, width=1.8))
    for n in by_id.values():
        shifted = {**n, "cy": n["cy"] + 80}
        body.extend(_node_box(shifted, OK))
    _write(path, _svg(w, h, body))


def write_wc005(path: Path) -> None:
    w, h = 800, 420
    body = [_text(16, 28, "WC005  one clock drives day and year. HUD text is not enough.", size=14, anchor="start")]
    for x, label in ((200, "day clock"), (600, "year clock")):
        body.append(_rect(x - 90, 66, 180, 48, ALT))
        body.append(_text(x, 95, label))
    body.append(_line(290, 90, 510, 90, EDGE, dashed=True))

    day = [
        (120, 180, "Sun orbit"),
        (120, 250, "Night dimming"),
        (120, 320, "Dusk / dawn tint"),
        (340, 180, "Light follows sun"),
        (340, 250, "Sky or fog"),
        (340, 320, "Cloud wrap"),
        (340, 380, "Moon"),
    ]
    year = [
        (600, 180, "Season cycle"),
        (600, 250, "World tint"),
        (600, 320, "Weather scale"),
    ]
    for x, y, label in day:
        body.append(_rect(x - 90, y - 22, 180, 44, OK))
        body.append(_text(x, y + 5, label, size=12))
        body.append(_line(200, 114, x, y - 22, EDGE))
    for x, y, label in year:
        body.append(_rect(x - 90, y - 22, 180, 44, "#f1c40f"))
        body.append(_text(x, y + 5, label, size=12))
        body.append(_line(600, 114, x, y - 22, EDGE))
    _write(path, _svg(w, h, body))


def write_ladder(path: Path) -> None:
    w, h = 800, 520
    rows = [
        ("WC000", "Voxel lattice", "38", "Cubes, then a mass in a void"),
        ("WC001", "Biome coverage", "10", "All ten biomes exist in JS"),
        ("WC002", "Placement graph", "10", "Neighbors and elevation"),
        ("WC003", "Micro-contents", "100", "What each biome is made of"),
        ("WC004", "Physics", "100", "How entities look and move"),
        ("WC005", "Temporal cycles", "10", "Day clock and seasons"),
    ]
    body = [_text(16, 28, "Ladder  268 pts  WC000 seafloor gates ocean points on WC003 and WC004", size=14, anchor="start")]
    for i, (wid, title, pts, note) in enumerate(rows):
        y = 56 + i * 74
        body.append(_rect(40, y, 720, 58, OK if i else "#f1c40f"))
        body.append(_text(64, y + 36, f"{wid}  {title}", size=15, anchor="start"))
        body.append(_text(520, y + 36, note, size=12, anchor="start", fill="#95a5a6"))
        body.append(_text(736, y + 36, pts, size=15, anchor="end"))
        if i:
            body.append(_line(80, y - 16, 80, y, EDGE))
    _write(path, _svg(w, h, body))


def main() -> None:
    tests = REPO / "tests"
    write_ladder(REPO / "docs" / "ladder.svg")
    write_wc000(tests / "WC000_voxel_world" / "graph.svg")
    write_wc001(tests / "WC001_trying_all_the_biomes" / "graph.svg")
    write_wc002(tests / "WC002_biome_placement" / "graph.svg")
    write_probe_flow(
        tests / "WC003_biome_micro_contents" / "graph.svg",
        "WC003  ten biome probes, then grade presence. Delta is dropped if WC000 has no seafloor.",
        "grade items",
    )
    write_probe_flow(
        tests / "WC004_biome_rendering" / "graph.svg",
        "WC004  ten biome probes, then grade look and motion. Delta is dropped if WC000 has no seafloor.",
        "grade look/move",
    )
    write_wc005(tests / "WC005_day_night_seasons" / "graph.svg")


if __name__ == "__main__":
    main()
