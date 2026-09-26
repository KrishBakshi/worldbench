"""Judge-model calls shared by capture and by any test that looks at captured views.

One place builds the Gemini client and turns local PNGs into image parts, so
a text probe, a vision judge and the navigator agent all use the same model
setup. Model: CAPTURE_MODEL, else the WC002_MODEL every test already uses.
"""

from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# Views go to the judge downscaled: 1280px wide costs ~2x the tokens of 896px
# and the judges are asked about biome-scale features, not single pixels.
JUDGE_IMAGE_WIDTH = 896


def judge_model_name(override: str | None = None) -> str:
    name = override or os.environ.get("CAPTURE_MODEL") or os.environ.get("WC002_MODEL")
    if not name:
        raise RuntimeError("set CAPTURE_MODEL or WC002_MODEL in .env")
    return name


def chat(model: str | None = None, temperature: float | None = None) -> ChatGoogleGenerativeAI:
    kwargs = {"model": judge_model_name(model), "google_api_key": os.environ.get("GOOGLE_API_KEY"), "max_retries": 2}
    if temperature is not None:
        kwargs["temperature"] = temperature
    return ChatGoogleGenerativeAI(**kwargs)


def image_part(path: Path, width: int = JUDGE_IMAGE_WIDTH) -> dict:
    from PIL import Image

    img = Image.open(path).convert("RGB")
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return {"type": "image_url", "image_url": f"data:image/jpeg;base64,{b64}"}


def invoke_structured(schema: type[BaseModel], prompt: str, images: list[Path] | None = None, model: str | None = None):
    """Text (+ optional images) in, a validated `schema` out."""
    content: list[dict] = [{"type": "text", "text": prompt}]
    for path in images or []:
        content.append({"type": "text", "text": f"[image: {Path(path).stem}]"})
        content.append(image_part(Path(path)))
    payload = (
        chat(model)
        .with_structured_output(schema, include_raw=True, method="json_schema")
        .invoke([HumanMessage(content=content)])
    )
    raw, parsed, err = payload["raw"], payload["parsed"], payload["parsing_error"]
    if parsed is not None:
        return parsed
    text = raw.content if isinstance(raw.content, str) else str(raw.content)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"parse failed: {err}\n{text[:1000]}")
    return schema.model_validate(json.loads(text[start : end + 1]))
