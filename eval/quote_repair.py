"""Make a probe's quotes real source lines before they are graded.

Every code probe (WC003/WC004/WC005) quotes the code that builds an item, and
the graders accept a quote only if `evidence.in_source` finds it, line by
line. That check is what stops invented code from scoring, so it stays
strict. But a probe can find the right code and still copy it badly. Seen on
a real WC005 probe run: three features the world
really has scored 0 because the quote
  - joined separate lines into one: lines 799, 801, 802 of the sun orbit
    quoted as `const sa=...; const sd=...; sunMesh.position...`, or
  - abbreviated with `...`: `const SEASONS=[{name:'Spring',...},...]`.

Three layers, cheapest first:
  1. QUOTE_RULES, appended to every probe prompt: copy lines exactly, one
     source line per line, never join or shorten.
  2. validate(): walks the report's `*evidence` fields and flags quotes that
     are not in the source or contain an ellipsis.
  3. repair: a flagged quote is cut into statement fragments and each
     fragment is located in the source (whitespace-insensitive, so it may
     span lines). If every fragment is found, the quote is replaced by the
     source lines they cover, copied from the file. What is left goes to the
     `repair` model (judge.yaml), which sees a numbered window of source and
     answers with LINE NUMBERS only; the new quote is built from the file,
     so the model can pick lines but cannot write code.

A repaired quote is graded exactly like any other; a quote that cannot be
repaired stays as it was and fails as before. Nothing here makes the grader
itself more lenient. Every repair is logged, and traced in LangSmith
(quote_repair::report / quote_repair::model).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

from langsmith import traceable
from pydantic import BaseModel, Field

from eval.evidence import MIN_LINE_CHARS, in_source, normalize

QUOTE_RULES = """

