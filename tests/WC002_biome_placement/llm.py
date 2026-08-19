from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

load_dotenv()

DEFAULT_MODEL = os.environ.get("WC002_MODEL")
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
    llm = ChatGoogleGenerativeAI(
        model=model or DEFAULT_MODEL,
        google_api_key=os.environ.get("GOOGLE_API_KEY"),
        max_retries=0,
    )
    payload = llm.with_structured_output(schema, include_raw=True, method="json_schema").invoke(prompt)
    raw, parsed, err = payload["raw"], payload["parsed"], payload["parsing_error"]
    if parsed is not None:
        return parsed
    text = raw.content if isinstance(raw.content, str) else str(raw.content)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"parse failed: {err}\n{text[:1000]}")
    return schema.model_validate(json.loads(text[start : end + 1]))
