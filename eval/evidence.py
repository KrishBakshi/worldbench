"""Is a judge's quoted evidence really in the world's source?

Every LLM probe returns "evidence" it claims to have copied from world.html.
The graders used to check only that the quote *looks* like building code, so
a plausible invented line (`scene.add(new THREE.Mesh(palmGeo, mat))`) earned
points. This checks the quote against the source, whitespace-insensitive and
line by line, so an honest multi-line quote with trimmed indentation or a
dropped comment still matches.
"""

from __future__ import annotations

import re
from pathlib import Path

_WS = re.compile(r"\s+")
# A quoted line shorter than this is too generic to prove anything ("}", "i++").
MIN_LINE_CHARS = 8
# Share of the quote's substantive lines that must be found in the source.
MIN_MATCH_SHARE = 0.8
# A line still matches if this share of it, from its start, is verbatim in
# the source. Probes garble line tails when copying (seen on kimi-k-3:
# `jcol(0x5f4326,x,z,0.07anche);` for `...0.07)});`). An invented line
# (`new THREE.Mesh(palmGeo, mat)` with no palmGeo anywhere) fails early.
MIN_PREFIX_SHARE = 0.85


def strip_to_js(html_path: str | Path) -> str:
    raw = Path(html_path).read_text(encoding="utf-8", errors="ignore")
    no_css = re.sub(r"<style\b[^>]*>.*?</style>", "", raw, flags=re.I | re.S)
    scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", no_css, flags=re.I | re.S)
    return "\n\n".join(s.strip() for s in scripts if s.strip()) or no_css


def normalize(text: str) -> str:
    return _WS.sub("", text)


def _longest_prefix_in(line: str, source_normalized: str) -> int:
    """Length of the longest prefix of `line` that occurs in the source (binary search:
    if a prefix occurs, every shorter prefix does too)."""
    lo, hi = 0, len(line)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if line[:mid] in source_normalized:
            lo = mid
        else:
            hi = mid - 1
    return lo


def _line_in_source(line: str, source_normalized: str) -> bool:
    if line in source_normalized:
        return True
    return _longest_prefix_in(line, source_normalized) >= MIN_PREFIX_SHARE * len(line)


def in_source(evidence: str, source_normalized: str) -> bool:
    """True if the quote (or >= MIN_MATCH_SHARE of its substantive lines) is in the source.

    `source_normalized` is normalize(source), computed once per world.
    """
    quote = normalize(evidence or "")
    if len(quote) < MIN_LINE_CHARS:
        return False
    if quote in source_normalized:
        return True
    if "\n" not in (evidence or "").strip() and _line_in_source(quote, source_normalized):
        return True
    lines = [normalize(ln.split("//")[0]) for ln in (evidence or "").splitlines()]
    lines = [ln for ln in lines if len(ln) >= MIN_LINE_CHARS]
    if not lines:
        return False
    hits = sum(1 for ln in lines if _line_in_source(ln, source_normalized))
    return hits / len(lines) >= MIN_MATCH_SHARE
