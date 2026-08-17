from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

load_dotenv()

DEFAULT_MODEL = (
    os.environ.get("WC005_MODEL")
    or os.environ.get("WC004_MODEL")
    or os.environ.get("WC003_MODEL")
    or os.environ.get("WC002_MODEL")
)
TEST_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = TEST_DIR / "prompts"

VALID_AXES = frozenset(
    {"n/a", "falling", "blowing", "rising", "still", "flowing", "grounded", "pulsing", "cyclic"}
)


@dataclass
class CheckResult:
    passed: bool
    reason: str
    details: dict = field(default_factory=dict)


class LeakJudgement(BaseModel):
    found: bool
    evidence: str = ""


class EntityJudgement(BaseModel):
    looks_ok: bool
    moves_ok: bool
    axis: str = "n/a"
    look_evidence: str = ""
    motion_evidence: str = ""


class CycleReport(BaseModel):
    biome: str = "cycle"
    aliases: list[str] = []
    entities: dict[str, EntityJudgement] = Field(default_factory=dict)
    must_not_present: dict[str, LeakJudgement] = Field(default_factory=dict)


def load_templates() -> dict:
    return json.loads((PROMPTS_DIR / "templates.json").read_text(encoding="utf-8"))


def load_prompt() -> str:
    return (PROMPTS_DIR / "prompt.md").read_text(encoding="utf-8").strip()


def invoke_structured(schema: type[BaseModel], prompt: str, model: str | None = None):
    llm = ChatGoogleGenerativeAI(model=model or DEFAULT_MODEL, max_retries=0)
    payload = llm.with_structured_output(schema, include_raw=True, method="json_schema").invoke(prompt)
    raw, parsed, err = payload["raw"], payload["parsed"], payload["parsing_error"]
    if parsed is not None:
        return parsed
    text = raw.content if isinstance(raw.content, str) else str(raw.content)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"parse failed: {err}\n{text[:1000]}")
    return schema.model_validate(json.loads(text[start : end + 1]))