QUOTING RULES (every *evidence field is checked verbatim against the file, line by line):
- Copy each line exactly as it appears in the source. One source line per line of your quote.
- Never join several source lines into one line; keep the line breaks.
- Never shorten with "..." or "…"; quote fewer lines instead.
- Quote at most 6 consecutive lines. If the code is spread out, quote the single most telling line.
"""

_ELLIPSIS = re.compile(r"\.\.\.|…")
# A repaired quote is the source lines its fragments cover; a quote that
# would need more than this many lines is not a quote any more.
MAX_REPAIRED_LINES = 12
# Source lines shown to the repair model around each fragment's best match.
WINDOW = 8


@dataclass
class Flag:
    path: str
    quote: str
    reasons: list[str]


class LinePick(BaseModel):
    lines: list[int] = Field(default_factory=list, description="source line numbers, empty if none match")


def _is_placeholder(text: str) -> bool:
    t = (text or "").strip().lower()
    return (len(normalize(t)) < MIN_LINE_CHARS or t.startswith(("n/a", "none", "(none"))
            or bool(re.match(r"not (in|within) .*scope", t)))


def _evidence_fields(obj, path: str = ""):
    """(owner, field_name, dotted_path) for every non-empty `*evidence` string."""
    if isinstance(obj, BaseModel):
        for name in type(obj).model_fields:
            value = getattr(obj, name)
            here = f"{path}.{name}" if path else name
            if name.endswith("evidence") and isinstance(value, str):
                if not _is_placeholder(value):
                    yield obj, name, here
            else:
                yield from _evidence_fields(value, here)
    elif isinstance(obj, dict):
        for key, value in obj.items():
            yield from _evidence_fields(value, f"{path}.{key}" if path else str(key))
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            yield from _evidence_fields(value, f"{path}[{i}]")


def validate(report: BaseModel, source_normalized: str) -> list[Flag]:
    """Quotes the graders would reject, or that are abbreviated."""
    flags = []
    for owner, name, path in _evidence_fields(report):
        quote = getattr(owner, name)
        reasons = []
        if _ELLIPSIS.search(quote):
            reasons.append("ellipsis")
        if not in_source(quote, source_normalized):
            reasons.append("not_in_source")
        if reasons:
            flags.append(Flag(path, quote, reasons))
    return flags


class _Index:
    """The source's lines plus a whitespace-free copy mapped back to line numbers."""

    def __init__(self, source: str):
        self.lines = source.splitlines()
        parts, self.starts = [], []
        pos = 0
        for line in self.lines:
            self.starts.append(pos)
            n = normalize(line)
            parts.append(n)
            pos += len(n)
        self.flat = "".join(parts)

    def line_of(self, offset: int) -> int:
        """0-based line holding flat[offset]."""
        lo, hi = 0, len(self.starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo

    def span(self, fragment: str) -> tuple[int, int] | None:
        """Line range (0-based, inclusive) of the first verbatim occurrence."""
        f = normalize(fragment)
        at = self.flat.find(f)
        if at < 0:
            return None
        return self.line_of(at), self.line_of(at + len(f) - 1)

    def best_line(self, fragment: str) -> int | None:
        """Line of the longest prefix of `fragment` found in the source."""
        f = normalize(fragment)
        lo, hi = 0, len(f)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if f[:mid] in self.flat:
                lo = mid
            else:
                hi = mid - 1
        if lo < max(MIN_LINE_CHARS, len(f) // 2):
            return None
        return self.line_of(self.flat.find(f[:lo]))

    def text(self, line_numbers: list[int]) -> str:
        return "\n".join(self.lines[i].strip() for i in sorted(set(line_numbers)))


def _fragments(quote: str) -> list[str]:
    """Statement-sized pieces of a quote: split at line breaks, `...` and `;`."""
    out = []
    for piece in _ELLIPSIS.split(quote):
        for line in piece.splitlines():
            for stmt in re.split(r";\s*", line):
                stmt = stmt.strip().strip(",[]{}()")
                if len(normalize(stmt)) >= MIN_LINE_CHARS:
                    out.append(stmt)
    return out


def _mechanical(quote: str, idx: _Index) -> str | None:
    frags = _fragments(quote)
    if not frags:
        return None
    covered: set[int] = set()
    for frag in frags:
        span = idx.span(frag)
        if span is None:
            return None
        covered.update(range(span[0], span[1] + 1))
    if len(covered) > MAX_REPAIRED_LINES:
        return None
    return idx.text(sorted(covered))


@traceable(name="quote_repair::model", run_type="chain")
def _by_model(quote: str, idx: _Index, context: str) -> tuple[str | None, dict]:
    """Ask the repair model which source lines the quote meant. Line numbers only."""
    from eval.capture.llm import invoke_structured, repair_model_name

    anchors = [line for line in (idx.best_line(f) for f in _fragments(quote)) if line is not None]
    if not anchors:
        return None, {"why": "no fragment of the quote is near any source line"}
    window: set[int] = set()
    for a in anchors:
        window.update(range(max(0, a - WINDOW), min(len(idx.lines), a + WINDOW + 1)))
    shown = "\n".join(f"{i + 1}: {idx.lines[i]}" for i in sorted(window))
    prompt = (
        f"A reviewer quoted code for: {context}\n"
        f"Their quote (possibly joined or abbreviated):\n{quote}\n\n"
        f"Numbered source lines:\n{shown}\n\n"
        f"Return the line numbers (at most {MAX_REPAIRED_LINES}) whose code the quote was copied from. "
        "Only lines listed above. Empty list if none of them match."
    )
    pick = invoke_structured(LinePick, prompt, model=repair_model_name())
    chosen = [n - 1 for n in pick.lines if (n - 1) in window][:MAX_REPAIRED_LINES]
    if not chosen:
        return None, {"why": "model picked no valid line", "picked": pick.lines}
    return idx.text(chosen), {"picked": [n + 1 for n in sorted(chosen)]}


@traceable(name="quote_repair::report", run_type="chain",
           process_inputs=lambda i: {"label": i.get("label")})
def repair_quotes(report: BaseModel, source: str, label: str = "") -> list[dict]:
    """Validate every quote in `report`; repair flagged ones in place.

    Returns one record per flagged quote: path, reasons, before, after,
    method (mechanical / model / none). Only quotes that pass in_source
    after repair are written back.
    """
    from harness.status import log

    source_normalized = normalize(source)
    flags = validate(report, source_normalized)
    if not flags:
        return []
    idx = _Index(source)
    owners = {path: (owner, name) for owner, name, path in _evidence_fields(report)}
    records = []
    for flag in flags:
        record = {"path": flag.path, "reasons": flag.reasons, "before": flag.quote, "after": None, "method": "none"}
        fixed = _mechanical(flag.quote, idx)
        method = "mechanical"
        if fixed is None or not in_source(fixed, source_normalized):
            started = time.monotonic()
            try:
                fixed, info = _by_model(flag.quote, idx, f"{label} {flag.path}")
            except Exception as exc:  # the repair is optional: a failure leaves the quote as it was
                fixed, info = None, {"error": str(exc)[:300]}
            record["model"] = {**info, "seconds": round(time.monotonic() - started, 1)}
            method = "model"
        if fixed and in_source(fixed, source_normalized) and not _ELLIPSIS.search(fixed):
            owner, name = owners[flag.path]
            setattr(owner, name, fixed)
            record.update(after=fixed, method=method)
        records.append(record)
        log(f"      quotes    {label} {flag.path}: {','.join(flag.reasons)} -> "
            f"{'repaired (' + record['method'] + ')' if record['after'] else 'left as is'}")
    return records
