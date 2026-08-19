"""Strip world.html to inline JS, then ask whether global day/night and
season cycles are implemented in SOURCE.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from llm import CycleReport, invoke_structured, load_prompt, load_templates

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))
from harness.status import log  # noqa: E402


def strip_html(html_path: str) -> str:
    raw = Path(html_path).read_text(encoding="utf-8", errors="ignore")
    no_css = re.sub(r"<style\b[^>]*>.*?</style>", "", raw, flags=re.I | re.S)
    scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", no_css, flags=re.I | re.S)
    return "\n\n".join(s.strip() for s in scripts if s.strip())


def probe_cycle(html_path: str, model: str | None = None) -> CycleReport:
    log("      probing  day/night + seasons  (llm)")
    js = strip_html(html_path)
    templates = load_templates()
    prompt = load_prompt().replace("{TEMPLATES}", json.dumps(templates, indent=2)).replace("{SOURCE}", js)
    return invoke_structured(CycleReport, prompt, model)
