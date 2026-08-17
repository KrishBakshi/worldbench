"""Per-biome entity rendering: probe (LLM) → grade.

    uv run python tests/WC004_biome_rendering/main.py [world.html] [out_dir]
    uv run python tests/WC004_biome_rendering/main.py [world.html] [out_dir] --biome desert
    uv run python tests/WC004_biome_rendering/main.py --regrade path/to/rendering.json [--biome desert]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from grade import grade_reports
from llm import BIOME_IDS, BiomeRenderReport, CheckResult
from probe import probe_all


def _dump_reports(reports: dict) -> dict:
    out = {}
    for biome_id, report in reports.items():
        if isinstance(report, BiomeRenderReport):
            out[biome_id] = report.model_dump()
        else:
            out[biome_id] = report
    return out


def resolve_biomes(biome: str | None) -> tuple[str, ...]:
    if biome is None or biome == "all":
        return BIOME_IDS
    if biome not in BIOME_IDS:
        allowed = ", ".join(("all",) + BIOME_IDS)
        raise ValueError(f"unknown biome {biome!r}; choose one of: {allowed}")
    return (biome,)


def write_artifacts(out_dir: Path, reports: dict, result: CheckResult) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    render_path = out_dir / "rendering.json"
    render_path.write_text(json.dumps(_dump_reports(reports), indent=2), encoding="utf-8")
    score_path = out_dir / "score.json"
    score_path.write_text(json.dumps(result.details["scorecard"], indent=2), encoding="utf-8")
    return {"rendering": render_path.name, "score": score_path.name}


def load_reports_from_json(path: Path) -> dict[str, BiomeRenderReport | dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    reports: dict[str, BiomeRenderReport | dict] = {}
    for biome_id, payload in raw.items():
        if isinstance(payload, dict) and "error" in payload:
            reports[biome_id] = payload
        else:
            reports[biome_id] = BiomeRenderReport.model_validate(payload)
    return reports


def check_biome_rendering(
    html_path: str,
    out_dir: Path | None = None,
    model: str | None = None,
    biome_ids: tuple[str, ...] | None = None,
) -> CheckResult:
    selected = biome_ids or BIOME_IDS
    reports = probe_all(html_path, model, selected)
    result = grade_reports(reports, selected)
    dest = Path(out_dir) if out_dir is not None else Path(html_path).parent
    result.details["artifacts"] = write_artifacts(dest, reports, result)
    return result


def regrade_rendering(
    rendering_path: Path,
    out_dir: Path | None = None,
    biome_ids: tuple[str, ...] | None = None,
) -> CheckResult:
    selected = biome_ids or BIOME_IDS
    reports = load_reports_from_json(rendering_path)
    result = grade_reports(reports, selected)
    dest = out_dir if out_dir is not None else rendering_path.parent
    result.details["artifacts"] = write_artifacts(dest, reports, result)
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WC004 biome entity rendering check")
    parser.add_argument("world_html", nargs="?", help="path to world.html")
    parser.add_argument("out_dir", nargs="?", help="directory to write rendering.json and score.json")
    parser.add_argument(
        "--biome",
        default="all",
        help="one biome id, or 'all' (default) to run every biome",
    )
    parser.add_argument(
        "--regrade",
        metavar="RENDERING_JSON",
        help="re-score an existing rendering.json without new LLM calls",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    try:
        selected = resolve_biomes(args.biome)
    except ValueError as exc:
        sys.exit(str(exc))

    if args.regrade:
        rendering_path = Path(args.regrade)
        out_dir = rendering_path.parent
        result = regrade_rendering(rendering_path, out_dir, biome_ids=selected)
    else:
        if not args.world_html:
            sys.exit("world_html required unless --regrade is used")
        if args.out_dir is not None:
            out_dir = Path(args.out_dir) / f"{Path(args.world_html).parent.name}__WC004_biome_rendering"
        else:
            out_dir = Path(args.world_html).parent
        result = check_biome_rendering(args.world_html, out_dir, biome_ids=selected)
    print(f"passed={result.passed} score={result.details['score']}/{result.details['max_score']}")
    print(result.reason)
    if result.details.get("missing"):
        print(result.details["missing"])
    artifacts = result.details.get("artifacts", {})
    for name in ("rendering", "score"):
        if name in artifacts:
            print(f"{out_dir}/{artifacts[name]}")
