"""Per-biome micro-contents: probe (LLM) → grade.

    uv run python tests/WC003_biome_micro_contents/main.py [world.html] [out_dir]
    uv run python tests/WC003_biome_micro_contents/main.py [world.html] [out_dir] --biome highlands
    uv run python tests/WC003_biome_micro_contents/main.py [world.html] [out_dir] --biome all
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from grade import grade_reports
from llm import BIOME_IDS, BiomeMicroReport, CheckResult
from probe import probe_all


def _dump_reports(reports: dict) -> dict:
    out = {}
    for biome_id, report in reports.items():
        if isinstance(report, BiomeMicroReport):
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
    micro_path = out_dir / "micro_contents.json"
    micro_path.write_text(json.dumps(_dump_reports(reports), indent=2), encoding="utf-8")
    score_path = out_dir / "score.json"
    score_path.write_text(json.dumps(result.details["scorecard"], indent=2), encoding="utf-8")
    return {"micro_contents": micro_path.name, "score": score_path.name}


def load_reports_from_json(path: Path) -> dict[str, BiomeMicroReport | dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    reports: dict[str, BiomeMicroReport | dict] = {}
    for biome_id, payload in raw.items():
        if isinstance(payload, dict) and "error" in payload:
            reports[biome_id] = payload
        else:
            reports[biome_id] = BiomeMicroReport.model_validate(payload)
    return reports


def check_biome_micro_contents(
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


def regrade_micro(
    micro_path: Path,
    out_dir: Path | None = None,
    biome_ids: tuple[str, ...] | None = None,
) -> CheckResult:
    selected = biome_ids or BIOME_IDS
    reports = load_reports_from_json(micro_path)
    result = grade_reports(reports, selected)
    dest = out_dir if out_dir is not None else micro_path.parent
    result.details["artifacts"] = write_artifacts(dest, reports, result)
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WC003 biome micro-contents check")
    parser.add_argument("world_html", nargs="?", help="path to world.html")
    parser.add_argument("out_dir", nargs="?", help="directory to write micro_contents.json and score.json")
    parser.add_argument(
        "--biome",
        default="all",
        help="one biome id, or 'all' (default) to run every biome",
    )
    parser.add_argument(
        "--regrade",
        metavar="MICRO_JSON",
        help="re-score an existing micro_contents.json without new LLM calls",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    try:
        selected = resolve_biomes(args.biome)
    except ValueError as exc:
        sys.exit(str(exc))

    if not args.regrade and not args.world_html:
        sys.exit("world_html required unless --regrade is used")

    if args.regrade:
        micro_path = Path(args.regrade)
        out_dir = micro_path.parent
        print(f"WC003  regrade  {micro_path}", file=sys.stderr, flush=True)
        result = regrade_micro(micro_path, out_dir, biome_ids=selected)
    else:
        if args.out_dir is not None:
            out_dir = Path(args.out_dir) / f"{Path(args.world_html).parent.name}__WC003_biome_micro_contents"
        else:
            out_dir = Path(args.world_html).parent

        _ROOT = Path(__file__).resolve().parents[2]
        if str(_ROOT) not in sys.path:
            sys.path.append(str(_ROOT))
        from harness.status import log

        log(f"WC003  {args.world_html}")
        log(f"biomes {', '.join(selected)}")
        result = check_biome_micro_contents(args.world_html, out_dir, biome_ids=selected)
    print(f"passed={result.passed} score={result.details['score']}/{result.details['max_score']}", flush=True)
    print(result.reason, flush=True)
    if result.details.get("missing"):
        print(result.details["missing"], flush=True)
    artifacts = result.details.get("artifacts", {})
    for name in ("micro_contents", "score"):
        if name in artifacts:
            print(f"{out_dir}/{artifacts[name]}", flush=True)
