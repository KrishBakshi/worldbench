"""Judge-model calls shared by capture and by any test that looks at captured views.

One place builds the judge client and turns local PNGs into image parts, so
a text probe, a vision judge, the navigator agent and the evidence agent all
use the same model setup.

Evaluation only (generation is separate and stays on OpenRouter). The API
key lives in .env (GOOGLE_API_KEY); every other setting — which model does
each role, each model's rate limits, and the call hyperparameters — lives in
eval/judge.yaml (or the file JUDGE_CONFIG names). Nothing is hard-coded here:
a missing file or value stops the run with a message naming it.

Roles (judge.yaml `roles`): `judge` for other text-only calls (source judge,
clock patch, evidence agent), `vlm` for every call carrying images, `nav` for
the navigator agent, `extract` for WC002 classify/extract, `probe` for the
WC003-WC005 code probes, `repair` for fixing their badly copied quotes. Roles that share a model share its limits.

Fallbacks (judge.yaml `fallbacks`, optional per model): when a model is still
overloaded after its own retries (503 / 500 / timeouts), invoke_structured
asks its fallback instead. Only server-side unavailability falls back: a bad
key, a spent quota or an unparseable reply is not the model being busy, and a
different model would only hide it. Every fallback is logged, written to the
usage log, and traced in LangSmith as its own run (judge::fallback) under the
call's judge::invoke_structured run.
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
from langsmith import get_current_run_tree, traceable
from pydantic import BaseModel

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# A model with fixed sampling warns on every call that `temperature` is
# ignored. True, but it says nothing new per call.
warnings.filterwarnings("ignore", message=r".*uses fixed sampling defaults.*")


class JudgeConfigError(RuntimeError):
    """eval/judge.yaml is missing, unreadable, or lacks a required value."""


CONFIG_FILE = Path(os.environ.get("JUDGE_CONFIG") or Path(__file__).resolve().parents[1] / "judge.yaml")


def _load_config() -> dict:
    import yaml

    try:
        data = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}
    except FileNotFoundError as exc:
        raise JudgeConfigError(f"judge config not found: {CONFIG_FILE}") from exc
    return data


CONFIG = _load_config()


def setting(section: str, key: str):
    """A required value from judge.yaml; a missing one names itself."""
    try:
        return CONFIG[section][key]
    except (KeyError, TypeError) as exc:
        raise JudgeConfigError(f"{CONFIG_FILE.name} is missing {section}.{key}") from exc


# The call hyperparameters, all from judge.yaml `call:`.
JUDGE_IMAGE_WIDTH = int(setting("call", "image_width"))
JUDGE_MAX_TOKENS = int(setting("call", "max_output_tokens"))
MAX_RATE_RETRIES = int(setting("call", "max_rate_retries"))
MAX_TRANSIENT_RETRIES = int(setting("call", "max_transient_retries"))
CHARS_PER_TOKEN = float(setting("call", "chars_per_token"))
TOKENS_PER_IMAGE = int(setting("call", "tokens_per_image"))
QUOTA_TZ = str(CONFIG.get("quota_day_timezone") or "UTC")

_RETRY_IN = re.compile(r"retry in ([0-9.]+)s", re.I)
_lock = threading.Lock()
# model -> list of [monotonic_time, input_tokens] reservations in the last 60s
_window: dict[str, list[list[float]]] = {}
DAILY_FILE = Path(__file__).resolve().parents[2] / "outputs" / ".judge_daily.json"


def limits_for(model: str) -> dict[str, int]:
    """This model's rpm / tpm / rpd from judge.yaml `limits`. Required: a model
    with no limits there stops the run rather than being driven unbounded."""
    global _UNAVAILABLE
    lim = (CONFIG.get("limits") or {}).get(model)
    if not lim or not all(k in lim for k in ("rpm", "tpm", "rpd")):
        # A run-stopping error, not a per-check one: every call to this model would fail the same way.
        _UNAVAILABLE = f"{CONFIG_FILE.name} has no complete limits (rpm, tpm, rpd) for model {model!r}"
        raise JudgeUnavailable(_UNAVAILABLE)
    return {k: int(lim[k]) for k in ("rpm", "tpm", "rpd")}


def fallback_for(model: str) -> str | None:
    """judge.yaml `fallbacks.<model>`: who answers when `model` is overloaded.
    Optional: no entry means no fallback, and the error stands."""
    fb = (CONFIG.get("fallbacks") or {}).get(model)
    return str(fb) if fb else None


def estimate_tokens(text: str = "", images: int = 0) -> int:
    return int(len(text) / CHARS_PER_TOKEN) + images * TOKENS_PER_IMAGE


def _quota_day() -> str:
    """The provider's quota day (judge.yaml quota_day_timezone)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo(QUOTA_TZ)).strftime("%Y-%m-%d")


