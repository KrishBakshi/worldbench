"""Render a run result as a self-contained HTML report.

The HTML is intentionally dependency-free (inline CSS, no external assets) so a
report can be opened directly from disk or served statically. Theme-aware light
and dark styling is included.
"""

from __future__ import annotations

import html

from ..runner.runner import RunResult

_CSS = """
:root { color-scheme: light dark; }
body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
       margin: 0 auto; max-width: 880px; padding: 2rem 1.25rem; line-height: 1.5;
       background: #ffffff; color: #16181d; }
@media (prefers-color-scheme: dark) {
  body { background: #14161a; color: #e7e9ee; }
  .card { background: #1d2027 !important; border-color: #2c313b !important; }
  th { background: #21252e !important; }
  code { background: #21252e !important; }
}
h1 { font-size: 1.6rem; margin-bottom: .25rem; }
.sub { color: #7a828e; margin-top: 0; }
.card { border: 1px solid #e3e6ea; border-radius: 12px; padding: 1rem 1.25rem;
        margin: 1rem 0; background: #f7f8fa; }
.score { font-size: 2.4rem; font-weight: 700; }
.meter { height: 12px; border-radius: 6px; background: #d7dbe0; overflow: hidden; }
.meter > span { display: block; height: 100%;
                background: linear-gradient(90deg,#e5534b,#e0a63c,#3fa45b); }
table { border-collapse: collapse; width: 100%; margin: .5rem 0; }
th, td { text-align: left; padding: .5rem .6rem; border-bottom: 1px solid #e3e6ea; }
th { background: #eef1f4; }
td.num { text-align: right; font-variant-numeric: tabular-nums; }
.pill { display: inline-block; padding: .1rem .5rem; border-radius: 999px; font-size: .8rem; }
.pass { background: #d7f0dd; color: #1a7f37; }
.fail { background: #fbdcd9; color: #b42318; }
.sev-error { color: #b42318; font-weight: 600; }
.sev-warning { color: #b7791f; }
.sev-info { color: #6b7280; }
code { background: #eef1f4; padding: .05rem .3rem; border-radius: 4px; }
"""


def _esc(text: str) -> str:
    return html.escape(str(text))


def render_html(result: RunResult) -> str:
    """Return a complete HTML document for ``result``."""
    pass_cls = "pass" if result.validation.passed else "fail"
    pass_txt = "PASSED" if result.validation.passed else "FAILED"
    pct = max(0.0, min(100.0, result.overall_score))

    metric_rows = "\n".join(
        f"<tr><td>{_esc(m.name)}</td><td class='num'>{m.score:.1f}</td>"
        f"<td class='num'>{m.weight:.2f}</td><td>{_esc(m.detail)}</td></tr>"
        for m in result.score.metrics
    )

    findings = result.validation.all_findings
    if findings:
        finding_rows = "\n".join(
            f"<tr><td class='sev-{f.severity.value}'>{_esc(f.severity.value)}</td>"
            f"<td><code>{_esc(f.code)}</code></td><td>{_esc(f.entity_id or '—')}</td>"
            f"<td>{_esc(f.message)}</td></tr>"
            for f in findings
        )
        findings_table = (
            "<table><thead><tr><th>Severity</th><th>Code</th><th>Entity</th>"
            f"<th>Message</th></tr></thead><tbody>{finding_rows}</tbody></table>"
        )
    else:
        findings_table = "<p><em>No findings — the world passed every validator cleanly.</em></p>"

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WorldBench Report — {_esc(result.task_id)}</title>
<style>{_CSS}</style></head><body>
<h1>WorldBench Report</h1>
<p class="sub">{_esc(result.task_id)} · {_esc(result.adapter)} / {_esc(result.model)}</p>
<div class="card">
  <div class="score">{result.overall_score:.1f} <span style="font-size:1rem;color:#7a828e">/ 100</span></div>
  <div class="meter"><span style="width:{pct:.1f}%"></span></div>
  <p style="margin:.75rem 0 0">
    Validation: <span class="pill {pass_cls}">{pass_txt}</span>
    &nbsp;{result.validation.error_count()} errors ·
    {result.validation.warning_count()} warnings ·
    parsed: {"yes" if result.parsed else "no"}
  </p>
</div>
<div class="card">
  <h2>Metric Breakdown</h2>
  <table><thead><tr><th>Metric</th><th>Score</th><th>Weight</th><th>Detail</th></tr></thead>
  <tbody>{metric_rows}</tbody></table>
</div>
<div class="card">
  <h2>Validation Findings</h2>
  {findings_table}
</div>
</body></html>
"""
