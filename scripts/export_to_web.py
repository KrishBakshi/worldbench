"""Project harness scores into worldbench-web.

Reads outputs/<slug>/validation.json (gitignored pipeline dump) and writes a
slim scores.json next to that model's world.html:

    worldbench-web/public/tests/<slug>/scores.json
    worldbench-web/public/tests/<slug>/graph.json   (WC002, no source evidence)

The site never reads outputs/. Evidence, probe transcripts, and harness
errors stay here.

Usage:
    uv run python scripts/export_to_web.py fable
    uv run python scripts/export_to_web.py --all
    uv run python scripts/export_to_web.py fable --web-root /path/to/worldbench-web
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from eval.loader import discover_tests  # noqa: E402
from harness.status import log  # noqa: E402

OUTPUTS_DIR = REPO_ROOT / "outputs"
DEFAULT_WEB_ROOT = REPO_ROOT.parent / "worldbench-web"


def _plain(text: str) -> str:
    text = text or ""
    text = text.replace(" \u2014 ", ", ").replace("\u2014", ",")
    text = text.replace(" \u2013 ", ", ").replace("\u2013", "-")
    return text.replace("\u2212", "-")


def _slim_row(row: dict, fallback: str = "") -> dict:
    label = _plain((row.get("label") or "").strip() or fallback or str(row.get("id") or ""))
    item = {"id": str(row.get("id") or ""), "label": label}
    if row.get("why"):
        item["why"] = str(row["why"])
    return item


def lost_items(scorecard: dict) -> list[dict]:
    """Public failure rows: labels only, no source evidence."""
    top = scorecard.get("lost")
    if isinstance(top, list) and top:
        return [_slim_row(row) for row in top]

    items: list[dict] = []
    biomes = scorecard.get("biomes") or {}
    if not isinstance(biomes, dict):
        return items
    for biome_id, card in biomes.items():
        if not isinstance(card, dict) or card.get("passed"):
            continue
        inner = card.get("lost") or []
        labeled = [row for row in inner if isinstance(row, dict) and row.get("label")]
        if labeled:
            for row in labeled:
                slim = _slim_row(row, fallback=f"{biome_id}: {row.get('id', '')}")
                slim["label"] = f"{biome_id}: {slim['label']}"
                items.append(slim)
            continue
        summary = (card.get("summary") or "").strip()
        row = {"id": str(biome_id), "label": f"{biome_id}: {summary}" if summary else str(biome_id)}
        if inner and isinstance(inner[0], dict) and inner[0].get("why"):
            row["why"] = str(inner[0]["why"])
        items.append(row)
    return items


def slim_graph(raw: dict) -> dict:
    """Public WC002 graph: layout + pass/fail, no source evidence."""
    nodes = []
    for node in raw.get("nodes") or []:
        if not isinstance(node, dict) or not node.get("id"):
            continue
        item = {
            "id": str(node["id"]),
            "label": str(node.get("label") or node["id"]),
            "passed": bool(node.get("passed")),
            "reason": str(node.get("reason") or ""),
            "cx": node.get("cx"),
            "cy": node.get("cy"),
            "w": node.get("w"),
            "h": node.get("h"),
        }
        if node.get("isolated"):
            item["isolated"] = True
        nodes.append(item)
    edges = []
    for edge in raw.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        src, dst = edge.get("from"), edge.get("to")
        if src and dst:
            edges.append({"from": str(src), "to": str(dst)})
    view = raw.get("viewBox") if isinstance(raw.get("viewBox"), dict) else {}
    return {
        "viewBox": {
            "width": view.get("width", 800),
            "height": view.get("height", 560),
        },
        "score": raw.get("score", 0),
        "max_score": raw.get("max_score", 10),
        "passed": bool(raw.get("passed")),
        "nodes": nodes,
        "edges": edges,
    }


def _wc002_graph_path(slug: str, ladder: list[dict]) -> Path | None:
    for meta in ladder:
        if meta.get("id") != "WC002":
            continue
        path = OUTPUTS_DIR / slug / meta["dir_name"] / "graph.json"
        return path if path.is_file() else None
    return None


def _check_record(validation: dict, dir_name: str) -> dict | None:
    prefix = f"{dir_name}::"
    for key, record in (validation.get("checks") or {}).items():
        if key.startswith(prefix) and isinstance(record, dict):
            return record
    return None


def project_validation(slug: str, validation: dict, ladder: list[dict]) -> dict:
    tests_out = []
    total_score = 0.0
    total_max = 0.0
    all_passed = True
    incomplete = False

    for meta in ladder:
        dir_name = meta["dir_name"]
        record = _check_record(validation, dir_name)
        details = (record or {}).get("details") or {}
        scorecard = details.get("scorecard") if isinstance(details, dict) else None
        max_score = float((record or {}).get("max_score") or 0)
        harness_error = isinstance(details, dict) and "error" in details
        scored = bool(record) and max_score > 0 and not harness_error

        row = {
            "id": meta["id"],
            "dir_name": dir_name,
            "title": meta["title"],
            "score": 0.0,
            "max_score": 0.0,
            "passed": False,
            "scored": scored,
            "reason": "",
            "lost": [],
        }
        if not record:
            row["reason"] = "Not scored in this run."
            incomplete = True
            all_passed = False
        elif not scored:
            row["reason"] = "Not scored in this run."
            incomplete = True
            all_passed = False
        else:
            score = float(record.get("score") or 0)
            row["score"] = score
            row["max_score"] = max_score
            row["passed"] = bool(record.get("passed"))
            row["reason"] = _plain(str(record.get("reason") or ""))
            lost = lost_items(scorecard) if isinstance(scorecard, dict) else []
            row["lost"] = lost
            total_score += score
            total_max += max_score
            all_passed = all_passed and row["passed"]

        tests_out.append(row)

    return {
        "slug": slug,
        "total_score": total_score,
        "total_max_score": total_max,
        "pct": (total_score / total_max) if total_max else 0.0,
        "passed": all_passed and not incomplete and total_max > 0,
        "incomplete": incomplete,
        "tests": tests_out,
    }


def export_slug(slug: str, web_root: Path, ladder: list[dict]) -> Path:
    src = OUTPUTS_DIR / slug / "validation.json"
    if not src.is_file():
        raise FileNotFoundError(f"No validation.json at {src}")

    dest_dir = web_root / "public" / "tests" / slug
    if not dest_dir.is_dir():
        raise FileNotFoundError(
            f"No worldbench-web test folder at {dest_dir}. "
            "The slug must match public/tests/<slug>."
        )

    validation = json.loads(src.read_text(encoding="utf-8"))
    payload = project_validation(slug, validation, ladder)
    dest = dest_dir / "scores.json"
    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    graph_src = _wc002_graph_path(slug, ladder)
    if graph_src:
        graph = slim_graph(json.loads(graph_src.read_text(encoding="utf-8")))
        (dest_dir / "graph.json").write_text(
            json.dumps(graph, indent=2) + "\n", encoding="utf-8"
        )

    return dest


def discover_output_slugs() -> list[str]:
    if not OUTPUTS_DIR.is_dir():
        return []
    slugs = []
    for path in sorted(OUTPUTS_DIR.iterdir()):
        if not path.is_dir() or path.name.startswith("."):
            continue
        if "__" in path.name:
            continue
        if (path / "validation.json").is_file():
            slugs.append(path.name)
    return slugs


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Export slim scores.json into worldbench-web")
    parser.add_argument("slug", nargs="?", help='model folder under outputs/ (e.g. "fable")')
    parser.add_argument("--all", action="store_true", help="export every outputs/<slug>/validation.json")
    parser.add_argument(
        "--web-root",
        type=Path,
        default=DEFAULT_WEB_ROOT,
        help="path to worldbench-web (default: sibling of this repo)",
    )
    args = parser.parse_args(argv)

    web_root = args.web_root.resolve()
    if not (web_root / "public" / "tests").is_dir():
        raise SystemExit(f"worldbench-web not found at {web_root}")

    ladder = discover_tests()
    slugs = discover_output_slugs() if args.all else ([args.slug] if args.slug else [])
    if not slugs:
        parser.error("pass a slug (fable) or --all")

    for slug in slugs:
        log(f"export  {slug}")
        dest = export_slug(slug, web_root, ladder)
        log(f"wrote   {dest}")
        print(dest, flush=True)


if __name__ == "__main__":
    main()