def _count_today(model: str) -> None:
    """Add one request to today's count for `model`; stop the run at the daily cap.

    Stored on disk (locked) so sequential and parallel runs share one count.
    """
    import fcntl

    global _UNAVAILABLE
    rpd = limits_for(model)["rpd"]
    DAILY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DAILY_FILE, "a+", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        fh.seek(0)
        try:
            data = json.loads(fh.read() or "{}")
        except json.JSONDecodeError:
            data = {}
        day = _quota_day()
        data = {day: data.get(day, {})}  # older days are dropped
        used = data[day].get(model, 0)
        if used >= rpd:
            _UNAVAILABLE = f"{model} reached its daily cap of {rpd} requests ({day}, resets at midnight {QUOTA_TZ})"
            raise JudgeUnavailable(_UNAVAILABLE)
        data[day][model] = used + 1
        fh.seek(0)
        fh.truncate()
        fh.write(json.dumps(data))


def throttle(model: str | None = None, est_tokens: int = 0) -> list[float]:
    """Block until one more call to `model` fits its per-minute caps; reserve it.

    Returns the reservation [time, tokens]; the caller replaces the estimate
    with the real input-token count once the reply arrives (settle()).
    """
    model = model or judge_model_name()
    lim = limits_for(model)
    _count_today(model)
    while True:
        with _lock:
            now = time.monotonic()
            win = [e for e in _window.get(model, []) if now - e[0] < 60.0]
            _window[model] = win
            used = sum(e[1] for e in win)
            # An empty window always admits one call, even one larger than tpm.
            if len(win) < lim["rpm"] and (not win or used + est_tokens <= lim["tpm"]):
                entry = [now, float(est_tokens)]
                win.append(entry)
                return entry
            wait = 60.0 - (now - win[0][0]) + 0.05
        time.sleep(max(0.05, wait))


def settle(entry: list[float] | None, result) -> None:
    """Replace a reservation's estimated tokens with the reply's real input count."""
    if entry is None:
        return
    msg = result.get("raw") if isinstance(result, dict) else result
    usage = getattr(msg, "usage_metadata", None) or {}
    if usage.get("input_tokens"):
        with _lock:
            entry[1] = float(usage["input_tokens"])


_RATE_LIMIT_RE = re.compile(r"\b429\b|RESOURCE_EXHAUSTED|rate.?limit", re.I)


class JudgeUnavailable(RuntimeError):
    """The judge model can't be used at all: no credit, a bad key, access
    denied, or an unknown model id. Unlike a rate limit or one bad reply,
    nothing that follows can succeed, so callers must not catch it per item
    and carry on: with credits exhausted, capture used to swallow each
    episode's 402 as "one broken biome", then go on taking screenshots and
    motion bursts for all ten biomes that no model would ever judge.

    Sticky: once raised, every later judge call in the process raises it
    again immediately, without a network round trip.
    """


