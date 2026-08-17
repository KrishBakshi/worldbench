"""Global day/night and season cycles: probe (LLM) → grade.

    uv run python tests/WC005_day_night_seasons/main.py [world.html] [out_dir]
    uv run python tests/WC005_day_night_seasons/main.py --regrade path/to/cycle.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from grade import grade_report
from llm import CheckResult, CycleReport
from probe import probe_cycle


def write_artifacts(out_dir: Path, report: CycleReport | dict, result: CheckResult) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    if isinstance(report, CycleReport):
        payload = report.model_dump()
    else:
        payload = report
    cycle_path = out_dir / "cycle.json"
    cycle_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    score_path = out_dir / "score.json"
    score_path.write_text(json.dumps(result.details["scorecard"], indent=2), encoding="utf-8")
    return {"cycle": cycle_path.name, "score": score_path.name}


def check_day_night_seasons(
    html_path: str,
    out_dir: Path | None = None,
    model: str | None = None,
) -> CheckResult:
    report = probe_cycle(html_path, model)
    result = grade_report(report)
    dest = Path(out_dir) if out_dir is not None else Path(html_path).parent
    result.details["artifacts"] = write_artifacts(dest, report, result)
    return result


def regrade_cycle(cycle_path: Path, out_dir: Path | None = None) -> CheckResult:
    raw = json.loads(cycle_path.read_text(encoding="utf-8"))
    report = CycleReport.model_validate(raw) if "error" not in raw else raw
    result = grade_report(report)
    dest = out_dir if out_dir is not None else cycle_path.parent
    result.details["artifacts"] = write_artifacts(dest, report, result)
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WC005 day/night and seasons check")
    parser.add_argument("world_html", nargs="?", help="path to world.html")
    parser.add_argument("out_dir", nargs="?", help="directory to write cycle.json and score.json")
    parser.add_argument("--regrade", metavar="CYCLE_JSON", help="re-score an existing cycle.json")
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    if args.regrade:
        cycle_path = Path(args.regrade)
        out_dir = cycle_path.parent
        result = regrade_cycle(cycle_path, out_dir)
    else:
        if not args.world_html:
            sys.exit("world_html required unless --regrade is used")
        if args.out_dir is not None:
            out_dir = Path(args.out_dir) / f"{Path(args.world_html).parent.name}__WC005_day_night_seasons"
        else:
            out_dir = Path(args.world_html).parent
        result = check_day_night_seasons(args.world_html, out_dir)
    print(f"passed={result.passed} score={result.details['score']}/{result.details['max_score']}")
    print(result.reason)
    artifacts = result.details.get("artifacts", {})
    for name in ("cycle", "score"):
        if name in artifacts:
            print(f"{out_dir}/{artifacts[name]}")
