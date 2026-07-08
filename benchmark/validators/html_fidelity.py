"""HTML fidelity validation: does a generated ``world.html`` actually derive
from a given ``world.json``, rather than being a generic, unconditioned scene?

WorldBench's second artifact is a self-contained Three.js visualization built
from a world's JSON data. This validator never renders or screenshots the
page — consistent with the rest of WorldBench, it is purely deterministic text
analysis:

1. The HTML must embed the exact source JSON verbatim in a
   ``<script type="application/json" id="world-data">`` block, so grading has
   ground truth to check against instead of guessing from prose or a rendered
   image.
2. The embedded blob's ``metadata.id`` must match the source world's id (proves
   the *correct* data was embedded, not an unrelated one).
3. The page must reference Three.js and contain a canvas to render into.
4. The code must actually read the embedded blob back out (``getElementById``/
   ``querySelector`` for ``world-data`` paired with ``JSON.parse``) rather than
   leaving it as an inert, unused script tag.

This is unlike every other validator in the package (single-argument
``validate(world)``): it takes both the HTML text and the ``World`` it should
be derived from, since there is no way to check fidelity without a reference
to compare against. It is therefore not part of :func:`validate_world`'s
composite and is invoked directly, e.g. via ``worldbench score-html``.
"""

from __future__ import annotations

import json
import re

from ..models import World
from ..results import Severity, ValidationResult
from .base import FindingCollector

NAME = "html_fidelity"
PREFIX = "HTM"

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

#: Structural section keys a genuinely data-driven scene should touch.
_SECTION_KEYS = [
    "regions", "features", "bodies", "zones", "species", "edges", "cycle",
    "events", "dynamics",
]


def extract_embedded_world(html: str) -> tuple[dict | None, str]:
    """Return ``(embedded_json_or_None, html_with_the_data_block_removed)``.

    The stripped text is what code-usage checks should search, so a model
    can't earn credit for "referencing" ids that only appear inertly inside
    the data blob itself.
    """
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


def validate(html: str, world: World) -> ValidationResult:
    """Check that ``html`` is a self-contained Three.js page whose scene is
    actually built from ``world``'s data, not a generic unrelated visualization.
    """
    c = FindingCollector(NAME, PREFIX)

    c.check("<html" in html.lower(), "not a valid HTML document (no <html> tag)")
    c.check(bool(_THREE_RE.search(html)), "no reference to three.js found")
    c.check(bool(_CANVAS_RE.search(html)), "no <canvas> element found")

    embedded, remainder = extract_embedded_world(html)
    if not c.check(
        embedded is not None,
        "no embedded world-data JSON script block found "
        '(expected <script type="application/json" id="world-data">...)',
    ):
        return c.result()

    embedded_id = (embedded or {}).get("metadata", {}).get("id")
    if not c.check(
        embedded_id == world.metadata.id,
        f"embedded JSON id {embedded_id!r} does not match source world id "
        f"{world.metadata.id!r} — this HTML was not built from the given JSON",
    ):
        return c.result()

    c.check(
        bool(_READS_BLOCK_RE.search(html)) and bool(_JSON_PARSE_RE.search(html)),
        "embedded JSON is never read back out (no getElementById/querySelector "
        "for 'world-data' paired with JSON.parse) — data appears unused",
        severity=Severity.WARNING,
    )

    referenced_sections = sum(1 for key in _SECTION_KEYS if key in remainder)
    c.check(
        referenced_sections >= len(_SECTION_KEYS) // 2,
        f"only {referenced_sections}/{len(_SECTION_KEYS)} schema section keys "
        f"are referenced in the rendering code outside the data block",
        severity=Severity.WARNING,
    )

    ids = _collect_ids(world)
    if ids:
        referenced_ids = sum(1 for i in ids if i in remainder)
        fraction = referenced_ids / len(ids)
        c.check(
            fraction >= 0.3,
            f"only {referenced_ids}/{len(ids)} entity ids ({fraction:.0%}) from "
            f"the source JSON appear in the code outside the data block",
            severity=Severity.WARNING,
        )

    return c.result()
