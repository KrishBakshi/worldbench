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
