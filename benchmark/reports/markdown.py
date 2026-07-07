"""Render a single run result as a Markdown report."""

from __future__ import annotations

from ..runner.runner import RunResult


def _bar(score: float, width: int = 20) -> str:
    filled = round(score / 100 * width)
    return "█" * filled + "░" * (width - filled)


def render_markdown(result: RunResult) -> str:
    """Return a human-readable Markdown report for ``result``."""
    lines: list[str] = []
    lines.append(f"# WorldBench Report — {result.task_id}")
    lines.append("")
    lines.append(f"- **Adapter:** {result.adapter}")
    lines.append(f"- **Model:** {result.model}")
    lines.append(f"- **Category:** {result.category}")
    lines.append(f"- **Timestamp:** {result.timestamp}")
    lines.append(f"- **Parsed:** {'yes' if result.parsed else 'no'}")
    lines.append(f"- **Validation passed:** {'yes' if result.validation.passed else 'no'} "
                 f"({result.validation.error_count()} errors, "
                 f"{result.validation.warning_count()} warnings)")
    lines.append("")
    lines.append(f"## Overall Score: {result.overall_score:.1f} / 100")
    lines.append("")
    lines.append(f"`{_bar(result.overall_score)}`")
    lines.append("")

    lines.append("## Metric Breakdown")
    lines.append("")
    lines.append("| Metric | Score | Weight | Detail |")
    lines.append("| --- | ---: | ---: | --- |")
    for m in result.score.metrics:
        lines.append(f"| {m.name} | {m.score:.1f} | {m.weight:.2f} | {m.detail} |")
    lines.append("")

    lines.append("## Validation Findings")
    lines.append("")
    findings = result.validation.all_findings
    if not findings:
        lines.append("_No findings — the world passed every validator cleanly._")
    else:
        lines.append("| Severity | Code | Entity | Message |")
        lines.append("| --- | --- | --- | --- |")
        for f in findings:
            lines.append(
                f"| {f.severity.value} | {f.code} | {f.entity_id or '—'} | {f.message} |"
            )
    lines.append("")
    return "\n".join(lines)