_UNAVAILABLE: str | None = None
_FATAL_STATUS = {401, 402, 403}
_FATAL_RE = re.compile(
    r"requires more credits|insufficient credits|no auth credentials|invalid api key|"
    r"user not found|is not a valid model id|model .* (?:not found|does not exist)|"
    # Provider: a bad key, no access, an unknown model, and the free tier's
    # per-day cap (retrying a daily quota minute by minute only burns the run).
    r"API key not valid|API_KEY_INVALID|PERMISSION_DENIED|NOT_FOUND.*models/|PerDay",
    re.I,
)


def _raise_if_unavailable() -> None:
    if _UNAVAILABLE:
        raise JudgeUnavailable(_UNAVAILABLE)


def _check_fatal(exc: Exception) -> None:
    """Turn an unrecoverable provider error into JudgeUnavailable (and latch it)."""
    global _UNAVAILABLE
    status = getattr(exc, "status_code", None)
    text = f"{exc} {getattr(exc, 'body', '') or ''}"
    if status in _FATAL_STATUS or (status == 404 and "model" in text.lower()) or _FATAL_RE.search(text):
        _UNAVAILABLE = f"judge model {judge_model_name()} unusable (HTTP {status}): {str(exc)[:300]}"
        raise JudgeUnavailable(_UNAVAILABLE) from exc


def _is_rate_limit(exc: Exception) -> bool:
    """A 429 / quota error, from OpenRouter or from the provider behind it.

    By HTTP status first: a client can raise a 429 whose text is only
    "Provider returned error" — no "429" to match — so a text-only check let
    real rate limits fail the call instead of waiting.
    """
    if getattr(exc, "status_code", None) == 429:
        return True
    return bool(_RATE_LIMIT_RE.search(str(exc)) or _RATE_LIMIT_RE.search(str(getattr(exc, "body", "") or "")))


def _rate_limited(exc: Exception) -> float | None:
    """Seconds the server asked us to wait, if `exc` is a rate limit that says; else None."""
    if not _is_rate_limit(exc):
        return None
    headers = getattr(exc, "headers", None) or getattr(getattr(exc, "response", None), "headers", None) or {}
    retry_after = headers.get("retry-after") if hasattr(headers, "get") else None
    if retry_after:
        try:
            return float(retry_after) + 1.0
        except ValueError:
            pass
    match = _RETRY_IN.search(f"{exc} {getattr(exc, 'body', '') or ''}")
    return float(match.group(1)) + 1.0 if match else None


def _backoff(attempt: int, hinted: float | None) -> float:
    return min(65.0, max(hinted or 0.0, 5.0 * attempt))


# Server-side 5xx ("500 INTERNAL" came and went on one vision model: one call
# failed, the next one on the same model worked). Temporary, so retried
# call.max_transient_retries times with backoff; never treated as a verdict
# or as JudgeUnavailable.
_TRANSIENT_RE = re.compile(r"\b(500|502|503|504)\b|INTERNAL|UNAVAILABLE|DEADLINE_EXCEEDED|timed out", re.I)


def _is_transient(exc: Exception) -> bool:
    if getattr(exc, "status_code", None) in (500, 502, 503, 504):
        return True
    return bool(_TRANSIENT_RE.search(str(exc))) and not _is_rate_limit(exc)


def call_with_retry(fn, model: str | None = None, est_tokens: int = 0):
    """Run fn() under `model`'s caps, retrying rate limits and brief server errors."""
    transient_left = MAX_TRANSIENT_RETRIES
    for attempt in range(1, MAX_RATE_RETRIES + 1):
        _raise_if_unavailable()
        entry = throttle(model, est_tokens)
        try:
            result = fn()
            settle(entry, result)
            return result
        except JudgeUnavailable:
            raise
        except Exception as exc:
            _check_fatal(exc)
            if _is_transient(exc) and transient_left > 0:
                transient_left -= 1
                time.sleep(5.0 * (MAX_TRANSIENT_RETRIES - transient_left))
                continue
            hinted = _rate_limited(exc)
            if not _is_rate_limit(exc):
                raise
            if attempt == MAX_RATE_RETRIES:
                raise
            delay = _backoff(attempt, hinted)
            from harness.status import log

            log(f"      rate-limited, retry {attempt}/{MAX_RATE_RETRIES - 1} in {delay:.0f}s")
            time.sleep(delay)


