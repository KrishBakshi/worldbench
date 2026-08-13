from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from llm import ClassifiedBiomeJS, invoke_structured, load_prompt


def strip_html(html_path: str) -> str:
    raw = Path(html_path).read_text(encoding="utf-8", errors="ignore")
    no_css = re.sub(r"<style\b[^>]*>.*?</style>", "", raw, flags=re.I | re.S)
    scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", no_css, flags=re.I | re.S)
    return "\n\n".join(s.strip() for s in scripts if s.strip())


def classify_biome_js(html_path: str, model: str | None = None) -> ClassifiedBiomeJS:
    js = strip_html(html_path)
    return invoke_structured(ClassifiedBiomeJS, load_prompt("classify.md") + "\n\nSOURCE:\n" + js, model)
