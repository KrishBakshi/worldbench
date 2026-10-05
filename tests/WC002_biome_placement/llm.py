from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

DEFAULT_MODEL = None  # the role's model from eval/judge.yaml
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8").strip()

BiomeId = Literal[
    "mountains", "forest", "highlands", "jungle", "swamp",
    "grove", "grassland", "delta", "desert", "volcano",
]


@dataclass
class CheckResult:
    passed: bool
    reason: str
    details: dict = field(default_factory=dict)


class BiomeBlock(BaseModel):
    present: bool
    aliases: list[str] = []
    placement_code: str = ""
    elevation_code: str = ""


class ClassifiedBiomeJS(BaseModel):
    biomes: dict[str, BiomeBlock]


class BiomeNode(BaseModel):
    id: BiomeId
    neighbors: list[BiomeId]
    evidence: str


class ExtractedGraph(BaseModel):
    nodes: list[BiomeNode]
    elevation_order: list[BiomeId] = Field(
        description="all 10 biome ids, highest elevation to lowest"
    )


def invoke_structured(schema: type[BaseModel], prompt: str, model: str | None = None):
    """Shared judge client: same model setup, client-side throttle and 429 backoff
    for every test (eval/capture/llm.py)."""
    import sys as _sys

    _root = str(Path(__file__).resolve().parents[2])
    if _root not in _sys.path:
        _sys.path.append(_root)
    from eval.capture.llm import invoke_structured as _shared

    return _shared(schema, prompt, model=model or DEFAULT_MODEL)