async def acall_with_retry(make_coro, model: str | None = None, est_tokens: int = 0):
    """Async twin of call_with_retry: make_coro() returns a fresh awaitable per attempt."""
    transient_left = MAX_TRANSIENT_RETRIES
    for attempt in range(1, MAX_RATE_RETRIES + 1):
        _raise_if_unavailable()
        entry = await asyncio.to_thread(throttle, model, est_tokens)
        try:
            result = await make_coro()
            settle(entry, result)
            return result
        except JudgeUnavailable:
            raise
        except Exception as exc:
            _check_fatal(exc)
            if _is_transient(exc) and transient_left > 0:
                transient_left -= 1
                await asyncio.sleep(5.0 * (MAX_TRANSIENT_RETRIES - transient_left))
                continue
            hinted = _rate_limited(exc)
            if not _is_rate_limit(exc):
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


def _role_model(role: str, what: str) -> str:
    """judge.yaml `roles.<role>`: never a built-in default. The judge decides
    every score, so a missing value stops the run rather than silently
    picking a model."""
    name = (CONFIG.get("roles") or {}).get(role)
    if not name:
        global _UNAVAILABLE
        _UNAVAILABLE = f"{CONFIG_FILE.name} has no roles.{role} ({what})"
        raise JudgeUnavailable(_UNAVAILABLE)
    return str(name)


def vlm_model_name(override: str | None = None) -> str:
    """The model for every judge call that carries images."""
    return override or _role_model("vlm", "the model for judge calls with images")


def nav_model_name(override: str | None = None) -> str:
    """The navigator agent's model (tool calls on frames)."""
    return override or _role_model("nav", "the navigator agent's model")


def extract_model_name(override: str | None = None) -> str:
    """WC002's classify + extract: slicing the source per biome, reading layout."""
    return override or _role_model("extract", "the model for WC002 classify/extract")


def probe_model_name(override: str | None = None) -> str:
    """WC003/WC004/WC005 code probes: quoting the code that builds each item."""
    return override or _role_model("probe", "the model for the WC003-WC005 code probes")


def judge_model_name(override: str | None = None) -> str:
    """The model for text-only judge calls."""
    return override or _role_model("judge", "the model for text-only judge calls")


def chat(model: str | None = None, temperature: float | None = None) -> ChatGoogleGenerativeAI:
    key = os.environ.get("GOOGLE_API_KEY")
    if not key:
        # Unusable, not flaky: stop the run the same way a rejected key does.
        global _UNAVAILABLE
        _UNAVAILABLE = "GOOGLE_API_KEY is not set in .env (the judge models' key)"
        raise JudgeUnavailable(_UNAVAILABLE)
    # Retries are ours (call_with_retry), so the client's own are off: two
    # retry layers multiply into a burst exactly when the quota is exhausted.
    kwargs = {
        "model": judge_model_name(model),
        "google_api_key": key,
        "max_retries": 0,
        "max_output_tokens": JUDGE_MAX_TOKENS,
    }
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


def log_usage(model: str, role: str, n_images: int, message, seconds: float, fallback_from: str | None = None) -> None:
    """Append one judge call's token use to $JUDGE_USAGE_LOG (JSON lines), if set.

    Off unless the env var names a file. Exists so cost/efficiency decisions
    are made from measured tokens per role (text / vision / navigator)
    rather than guesses.
    """
    path = os.environ.get("JUDGE_USAGE_LOG")
    if not path:
        return
    usage = getattr(message, "usage_metadata", None) or {}
    row = {
        "t": round(time.time(), 1),
        "model": model,
        "role": role,
        "images": n_images,
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "seconds": round(seconds, 2),
    }
    if fallback_from:
        row["fallback_from"] = fallback_from
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except OSError:
        pass


