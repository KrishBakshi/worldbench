"""Extract a JSON world object from raw model output.

Models rarely return clean JSON: they wrap it in prose, fence it in Markdown
code blocks, or emit trailing commentary. This module recovers the first
balanced JSON object from such output so the runner can measure a model's world
even when its formatting is imperfect (formatting discipline is captured
separately by the schema-validity metric).
"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class ExtractionResult:
    """Outcome of attempting to parse JSON from model output."""

    ok: bool
    data: dict | None
    error: str | None = None
    used_fallback: bool = False


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        # Drop the opening fence (optionally ```json) and the closing fence.
        first_newline = stripped.find("\n")
        if first_newline != -1:
            stripped = stripped[first_newline + 1 :]
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3]
    return stripped


def _find_balanced_object(text: str) -> str | None:
    """Return the first balanced ``{...}`` span, respecting strings/escapes."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def extract_json(text: str) -> ExtractionResult:
    """Best-effort recovery of a JSON object from ``text``."""
    if not text or not text.strip():
        return ExtractionResult(ok=False, data=None, error="empty model output")

    candidate = _strip_code_fences(text)

    # Fast path: the whole (de-fenced) response is valid JSON.
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return ExtractionResult(ok=True, data=parsed)
    except json.JSONDecodeError:
        pass

    # Fallback: pull the first balanced object out of the surrounding prose.
    span = _find_balanced_object(candidate)
    if span is None:
        return ExtractionResult(ok=False, data=None, error="no JSON object found in output")
    try:
        parsed = json.loads(span)
    except json.JSONDecodeError as exc:
        return ExtractionResult(ok=False, data=None, error=f"invalid JSON: {exc}")
    if not isinstance(parsed, dict):
        return ExtractionResult(ok=False, data=None, error="top-level JSON is not an object")
    return ExtractionResult(ok=True, data=parsed, used_fallback=True)
