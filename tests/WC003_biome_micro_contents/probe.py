"""Strip world.html to inline JS, then ask the per-biome prompt whether
each required / forbidden micro-feature is in that biome's scope.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from llm import BIOME_IDS, BiomeMicroReport, invoke_structured, load_prompt, load_requirements


def strip_html(html_path: str) -> str:
    raw = Path(html_path).read_text(encoding="utf-8", errors="ignore")
    no_css = re.sub(r"<style\b[^>]*>.*?</style>", "", raw, flags=re.I | re.S)
    scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", no_css, flags=re.I | re.S)
    return "\n\n".join(s.strip() for s in scripts if s.strip())


def probe_biome(js: str, biome_id: str, model: str | None = None) -> BiomeMicroReport:
    requirements = load_requirements(biome_id)
    prompt = (
        load_prompt(biome_id)
        .replace("{REQUIREMENTS}", json.dumps(requirements, indent=2))
        .replace("{SOURCE}", js)
    )
    return invoke_structured(BiomeMicroReport, prompt, model)


def probe_all(
    html_path: str,
    model: str | None = None,
    biome_ids: tuple[str, ...] | None = None,
) -> dict[str, BiomeMicroReport | dict]:
    js = strip_html(html_path)
    reports: dict[str, BiomeMicroReport | dict] = {}
    for biome_id in biome_ids or BIOME_IDS:
        try:
            reports[biome_id] = probe_biome(js, biome_id, model)
        except Exception as exc:
            reports[biome_id] = {"error": str(exc)}
    return reports
