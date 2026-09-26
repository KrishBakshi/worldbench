"""Judge-model calls shared by capture and by any test that looks at captured views.

One place builds the Gemini client and turns local PNGs into image parts, so
a text probe, a vision judge and the navigator agent all use the same model
setup. Model: CAPTURE_MODEL, else the WC002_MODEL every test already uses.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import re
import threading
import time
import warnings
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# gemini-3.5-flash-lite (the current WC002_MODEL) has fixed sampling and warns
# on every call that `temperature` is ignored. The warning is true but says
# nothing new per call; re-votes on that model still differ.
warnings.filterwarnings("ignore", message=r".*uses fixed sampling defaults.*")

# Views go to the judge downscaled: 1280px wide costs ~2x the tokens of 896px
# and the judges are asked about biome-scale features, not single pixels.
JUDGE_IMAGE_WIDTH = 896


# The judge model's free tier is 15 requests/minute. A full ladder is ~80
# calls in bursts (bug-hunt re-votes, ten probes back to back), and on the
# first kimi-k-3 run every WC003 probe hit 429 and the test scored 0/100 for
# a quota reason, not a model one. So calls are spaced client-side
# (JUDGE_RPM) and a 429 that still gets through waits the server's own
# "retry in Xs" hint instead of failing.
JUDGE_RPM = float(os.environ.get("JUDGE_RPM", "15"))
MAX_RATE_RETRIES = 8
_RETRY_IN = re.compile(r"retry in ([0-9.]+)s", re.I)
_lock = threading.Lock()
_last_call = 0.0


def throttle() -> None:
    """Block until one more call fits under JUDGE_RPM (process-wide)."""
    global _last_call
    if JUDGE_RPM <= 0:
        return
    gap = 60.0 / JUDGE_RPM
    with _lock:
        wait = _last_call + gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()


def _rate_limited(exc: Exception) -> float | None:
    """Seconds to wait if `exc` is a 429 / quota error, else None."""
    text = str(exc)
    if "429" not in text and "RESOURCE_EXHAUSTED" not in text:
        return None
    match = _RETRY_IN.search(text)
    return float(match.group(1)) + 1.0 if match else None


def _backoff(attempt: int, hinted: float | None) -> float:
    return min(65.0, max(hinted or 0.0, 5.0 * attempt))


def call_with_retry(fn):
    """Run fn() under the throttle, retrying rate-limit errors only."""
    for attempt in range(1, MAX_RATE_RETRIES + 1):
        throttle()
        try:
            return fn()
        except Exception as exc:
            hinted = _rate_limited(exc)
            if hinted is None and "429" not in str(exc) and "RESOURCE_EXHAUSTED" not in str(exc):
                raise
            if attempt == MAX_RATE_RETRIES:
                raise
            delay = _backoff(attempt, hinted)
            from harness.status import log

            log(f"      rate-limited, retry {attempt}/{MAX_RATE_RETRIES - 1} in {delay:.0f}s")
            time.sleep(delay)


async def acall_with_retry(make_coro):
    """Async twin of call_with_retry: make_coro() returns a fresh awaitable per attempt."""
    for attempt in range(1, MAX_RATE_RETRIES + 1):
        await asyncio.to_thread(throttle)
        try:
            return await make_coro()
        except Exception as exc:
            hinted = _rate_limited(exc)
            if hinted is None and "429" not in str(exc) and "RESOURCE_EXHAUSTED" not in str(exc):
                raise
            if attempt == MAX_RATE_RETRIES:
                raise
            await asyncio.sleep(_backoff(attempt, hinted))


def raise_if_mostly_failed(results: dict, label: str) -> None:
    """Raise when more than half of a check's model calls errored.

    A failed call is an infrastructure fact, not evidence about the world. If
    most of a check's calls failed, the honest outcome is an error (validate
    records max_score 0 and the message), not a score of 0 that reads as the
    model's fault. A few failures still grade, and show as probe_failed rows.
    """
    errors = [v for v in results.values() if isinstance(v, dict) and "error" in v]
    if results and len(errors) * 2 > len(results):
        raise RuntimeError(f"{label}: {len(errors)}/{len(results)} model calls failed; first: {errors[0]['error'][:300]}")


def judge_model_name(override: str | None = None) -> str:
    name = override or os.environ.get("CAPTURE_MODEL") or os.environ.get("WC002_MODEL")
    if not name:
        raise RuntimeError("set CAPTURE_MODEL or WC002_MODEL in .env")
    return name


def chat(model: str | None = None, temperature: float | None = None) -> ChatGoogleGenerativeAI:
    # Retries are ours (call_with_retry), so the client's own are off: two
    # retry layers multiply into a burst exactly when the quota is exhausted.
    kwargs = {"model": judge_model_name(model), "google_api_key": os.environ.get("GOOGLE_API_KEY"), "max_retries": 0}
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


def invoke_structured(
    schema: type[BaseModel],
    prompt: str,
    images: list[Path] | None = None,
    model: str | None = None,
    temperature: float = 0.0,
):
    """Text (+ optional images) in, a validated `schema` out.

    Judges run at temperature 0 so a re-grade of the same frame agrees with
    itself; a caller that re-votes on purpose passes a higher temperature.
    """
    content: list[dict] = [{"type": "text", "text": prompt}]
    for path in images or []:
        content.append({"type": "text", "text": f"[image: {Path(path).stem}]"})
        content.append(image_part(Path(path)))
    runnable = chat(model, temperature).with_structured_output(schema, include_raw=True, method="json_schema")
    payload = call_with_retry(lambda: runnable.invoke([HumanMessage(content=content)]))
    raw, parsed, err = payload["raw"], payload["parsed"], payload["parsing_error"]
    if parsed is not None:
        return parsed
    text = raw.content if isinstance(raw.content, str) else str(raw.content)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"parse failed: {err}\n{text[:1000]}")
    return schema.model_validate(json.loads(text[start : end + 1]))
