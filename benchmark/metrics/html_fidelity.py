"""Metric: html_fidelity.

Scores how faithfully a generated ``world.html`` (a self-contained Three.js
visualization) actually derives from a given ``world.json``, as opposed to a
generic scene that ignores it. Purely deterministic text analysis — no
rendering, no screenshots, no LLM judging.

This metric is deliberately kept out of :mod:`benchmark.metrics.overall` and
``weights.yaml``: it scores a different artifact (HTML) against a reference
(the JSON) rather than judging the JSON in isolation, so blending it into the
existing 9-metric ``overall`` would change the meaning of every prior JSON-only
score. It is reported as its own separate number, e.g. via
``worldbench score-html``.

Per this package's convention, metrics never import validators (see
``benchmark/validators/html_fidelity.py`` for the sibling pass/fail checks) —
so the small amount of embedded-JSON extraction logic here is intentionally
duplicated rather than shared.
"""

from __future__ import annotations

import json
import re

from ..models import World
from ..results import MetricResult
from ._common import clamp

NAME = "html_fidelity"

_DATA_BLOCK_RE = re.compile(
    r'<script[^>]*\bid=["\']world-data["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
_READS_BLOCK_RE = re.compile(
    r"""(getElementById\(\s*['"]world-data['"]\s*\)|querySelector\(\s*['"]#world-data['"]\s*\))""",
    re.IGNORECASE,
)
_JSON_PARSE_RE = re.compile(r"JSON\.parse\s*\(", re.IGNORECASE)
_THREE_RE = re.compile(r"\bthree(\.js|\.module\.js)?\b|THREE\.", re.IGNORECASE)
_CANVAS_RE = re.compile(r"<canvas\b|createElement\(\s*['\"]canvas['\"]\s*\)", re.IGNORECASE)

_SECTION_KEYS = [
    "regions", "features", "bodies", "zones", "species", "edges", "cycle",
    "events", "dynamics",
]


def _extract_embedded_world(html: str) -> tuple[dict | None, str]:
    match = _DATA_BLOCK_RE.search(html)
    if not match:
        return None, html
    remainder = html[: match.start()] + html[match.end() :]
    try:
        return json.loads(match.group(1)), remainder
    except json.JSONDecodeError:
        return None, remainder


def _collect_ids(world: World) -> list[str]:
    ids = [world.metadata.id]
    ids += [r.id for r in world.layout.regions]
    ids += [f.id for f in world.terrain.features]
    ids += [b.id for b in world.water.bodies]
    ids += [z.id for z in world.biomes.zones]
    ids += [s.id for s in world.flora.species]
    ids += [s.id for s in world.fauna.species]
    return ids


def score_html_fidelity(html: str, world: World) -> MetricResult:
    """Score how much of ``world`` the given ``html`` actually uses.

    100 requires: the exact source JSON embedded and identified, three.js and
    a canvas present, the blob demonstrably read back out, and the rendering
    code touching most of the schema's sections and entity ids.
    """
    embedded, remainder = _extract_embedded_world(html)
    embedded_id = (embedded or {}).get("metadata", {}).get("id") if embedded else None
    id_matches = embedded is not None and embedded_id == world.metadata.id

    if not id_matches:
        detail = (
            "no matching embedded world-data JSON found — this HTML does not "
            "appear to have been built from the given world"
        )
        return MetricResult(name=NAME, score=0.0, weight=1.0, detail=detail)

    has_three = bool(_THREE_RE.search(html))
    has_canvas = bool(_CANVAS_RE.search(html))
    reads_blob = bool(_READS_BLOCK_RE.search(html)) and bool(_JSON_PARSE_RE.search(html))

    ids = _collect_ids(world)
    id_fraction = (sum(1 for i in ids if i in remainder) / len(ids)) if ids else 0.0
    section_fraction = sum(1 for k in _SECTION_KEYS if k in remainder) / len(_SECTION_KEYS)
    usage_fraction = clamp(100.0 * (0.5 * id_fraction + 0.5 * section_fraction)) / 100.0

    value = clamp(
        40.0
        + 10.0 * has_three
        + 10.0 * has_canvas
        + 15.0 * reads_blob
        + 25.0 * usage_fraction
    )
    detail = (
        f"embedded JSON matches (40), three.js={has_three}, canvas={has_canvas}, "
        f"reads blob={reads_blob}, data usage={usage_fraction * 100:.0f}%"
    )
    return MetricResult(name=NAME, score=value, weight=1.0, detail=detail)
