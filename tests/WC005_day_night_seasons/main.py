"""Global day/night and season cycles: code probe (LLM) + pinned-time frames (VLM) → grade.

20 points, 2 per item, split between code and what the frames show when the
world's clock is pinned to day / night / each season (see visual.py).

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
from probe import probe_cycle, strip_html
from visual import judge_cycle

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))
from eval.evidence import normalize  # noqa: E402


def write_artifacts(out_dir: Path, report: CycleReport | dict, result: CheckResult, visual: dict | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    if isinstance(report, CycleReport):
        payload = report.model_dump()
    else:
        payload = report
    cycle_path = out_dir / "cycle.json"
    cycle_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    score_path = out_dir / "score.json"
    score_path.write_text(json.dumps(result.details["scorecard"], indent=2), encoding="utf-8")
    out = {"cycle": cycle_path.name, "score": score_path.name}
    if visual is not None:
        (out_dir / "visual.json").write_text(json.dumps(visual, indent=2), encoding="utf-8")
        out["visual"] = "visual.json"
    return out


def check_day_night_seasons(
    html_path: str,
    out_dir: Path | None = None,
    model: str | None = None,
) -> CheckResult:
    report = probe_cycle(html_path, model)
    visual = judge_cycle(html_path, model)
    result = grade_report(report, visual, normalize(strip_html(html_path)))
    dest = Path(out_dir) if out_dir is not None else Path(html_path).parent
    result.details["artifacts"] = write_artifacts(dest, report, result, visual)
    return result


def regrade_cycle(cycle_path: Path, out_dir: Path | None = None) -> CheckResult:
    raw = json.loads(cycle_path.read_text(encoding="utf-8"))
    report = CycleReport.model_validate(raw) if "error" not in raw else raw
    visual_path = cycle_path.parent / "visual.json"
    visual = json.loads(visual_path.read_text(encoding="utf-8")) if visual_path.is_file() else None
    world = cycle_path.parent.parent / "world.html"
    source = normalize(strip_html(str(world))) if world.is_file() else None
    result = grade_report(report, visual, source)
    dest = out_dir if out_dir is not None else cycle_path.parent
    result.details["artifacts"] = write_artifacts(dest, report, result, visual)
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
        print(f"WC005  regrade  {cycle_path}", file=sys.stderr, flush=True)
        result = regrade_cycle(cycle_path, out_dir)
    else:
        if not args.world_html:
            sys.exit("world_html required unless --regrade is used")
        if args.out_dir is not None:
            out_dir = Path(args.out_dir) / f"{Path(args.world_html).parent.name}__WC005_day_night_seasons"
        else:
            out_dir = Path(args.world_html).parent
        result = check_day_night_seasons(args.world_html, out_dir)
    print(f"passed={result.passed} score={result.details['score']}/{result.details['max_score']}", flush=True)
    print(result.reason, flush=True)
    artifacts = result.details.get("artifacts", {})
    for name in ("cycle", "score"):
        if name in artifacts:
            print(f"{out_dir}/{artifacts[name]}", flush=True)
