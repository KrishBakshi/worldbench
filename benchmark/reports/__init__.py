"""Report rendering: Markdown, JSON, HTML, and leaderboard."""

from __future__ import annotations

from .html import render_html
from .json_report import build_json_report, render_json
from .leaderboard import (
    ModelStanding,
    build_leaderboard_json,
    collect_standings,
    render_leaderboard_html,
    render_leaderboard_markdown,
)
from .markdown import render_markdown

__all__ = [
    "render_markdown",
    "render_json",
    "build_json_report",
    "render_html",
    "collect_standings",
    "render_leaderboard_markdown",
    "render_leaderboard_html",
    "build_leaderboard_json",
    "ModelStanding",
]
