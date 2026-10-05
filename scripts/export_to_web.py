"""Project harness scores into worldbench-web: one compact file per model, one index.

Reads outputs/<slug>/ (gitignored pipeline dump) and writes only what the
site's score views draw:

    worldbench-web/public/tests/<slug>/results.json   per model (beside world.html)
    worldbench-web/public/leaderboard.json            every exported model's totals

Test display names live here, once (TEST_NAMES): the data keeps the WC ids as
keys and carries the name strings, so the site shows "Physics", never "WC004".
No evidence, quotes, probe transcripts or judge text leave this repo. Read-only
on outputs/, no model calls, deterministic.

Usage:
    uv run python scripts/export_to_web.py claude-fable-5-1
    uv run python scripts/export_to_web.py --all
    uv run python scripts/export_to_web.py --all --web-root /path/to/worldbench-web
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tests" / "WC002_biome_placement"))

from eval.loader import discover_tests  # noqa: E402
from grade import RULES  # noqa: E402  WC002's own placement rules
from harness.status import log  # noqa: E402

OUTPUTS_DIR = REPO_ROOT / "outputs"
DEFAULT_WEB_ROOT = REPO_ROOT.parent / "worldbench-web"
SCHEMA = 1

# The one place test ids get their human names. Keys stay the WC ids.
TEST_NAMES = {
    "WC001": {"name": "Voxel island", "short": "Voxel"},
    "WC002": {"name": "Coverage and placement", "short": "Placement"},
    "WC003": {"name": "Micro-contents", "short": "Contents"},
    "WC004": {"name": "Physics", "short": "Physics"},
    "WC005": {"name": "Temporal cycles", "short": "Cycles"},
}
BIOMES = ["mountains", "forest", "highlands", "jungle", "swamp",
          "grove", "grassland", "delta", "desert", "volcano"]


def _r(x: float) -> float:
    return round(float(x), 2)


def test_scores(validation: dict, ladder: list[dict]) -> list[dict]:
    """Earned / max per test, summing a test's checks (WC001 has two)."""
    rows = []
    for meta in ladder:
        score = maxs = 0.0
        scored = False
        for key, rec in (validation.get("checks") or {}).items():
            if not key.startswith(f"{meta['dir_name']}::") or not isinstance(rec, dict):
                continue
            d = rec.get("details") or {}
            if not isinstance(d, dict) or "error" in d or not d.get("max_score"):
                continue
            score += float(d.get("score") or 0)
            maxs += float(d["max_score"])
            scored = True
        names = TEST_NAMES.get(meta["id"], {"name": meta["title"], "short": meta["title"]})
        rows.append({"id": meta["id"], **names, "score": _r(score), "max": _r(maxs), "scored": scored})
    return rows


def biome_scores(slug: str, dir_name: str) -> list[float] | None:
    """Per-biome score (/10) in BIOMES order, or None if the test wasn't run."""
    path = OUTPUTS_DIR / slug / dir_name / "score.json"
    if not path.is_file():
        return None
    biomes = json.loads(path.read_text(encoding="utf-8")).get("biomes") or {}
    # capped at the biome max: item points are rounded before summing (10.02/10)
    return [_r(min(10.0, (biomes.get(b) or {}).get("score") or 0)) for b in BIOMES]


def placement(slug: str, dir_name: str) -> dict | None:
    """WC002 graph, rule-relevant only: node verdicts and the links the rules
    speak about (required present/missing, forbidden present). Positions and
    labels are the site's own layout, so none are sent."""
    path = OUTPUTS_DIR / slug / dir_name / "graph.json"
    if not path.is_file():
        return None
    g = json.loads(path.read_text(encoding="utf-8"))
    have = {tuple(sorted((e["from"], e["to"]))) for e in g.get("edges") or [] if isinstance(e, dict)}
    links = []
    for b, rule in RULES.items():
        for o in rule.get("must_connect", []) + rule.get("must_connect_any", []):
            pair = tuple(sorted((b, o)))
            links.append({"from": pair[0], "to": pair[1], "kind": "required" if pair in have else "missing"})
        for o in rule.get("must_not_connect", []):
            pair = tuple(sorted((b, o)))
            if pair in have:
                links.append({"from": pair[0], "to": pair[1], "kind": "forbidden"})
    seen, uniq = set(), []
    for link in links:  # a pair named by both of its biomes' rules appears once
        k = (link["from"], link["to"])
        if k not in seen:
            seen.add(k)
            uniq.append(link)
    nodes = []
    for n in g.get("nodes") or []:
        raw = n.get("state") or ("ok" if n.get("passed") else "fail")
        # the site's three states; the grader writes "not_covered"
        item = {"id": n["id"], "state": {"not_covered": "uncovered"}.get(raw, raw)}
        if item["state"] not in ("ok", "fail", "uncovered"):
            item["state"] = "fail"
        # link failures are already drawn as forbidden/missing links; only a
        # height failure needs words
        if item["state"] == "fail" and "elevation" in (n.get("reason") or ""):
            item["reason"] = n["reason"]
        nodes.append(item)
    return {"nodes": nodes, "links": uniq, "heightOrder": g.get("elevation_order") or []}


