"""Aggregate run outputs into a leaderboard across models and categories.

The leaderboard walks the ``outputs/`` tree, reads each run's ``report.json``,
and produces per-model averages plus a per-category breakdown. It renders to
Markdown, JSON, and HTML so results can be dropped into docs, CI summaries, or a
static site.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean

from ..runner.runner import OUTPUTS_DIR


@dataclass
class ModelStanding:
    """Aggregated results for one model across all its runs."""

    model_dir: str
    adapter: str
    model: str
    runs: int = 0
    overall_scores: list[float] = field(default_factory=list)
    category_scores: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    pass_count: int = 0

    @property
    def average(self) -> float:
        return mean(self.overall_scores) if self.overall_scores else 0.0

    @property
    def pass_rate(self) -> float:
        return self.pass_count / self.runs if self.runs else 0.0

    def category_average(self, category: str) -> float:
        scores = self.category_scores.get(category, [])
        return mean(scores) if scores else 0.0


def collect_standings(outputs_dir: str | Path | None = None) -> list[ModelStanding]:
    """Scan ``outputs_dir`` and build a sorted list of model standings."""
    root = Path(outputs_dir) if outputs_dir else OUTPUTS_DIR
    standings: dict[str, ModelStanding] = {}
    if not root.exists():
        return []

    for report_path in sorted(root.glob("*/*/report.json")):
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        model_dir = report_path.parent.parent.name
        standing = standings.get(model_dir)
        if standing is None:
            standing = ModelStanding(
                model_dir=model_dir,
                adapter=data.get("adapter", "unknown"),
                model=data.get("model", model_dir),
            )
            standings[model_dir] = standing
        standing.runs += 1
        score = float(data.get("overall_score", 0.0))
        standing.overall_scores.append(score)
        standing.category_scores[data.get("category", "unknown")].append(score)
        if data.get("passed_validation"):
            standing.pass_count += 1

    return sorted(standings.values(), key=lambda s: s.average, reverse=True)


def all_categories(standings: list[ModelStanding]) -> list[str]:
    cats: set[str] = set()
    for s in standings:
        cats.update(s.category_scores)
    return sorted(cats)


def render_leaderboard_markdown(standings: list[ModelStanding]) -> str:
    """Render the leaderboard as Markdown (overall + per-category tables)."""
    if not standings:
        return "# WorldBench Leaderboard\n\n_No runs found under outputs/._\n"

    lines = ["# WorldBench Leaderboard", ""]
    lines.append("| Rank | Model | Adapter | Runs | Avg Score | Pass Rate |")
    lines.append("| ---: | --- | --- | ---: | ---: | ---: |")
    for i, s in enumerate(standings, start=1):
        lines.append(
            f"| {i} | {s.model} | {s.adapter} | {s.runs} | "
            f"{s.average:.1f} | {s.pass_rate * 100:.0f}% |"
        )
    lines.append("")

    categories = all_categories(standings)
    if categories:
        lines.append("## Per-Category Breakdown")
        lines.append("")
        header = "| Model | " + " | ".join(categories) + " |"
        sep = "| --- | " + " | ".join("---:" for _ in categories) + " |"
        lines.append(header)
        lines.append(sep)
        for s in standings:
            cells = " | ".join(f"{s.category_average(c):.1f}" for c in categories)
            lines.append(f"| {s.model} | {cells} |")
        lines.append("")
    return "\n".join(lines)


def build_leaderboard_json(standings: list[ModelStanding]) -> dict:
    """Return a JSON-serializable leaderboard document."""
    categories = all_categories(standings)
    return {
        "categories": categories,
        "standings": [
            {
                "rank": i,
                "model": s.model,
                "adapter": s.adapter,
                "runs": s.runs,
                "average": round(s.average, 2),
                "pass_rate": round(s.pass_rate, 4),
                "category_averages": {c: round(s.category_average(c), 2) for c in categories},
            }
            for i, s in enumerate(standings, start=1)
        ],
    }


def render_leaderboard_html(standings: list[ModelStanding]) -> str:
    """Render the leaderboard as a minimal self-contained HTML page."""
    rows = "\n".join(
        f"<tr><td class='num'>{i}</td><td>{s.model}</td><td>{s.adapter}</td>"
        f"<td class='num'>{s.runs}</td><td class='num'>{s.average:.1f}</td>"
        f"<td class='num'>{s.pass_rate * 100:.0f}%</td></tr>"
        for i, s in enumerate(standings, start=1)
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WorldBench Leaderboard</title>
<style>
:root {{ color-scheme: light dark; }}
body {{ font-family: system-ui, sans-serif; max-width: 760px; margin: 2rem auto;
        padding: 0 1rem; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ padding: .5rem .6rem; border-bottom: 1px solid #ccc; text-align: left; }}
td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
</style></head><body>
<h1>WorldBench Leaderboard</h1>
<table><thead><tr><th class="num">#</th><th>Model</th><th>Adapter</th>
<th class="num">Runs</th><th class="num">Avg</th><th class="num">Pass</th></tr></thead>
<tbody>{rows}</tbody></table>
</body></html>
"""
