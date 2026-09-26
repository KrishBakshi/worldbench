from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

load_dotenv()

DEFAULT_MODEL = os.environ.get("WC003_MODEL") or os.environ.get("WC002_MODEL")
TEST_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = TEST_DIR / "prompts"

BIOME_IDS = (
    "mountains",
    "forest",
    "highlands",
    "jungle",
    "swamp",
    "grove",
    "grassland",
    "delta",
    "desert",
    "volcano",
)


@dataclass
class CheckResult:
    passed: bool
    reason: str
    details: dict = field(default_factory=dict)


class ItemJudgement(BaseModel):
    found: bool
    evidence: str = ""


class BiomeMicroReport(BaseModel):
    biome: str
    aliases: list[str] = []
    must_present: dict[str, ItemJudgement] = Field(default_factory=dict)
    must_not_present: dict[str, ItemJudgement] = Field(default_factory=dict)


def load_requirements(biome_id: str) -> dict:
    path = PROMPTS_DIR / biome_id / "requirements.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_prompt(biome_id: str) -> str:
    return (PROMPTS_DIR / biome_id / "prompt.md").read_text(encoding="utf-8").strip()


def invoke_structured(schema: type[BaseModel], prompt: str, model: str | None = None):
    """Shared judge client: same model setup, client-side throttle and 429 backoff
    for every test (eval/capture/llm.py)."""
    import sys as _sys

    _root = str(Path(__file__).resolve().parents[2])
    if _root not in _sys.path:
        _sys.path.append(_root)
    from eval.capture.llm import invoke_structured as _shared

    return _shared(schema, prompt, model=model or DEFAULT_MODEL)