def build(slug: str, ladder: list[dict]) -> dict:
    validation = json.loads((OUTPUTS_DIR / slug / "validation.json").read_text(encoding="utf-8"))
    tests = test_scores(validation, ladder)
    dirs = {m["id"]: m["dir_name"] for m in ladder}
    out = {
        "schema": SCHEMA,
        "slug": slug,
        "total": {"score": _r(sum(t["score"] for t in tests)), "max": _r(sum(t["max"] for t in tests))},
        "complete": all(t["scored"] for t in tests),
        "tests": tests,
    }
    contents = biome_scores(slug, dirs["WC003"])
    physics = biome_scores(slug, dirs["WC004"])
    if contents or physics:
        out["biomes"] = {"ids": BIOMES, "WC003": contents, "WC004": physics}
    graph = placement(slug, dirs["WC002"])
    if graph:
        out["placement"] = graph
    return out


def discover_output_slugs() -> list[str]:
    if not OUTPUTS_DIR.is_dir():
        return []
    return [p.name for p in sorted(OUTPUTS_DIR.iterdir())
            if p.is_dir() and not p.name.startswith(".") and "__" not in p.name
            and (p / "validation.json").is_file()]


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Export compact results into worldbench-web")
    parser.add_argument("slugs", nargs="*", help="model folders under outputs/ (e.g. claude-fable-5-1)")
    parser.add_argument("--all", action="store_true", help="export every graded model")
    parser.add_argument("--web-root", type=Path, default=DEFAULT_WEB_ROOT,
                        help="path to worldbench-web (default: sibling of this repo)")
    args = parser.parse_args(argv)

    web_root = args.web_root.resolve()
    tests_dir = web_root / "public" / "tests"
    if not tests_dir.is_dir():
        raise SystemExit(f"worldbench-web not found at {web_root}")
    slugs = discover_output_slugs() if args.all else args.slugs
    if not slugs:
        parser.error("pass one or more slugs, or --all")

    ladder = discover_tests()
    for slug in slugs:
        if not (tests_dir / slug).is_dir():
            log(f"skip    {slug}: no public/tests/{slug} folder on the site")
            continue
        data = build(slug, ladder)
        dest = tests_dir / slug / "results.json"
        write_json(dest, data)
        log(f"wrote   {dest.relative_to(web_root)}  ({dest.stat().st_size} B)")

    # The index covers every model that has a results.json on the site, so
    # exporting one model never drops the others from the leaderboard.
    rows, maxima = [], {}
    for path in sorted(tests_dir.glob("*/results.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        for t in d["tests"]:
            if t["scored"]:
                maxima[t["id"]] = t["max"]
        rows.append({
            "slug": d["slug"], "total": d["total"]["score"], "max": d["total"]["max"],
            "complete": d.get("complete", True),
            "tests": {t["id"]: t["score"] for t in d["tests"]},
        })
    rows.sort(key=lambda r: -r["total"])
    index = {"schema": SCHEMA,
             "tests": [{"id": k, **v, "max": maxima.get(k, 0)} for k, v in TEST_NAMES.items()],
             "models": rows}
    write_json(web_root / "public" / "leaderboard.json", index)
    log(f"wrote   public/leaderboard.json  ({len(rows)} models)")


if __name__ == "__main__":
    main()