def _trace_inputs(inputs: dict) -> dict:
    """What a judge call's LangSmith run records: sizes and ids, not the whole
    source or base64 frames (those are in the check's own artifacts)."""
    prompt = inputs.get("prompt") or ""
    images = inputs.get("images") or []
    schema = inputs.get("schema")
    return {
        "schema": getattr(schema, "__name__", str(schema)),
        "model": inputs.get("model"),
        "images": [Path(p).name for p in images],
        "prompt_chars": len(prompt),
        "prompt_head": prompt[:400],
        "temperature": inputs.get("temperature"),
    }


def _answer(schema, content, model, temperature, est_tokens):
    """One model's answer under its own caps and retries."""
    runnable = chat(model, temperature).with_structured_output(schema, include_raw=True, method="json_schema")
    return call_with_retry(
        lambda: runnable.invoke([HumanMessage(content=content)]),
        model=model,
        est_tokens=est_tokens,
    )


@traceable(
    name="judge::fallback",
    run_type="chain",
    process_inputs=lambda i: {k: i[k] for k in ("primary", "fallback", "reason", "policy")},
)
def _fallback(primary, fallback, reason, policy, schema, content, temperature, est_tokens):
    """The fallback model answers a call the primary could not serve.

    Its own LangSmith run, so a trace shows which model was asked first, why
    it failed, and which model's answer the score was built on."""
    from harness.status import log

    log(f"      fallback  {primary} unavailable after retries; asking {fallback}  ({reason[:120]})")
    return _answer(schema, content, fallback, temperature, est_tokens)


_FALLBACK_POLICY = (
    "primary retried call.max_transient_retries times on 5xx/timeout, still unavailable; "
    "judge.yaml fallbacks.<primary> answers instead. Not used for bad key, spent quota "
    "or parse errors."
)


@traceable(name="judge::invoke_structured", run_type="chain", process_inputs=_trace_inputs)
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
    # Calls with frames go to the vision model; text-only calls to the judge.
    if model is None and images:
        model = vlm_model_name()
    content: list[dict] = [{"type": "text", "text": prompt}]
    for path in images or []:
        content.append({"type": "text", "text": f"[image: {Path(path).stem}]"})
        content.append(image_part(Path(path)))
    model = model or judge_model_name()
    est = estimate_tokens(prompt, len(images or []))
    answered_by, fallback_from, reason = model, None, None
    started = time.monotonic()
    try:
        payload = _answer(schema, content, model, temperature, est)
    except JudgeUnavailable:
        raise
    except Exception as exc:
        fb = fallback_for(model)
        if not (fb and _is_transient(exc)):
            raise
        reason = str(exc)[:300]
        started = time.monotonic()
        payload = _fallback(
            primary=model, fallback=fb, reason=reason, policy=_FALLBACK_POLICY,
            schema=schema, content=content, temperature=temperature, est_tokens=est,
        )
        answered_by, fallback_from = fb, model
    run = get_current_run_tree()
    if run is not None:
        run.metadata.update({
            "requested_model": model,
            "answered_by": answered_by,
            "fallback_used": fallback_from is not None,
            **({"fallback_reason": reason} if reason else {}),
        })
    raw, parsed, err = payload["raw"], payload["parsed"], payload["parsing_error"]
    log_usage(answered_by, "vision" if images else "text", len(images or []), raw,
              time.monotonic() - started, fallback_from=fallback_from)
    if parsed is not None:
        return parsed
    text = raw.content if isinstance(raw.content, str) else str(raw.content)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"parse failed: {err}\n{text[:1000]}")
    return schema.model_validate(json.loads(text[start : end + 1]))
