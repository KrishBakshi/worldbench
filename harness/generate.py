"""LangGraph generate -> debug -> fix loop for one world.html. The only
generation entrypoint — there is no separate one-shot `generate` command;
a one-shot completion is just what the `generate` node below does before
handing off to `debug`.

    generate  -- one call to the model under test (harness.model_call),
                 writes inputs/<name>/world.html. Reasoning tokens stream
                 live to stderr; the full generated file is printed too.
    debug     -- static lint (harness.world_lint: [structure] document
                 damage — leftover markdown fences, unclosed <script>,
                 leaked commentary — and [syntax]: a real JS parser, with a
                 missing/extra brace localized and parser-verified) then
                 headless console capture (harness.browser_debug), skipped
                 when a script doesn't parse. No rendering check.
    fix       -- only runs when debug found errors. Same model under test,
                 same live reasoning stream as generate. Two modes:
                 [structure] -> rewrite the whole document, streamed as
                 content (model_call.complete_document), never as a tool
                 argument; everything else -> small str_replace edits
                 against a windowed excerpt, each one parse-checked the
                 moment it's made and refused if it would break parsing.
                 Loops back to debug.

Stops when a debug pass comes back clean, or after MAX_FIX_ROUNDS (5) fix
attempts — a hard cap, stated to the model — whichever comes first. The file on disk at inputs/<name>/world.html
is always the latest attempt, clean or not; a run that gives up still leaves
something there rather than nothing, and says so.

Transparency: every node (generate/debug/fix) is a named LangSmith
@traceable run nested under one parent run per invocation of `run()`, and
every one of them also prints to stderr as it happens — reasoning, the full
generated/fixed HTML, and every debug error found. Nothing about a run is
visible only in one place or the other; the terminal and LangSmith see the
same information, so a run's traces don't need to be re-run to see what
happened, and a run without LangSmith configured is still fully legible on
the terminal alone.

Usage:
    uv run python -m harness.generate <name> --model <openrouter-id>
    uv run python -m harness.generate <name> --model <openrouter-id> --run
"""

from __future__ import annotations

import argparse
import difflib
import json
import shutil
import tempfile
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
load_dotenv(REPO_ROOT / ".env")

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage  # noqa: E402
from langchain_core.tools import tool  # noqa: E402
from langgraph.graph import END, StateGraph  # noqa: E402
from langsmith import get_current_run_tree, traceable  # noqa: E402

from harness.model_call import (  # noqa: E402
    ReasoningLoop,
    SilentToolCallTimeout,
    complete_document,
    detect_reasoning,
    generate as generate_completion,
    invoke_turn,
)
from harness.code_tools import ReadOnlySource, dep_path  # noqa: E402
from harness.world_lint import check_world, syntax_findings  # noqa: E402
from harness.status import log, log_to_file, timed  # noqa: E402

INPUTS_DIR = REPO_ROOT / "inputs"
# The whole fix budget, and the only limit on fixing: a hard cap, not a
# default (no CLI override). It is stated to the model up front — in the
# generation system message and in every fix round's prompt — so a model can
# plan across the budget instead of discovering it: a crash hides every
# error after it (a real run surfaced exactly one new bug per round and ran
# out with the fourth still hidden), so a model that knows it
# has N rounds has a reason to look past the one reported error. Nothing
# inside a round is capped: a model mid-fix is never cut off by the harness
# (the old 4-tool-calls-per-round cap ended rounds while models were still
# making progress). See _patch_round for the one stop that isn't a budget.
MAX_FIX_ROUNDS = 5
# One sampling temperature for every turn the model under test takes —
# generation and fix alike. Fix turns used to run at 0.2, and very low
# temperature is a known trigger for reasoning models looping on their own
# text; a model's fix rounds should also sample the way it generated.
TEMPERATURE = 1.0
MAX_ERRORS_IN_PROMPT = 15  # dedup already collapses per-frame spam; cap for prompt size
FIX_CONTEXT_LINES = 40  # lines of context on each side of an error location, for the windowed fix prompt
# A stack trace is control flow ("who called this"), never data flow ("where
# did this bad value come from"). A real run hit the gap: `Cannot
# read properties of undefined (reading 'color')` threw at line 350 on
# `terrainGeo.attributes.color`, with a caller frame at 1037 — but the defect
# is at line 996, `terrainGeo=buildTerrain(0);`, assigning a Mesh to something
# used as a Geometry. Windows were 310-390 and 997-1077: the fix site missed
# by ONE line, and no stack frame would ever have pointed at it. So the
# identifiers on a throw line get their own definition/assignment sites
# windowed in too. Smaller span than an error window — the point is to see
# what a name was bound to, not to tour its neighbourhood.
DEF_CONTEXT_LINES = 12
# Selectivity gate, and the whole reason this doesn't blow the prompt up. An
# identifier assigned all over the file localizes nothing: the same scan run
# for bug 1's `z` returns 21 hits (loop counters, destructured coords) and
# would drag in most of the document, while `terrainGeo` returns exactly
# [572, 996]. More hits than this means the name isn't a useful lookup key.
DEF_SITE_MAX_HITS = 3
DEF_SITE_MIN_IDENT_LEN = 3  # `z`, `i`, `dx` are loop noise, never a useful definition lookup
MAX_DEFINITION_SITES = 6  # hard cap across all errors, so a pathological line can't unwind the windowing


class AgentState(TypedDict):
    name: str
    model: str
    round: int
    reasoning: bool | None
    errors: list[str]
    fix_history: list[str]
    # Per-round record of what debug saw, kept for the same reason fix_history
    # exists: so the saved run trajectory reads as a sequence of rounds rather
    # than just a final verdict. Scoped to one run() call, like fix_history.
    debug_history: list[dict]
    force_full_file: bool
    # Run-scoped temp dir where debug saves the modules the page imported
    # (modules.json, {url: source}); fix mounts them read-only under deps/.
    # A path, not the sources: a 1MB library in graph state would be copied
    # into every node's trace.
    modules_dir: str
    _generate_reasoning: str
    _generate_html: str
    _fix_reasoning: str | None


def _html_path(name: str) -> Path:
    return INPUTS_DIR / name / "world.html"


def _print_output_block(label: str, content: str) -> None:
    """Print the full generated/fixed file to stderr, clearly delimited.

    Nothing is summarized or truncated here — the point is that the actual
    output a round produced is visible in the terminal, not just its
    existence ("wrote world.html") or its size.
    """
    log(f"\n----- {label} ({len(content)} chars) -----")
    log(content)
    log(f"----- end {label} -----\n")


def _tag_current_run(*, round_n: int, extra_tags: list[str] | None = None, **metadata) -> None:
    """Attach round number + arbitrary metadata to the current LangSmith run,
    and tag it `round-N` so the whole loop is filterable/groupable by round
    in the UI without opening every nested run — no-ops (get_current_run_tree
    returns None) exactly when @traceable itself no-ops, i.e. without
    LANGSMITH_TRACING=true + LANGSMITH_API_KEY.
    """
    run_tree = get_current_run_tree()
    if run_tree is None:
        return
    run_tree.add_metadata({"round": round_n, **metadata})
    run_tree.add_tags([f"round-{round_n}", *(extra_tags or [])])


@traceable(name="generate::generate_node", run_type="chain")
def _generate_node(state: AgentState) -> dict:
    log(f"[generate] {state['model']} -> inputs/{state['name']}/world.html")
    result = generate_completion(
        state["name"],
        state["model"],
        reasoning=state["reasoning"],
        system=generation_system(),
        temperature=TEMPERATURE,
    )
    _print_output_block(f"generated output, round {state['round']}", result.html)
    _tag_current_run(
        round_n=state["round"],
        model=state["model"],
        html_chars=len(result.html),
        generation_rounds=result.rounds,  # model_call.generate()'s own truncation-recovery turns, distinct from fix rounds
    )
    return {
        "_generate_reasoning": result.reasoning_content,
        "_generate_html": result.html,
    }


@traceable(name="generate::debug_node", run_type="chain")
def _debug_node(state: AgentState) -> dict:
    modules: dict[str, str] = {}
    with timed(f"debug round {state['round']}"):
        errors = check_world(_html_path(state["name"]), modules=modules)
    if state.get("modules_dir") and modules:
        (Path(state["modules_dir"]) / "modules.json").write_text(json.dumps(modules), encoding="utf-8")
    if errors:
        log(f"[debug]  round {state['round']}: {len(errors)} distinct error(s)")
        for e in errors:
            log(f"         {e}")
    else:
        log(f"[debug]  round {state['round']}: clean")
    _tag_current_run(
        round_n=state["round"],
        error_count=len(errors),
        errors=errors,
        extra_tags=["clean" if not errors else "has-errors"],
    )
    return {
        "errors": errors,
        "debug_history": state["debug_history"] + [{"round": state["round"], "errors": errors}],
    }


def _budget_text(round_n: int) -> str:
    """The fix budget, said the same way to every model in every mode."""
    left = MAX_FIX_ROUNDS - round_n
    if left:
        after = (
            f"{left} more after this one. After each round the file is loaded in a "
            "browser again and any remaining errors come back to you as the next "
            "round; when the rounds run out, the file on disk is final."
        )
    else:
        after = "this is the LAST one. No round follows: the file as you leave it now is final."
    return (
        f"This is fix round {round_n} of {MAX_FIX_ROUNDS} — a hard limit; {after} "
        "A crash stops the script, so an error can hide others that come after "
        "it; the list you see is only what the browser reached."
    )


def _fix_system(round_n: int) -> str:
    return (
        "You are fixing a self-contained Three.js world.html file by editing it "
        "in place: str_replace(old_str, new_str) changes existing text, and "
        "insert_after_line(line, text) adds new lines after a numbered line "
        "without touching existing ones. To look around first, you also have "
        "read-only tools over the current file: grep (regex, returns `N: line`), "
        "read_lines(start, end), and shell (read-only grep/sed -n/head/tail/wc "
        "pipelines on world.html) — use them to find where a bad value comes "
        "from, or whether the same mistake repeats elsewhere, before you edit. "
        "You'll get a list of problems and "
        "either the complete file or, when every problem has a known source "
        "location, only excerpts around those locations (the file may be "
        "hundreds of lines; you don't need all of it to fix a specific error). "
        "Problem tags:\n"
        "  [syntax] — a script doesn't parse, found by a real JS parser. The "
        "message says where the fix goes (often a missing or extra '}' — and "
        "says so when the parser has verified that one change makes the script "
        "parse).\n"
        "  [uncaught] / [console.error] / [navigation] — browser runtime error. "
        "The location is where it was raised in this file; `called from` lines "
        "are callers, and the bug is often in a caller or where a value was "
        "assigned, not at the raise site.\n"
        "Excerpt lines are prefixed `NNNNN: ` for orientation only — old_str/"
        "new_str must be the exact source text WITHOUT that prefix. Keep each "
        "edit small: a few lines of old_str, never a whole function or the file. "
        "Call str_replace as many times as you need. Every result tells you "
        "immediately whether the edit applied and whether all scripts still "
        "parse; an edit that would break parsing is refused and the file is "
        "left unchanged, so read the result and adjust. If old_str isn't found, "
        "the result shows the closest matching text — copy from it.\n"
        f"{_budget_text(round_n)}\n"
        "Stop calling tools when you are done with this round."
    )


def _rewrite_system(round_n: int) -> str:
    return (
        "You are repairing a self-contained Three.js world.html file whose "
        "document structure is broken: a generation artifact such as two drafts "
        "glued together, a leaked markdown fence, prose in the file, or a missing "
        "</html>. Patching around that damage can't work, so write the complete "
        "corrected file: ONE HTML document from <!DOCTYPE html> to </html>, "
        "keeping everything that works in the current file. Output only the raw "
        "file — no markdown fences, no commentary before or after it.\n"
        f"{_budget_text(round_n)}"
    )


def generation_system() -> str:
    """Harness context for the generate node, identical for every model.
    prompts/prompt.md stays the world spec (mirrored in worldbench-web); how
    the harness checks the result is the harness's to say."""
    return (
        "After you write the file, it is loaded in a headless browser and "
        "checked for JavaScript errors. If there are any, you get at most "
        f"{MAX_FIX_ROUNDS} fix rounds in total: each round shows you the errors "
        "the browser reached and lets you edit the file. After the last round "
        "the file is final as it stands. A crash stops the script, so an error "
        "can hide others that come after it."
    )


# Two-step on purpose. _LOCATION_RE isolates the suffix browser_debug.py
# appends (`(line 104, col 27; called from line 383, line 397)`), or
# world_lint's `[syntax]` equivalent (`(line 393; see also line 391, line
# 451)`), and nothing else; _LINE_NO_RE then pulls EVERY line number out of that matched group.
# Doing it in one pass would mean running findall over the whole error string,
# where a model's own `console.error("line 5 failed")` would register as a
# source location. Matches the old single-location format unchanged.
_LOCATION_RE = re.compile(r"\(line \d+(?:, col \d+)?(?:; (?:called from|see also) line \d+(?:, line \d+)*)?\)")
_LINE_NO_RE = re.compile(r"line (\d+)")


def _error_line_numbers(errors: list[str]) -> list[int]:
    """Every source line worth windowing around, across all errors.

    Includes caller frames, not just throw sites: for `X is not a function`
    /`undefined is not an object`-class errors the throw site is usually
    correct code and the defect is in the caller, so windowing on the throw
    site alone shows the model nothing wrong (see browser_debug.py's
    docstring for the run this comes from).
    """
    lines = []
    for e in errors:
        m = _LOCATION_RE.search(e)
        if m:
            lines.extend(int(n) for n in _LINE_NO_RE.findall(m.group(0)))
    return lines


# Identifiers that are never a useful definition lookup: language keywords,
# globals the model can't have mis-assigned, and the Three.js surface. Without
# this, `const`/`new`/`THREE` are scanned on every throw line for nothing.
_JS_NOISE = frozenset(
    """
    const let var function class return new this true false null undefined void delete
    typeof instanceof in of if else for while do switch case break continue
    try catch finally throw yield await async export import from default extends super
    Math JSON Object Array String Number Boolean Date RegExp Error Promise Map Set Symbol
    console window document requestAnimationFrame setTimeout setInterval
    THREE scene camera renderer geometry material mesh position attributes length
    """.split()
)
_IDENT_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
# `X is not defined` / `X is not a function` name the identifier outright; the
# throw line may not even contain it (a bare call `foo()` does, but a callback
# invoked by name from elsewhere may not), so both sources are scanned.
_NAMED_IDENT_RE = re.compile(r"\b([A-Za-z_$][A-Za-z0-9_$]*) is not (?:defined|a function|a constructor)")


def _definition_sites(lines: list[str], errors: list[str], throw_lines: list[int]) -> list[int]:
    """Lines that bind an identifier involved in one of these errors.

    A stack trace answers "who called this", never "where did this value come
    from" — see DEF_CONTEXT_LINES' comment for the run that exposed the
    difference. This closes that gap statically: take the identifiers on each
    throw line (plus any the error message names outright), and find where
    each one is declared or assigned.

    Selectivity is the whole design. An identifier bound in many places
    localizes nothing, so anything over DEF_SITE_MAX_HITS is dropped rather
    than windowed — that's what keeps a common name like `z` (21 hits in the
    file this was built against) from dragging in the whole document while
    `terrainGeo` (2 hits) resolves exactly.
    """
    candidates: list[str] = []
    for e in errors:
        candidates.extend(_NAMED_IDENT_RE.findall(e))
    for n in throw_lines:
        candidates.extend(_IDENT_RE.findall(lines[n - 1]))

    seen: dict[str, None] = {}
    for ident in candidates:
        if len(ident) >= DEF_SITE_MIN_IDENT_LEN and ident not in _JS_NOISE:
            seen.setdefault(ident, None)

    sites: list[int] = []
    for ident in seen:
        # A binding: `let/const/var/function/class NAME`, or `NAME =` (but not
        # `==`/`===`/`=>`, and not `!=`/`<=`/`>=` via the lookbehind).
        pattern = re.compile(
            rf"\b(?:let|const|var|function|class)\s+{re.escape(ident)}\b"
            rf"|(?<![=!<>])\b{re.escape(ident)}\s*=(?![=>])"
        )
        hits = [i + 1 for i, line in enumerate(lines) if pattern.search(line)]
        if 0 < len(hits) <= DEF_SITE_MAX_HITS:
            sites.extend(hits)
    # Deterministic order, and a hard cap so one pathological throw line can't
    # quietly turn a windowed round into a full-file one.
    return sorted(set(sites))[:MAX_DEFINITION_SITES]


def _build_fix_context(html: str, errors: list[str], *, force_full_file: bool = False) -> tuple[str, bool]:
    """Return (text_shown_to_model, is_full_file).

    The common case — a runtime problem with a known `(line N)` location and
    no [structure] problem alongside it — gets only a windowed excerpt
    (+/- FIX_CONTEXT_LINES) around each error, not the whole file: that's
    the actual point of this function, industry-standard for a coding
    harness working against files far larger than any one bug. Falls back
    to the complete file in three cases where a window genuinely isn't
    enough: any [structure] problem present (the whole document is what's
    broken; _rewrite_round sends it whole anyway), no error in this batch
    carrying a location to window around at all, or `force_full_file` — the
    previous windowed round came back with no edits at all (see
    _fix_node), which is evidence the window is pointing somewhere the bug
    isn't, not that the model was idle.
    """
    if force_full_file or any(e.startswith("[structure]") for e in errors):
        return html, True

    lines = html.split("\n")
    total = len(lines)
    # Drop locations that aren't in this file at all. A console.error raised
    # from inside the Three.js CDN bundle reports ITS line number (seen for
    # real: `computeBoundingSphere(): Computed radius is NaN` at line 10951
    # of three.module.js, against an 806-line world.html), and Playwright's
    # msg.location gives no way to tell which script it came from. Windowing
    # on it yields range(10911, 807) — an empty excerpt handed to a
    # str_replace-only round, i.e. the same "fix this, but you can't see it"
    # dead end caller frames were added to eliminate. Out of range means the
    # bug is somewhere in our file we can't localize, which is what the
    # full-file fallback is for.
    line_numbers = [n for n in _error_line_numbers(errors) if 1 <= n <= total]
    if not line_numbers:
        return html, True

    # The throw site is the first location in each error's suffix; caller
    # frames follow it. Only throw lines are scanned for identifiers — a
    # caller frame's own locals are a different scope and would just add noise.
    throw_lines = []
    for e in errors:
        m = _LOCATION_RE.search(e)
        if m:
            first = _LINE_NO_RE.search(m.group(0))
            if first and 1 <= int(first.group(1)) <= total:
                throw_lines.append(int(first.group(1)))

    spans = [(n, FIX_CONTEXT_LINES) for n in set(line_numbers)]
    spans += [(n, DEF_CONTEXT_LINES) for n in _definition_sites(lines, errors, throw_lines)]
    windows = sorted([max(1, n - span), min(total, n + span)] for n, span in spans)
    merged: list[list[int]] = []
    for w in windows:
        if merged and w[0] <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], w[1])
        else:
            merged.append(w)

    parts = []
    for start, end in merged:
        block = "\n".join(f"{n:>5}: {lines[n - 1]}" for n in range(start, end + 1))
        parts.append(f"--- lines {start}-{end} of {total} total ---\n{block}")
    return "\n\n".join(parts), False


# ---------------------------------------------------------------------------
# str_replace, made to land on the first try.
#
# A failed edit costs a whole model turn (one real round spent 2 of its
# turns on `old_str not found`). Every refusal below therefore
# says exactly what to do next, and the two mismatches that are unambiguous
# (excerpt line-number prefixes copied into old_str; whitespace-only
# differences with a single match) are resolved instead of refused.
# ---------------------------------------------------------------------------
_EXCERPT_PREFIX_RE = re.compile(r"^ *\d+: ?", re.M)
CLOSEST_MATCH_MIN_RATIO = 0.5
CLOSEST_MATCH_MAX_LINES = 30
SNIPPET_LINES = 4  # context on each side of a [syntax] location shown in a tool result


def _strip_excerpt_prefixes(text: str) -> str:
    """Drop `  393: ` prefixes if EVERY non-blank line carries one — the
    signature of text copied from a windowed excerpt, not of real code."""
    body = [line for line in text.split("\n") if line.strip()]
    if body and all(_EXCERPT_PREFIX_RE.match(line) for line in body):
        return _EXCERPT_PREFIX_RE.sub("", text)
    return text


def _line_of(html: str, offset: int) -> int:
    return html.count("\n", 0, offset) + 1


def _closest_match(html: str, old_str: str) -> str:
    """The file text most similar to a not-found old_str, line-aligned."""
    want_lines = [line.strip() for line in old_str.strip("\n").split("\n")]
    want = "\n".join(want_lines)
    file_lines = html.split("\n")
    stripped = [line.strip() for line in file_lines]
    k = max(1, len(want_lines))
    best_ratio, best_at = 0.0, None
    for i in range(0, max(1, len(file_lines) - k + 1)):
        sm = difflib.SequenceMatcher(None, want, "\n".join(stripped[i : i + k]), autojunk=False)
        if sm.real_quick_ratio() <= best_ratio or sm.quick_ratio() <= best_ratio:
            continue
        ratio = sm.ratio()
        if ratio > best_ratio:
            best_ratio, best_at = ratio, i
    if best_at is None or best_ratio < CLOSEST_MATCH_MIN_RATIO:
        return "No similar text found — the code you're targeting may not exist in this file."
    end = min(best_at + k, best_at + CLOSEST_MATCH_MAX_LINES)
    exact = "\n".join(file_lines[best_at:end])
    return (
        f"Closest text in the file (lines {best_at + 1}-{end}, {best_ratio:.0%} similar) — "
        f"copy old_str exactly from here:\n{exact}"
    )


def _unescape(text: str) -> str:
    r"""`\n`/`\t` typed as two characters -> the real characters. Models
    writing JSON tool arguments sometimes double-escape; seen for real: an
    old_str of `\n` meant as a blank line, reported "not found"."""
    return text.replace("\\n", "\n").replace("\\t", "\t")


def _resolve_old_str(html: str, old_str: str) -> tuple[int, int, str] | str:
    """(start, end, note) of old_str's one occurrence, or an `ERROR: …` string."""
    if not _unescape(old_str).strip():
        # A blank line or a bare newline can't name one place in a file, and
        # this is always an attempt to *add* text (seen for real: a model
        # spent a whole round trying to replace line 34, a blank line, to put
        # a new <script> element before line 35).
        return (
            "ERROR: old_str has no visible text (only whitespace/newlines), so it can't pick out "
            "one place. To add new lines, use insert_after_line(line, text) with the line number "
            "the tools show."
        )
    count = html.count(old_str)
    if count == 1:
        start = html.index(old_str)
        return start, start + len(old_str), ""
    if count > 1:
        lines = [_line_of(html, m.start()) for m in re.finditer(re.escape(old_str), html)]
        return (
            f"ERROR: old_str matches {count} places (lines {', '.join(map(str, lines[:8]))}), not 1. "
            "Add a neighbouring line to old_str so it matches exactly one of them."
        )
    if "\\n" in old_str or "\\t" in old_str:
        resolved = _resolve_old_str(html, _unescape(old_str))
        if not isinstance(resolved, str):
            return resolved[0], resolved[1], " (read \\n/\\t in old_str as a real newline/tab)"

    unprefixed = _strip_excerpt_prefixes(old_str)
    if unprefixed != old_str:
        resolved = _resolve_old_str(html, unprefixed)
        if not isinstance(resolved, str):
            return resolved[0], resolved[1], " (ignored the excerpt line-number prefixes in old_str)"
        return resolved

    # Same tokens, different whitespace/indentation, one match: unambiguous.
    pattern = r"\s+".join(re.escape(tok) for tok in old_str.split())
    matches = list(re.finditer(pattern, html))
    if len(matches) == 1:
        return matches[0].start(), matches[0].end(), " (matched ignoring whitespace differences)"
    if len(matches) > 1:
        lines = [_line_of(html, m.start()) for m in matches]
        return (
            f"ERROR: old_str not found exactly; ignoring whitespace it matches {len(matches)} places "
            f"(lines {', '.join(map(str, lines[:8]))}). Copy it exactly, with a neighbouring line to make it unique."
        )
    return "ERROR: old_str not found in the current file. " + _closest_match(html, old_str)


def _snippet(html: str, finding: str) -> str:
    """Numbered lines around a finding's primary location, so a tool result
    shows the model the problem instead of making it ask for it."""
    m = _LOCATION_RE.search(finding)
    first = _LINE_NO_RE.search(m.group(0)) if m else None
    if not first:
        return ""
    lines = html.split("\n")
    center = int(first.group(1))
    lo, hi = max(1, center - SNIPPET_LINES), min(len(lines), center + SNIPPET_LINES)
    return "\n" + "\n".join(f"{n:>5}: {lines[n - 1]}" for n in range(lo, hi + 1))


def _provider_failure_note(round_n: int, exc: Exception) -> str:
    note = f"round {round_n}: model call failed, round forfeited ({type(exc).__name__}: {exc})"
    log(f"error    {note}")
    return note


@traceable(name="generate::fix_node", run_type="chain")
def _fix_node(state: AgentState) -> dict:
    """Route by what's broken. [structure] -> the model rewrites the whole
    document as streamed content (_rewrite_round); anything else -> small
    parse-verified str_replace edits (_patch_round)."""
    if any(e.startswith("[structure]") for e in state["errors"]):
        return _rewrite_round(state)
    return _patch_round(state)


def _problems_text(state: AgentState) -> str:
    history_note = ""
    if state["fix_history"]:
        history_note = (
            "Previous attempts this session (do not repeat an edit that didn't "
            "fix the problem — diagnose why it's still failing instead):\n"
            + "\n".join(state["fix_history"])
            + "\n\n"
        )
    errors_text = "\n".join(f"- {e}" for e in state["errors"][:MAX_ERRORS_IN_PROMPT])
    return f"{history_note}Problems:\n{errors_text}"


def _rewrite_round(state: AgentState) -> dict:
    """Full rewrite as streamed content, never as a tool-call argument.

    The tool-call version is what failed in a real run: the provider
    buffers tool arguments, so a 54KB write_world_html call left the
    connection silent until OpenRouter's idle timeout killed it (504), three
    times. Content streams — progress is visible, the connection is never
    idle — and complete_document continues a cut-off rewrite the same way
    generate() continues a cut-off generation.
    """
    round_n = state["round"]
    html_path = _html_path(state["name"])
    current_html = html_path.read_text(encoding="utf-8")
    total_lines = current_html.count("\n") + 1
    log(f"[fix]    round {round_n}: [structure] problem — full rewrite, streamed as content")
    messages = [
        SystemMessage(content=_rewrite_system(round_n)),
        HumanMessage(
            content=f"{_problems_text(state)}\n\nCurrent world.html (complete, {total_lines} lines):\n"
            f"```html\n{current_html}\n```"
        ),
    ]
    reasoning_text = None
    try:
        doc = complete_document(
            state["model"],
            messages,
            temperature=TEMPERATURE,
            reasoning=bool(state["reasoning"]),
            label=f"fix round {round_n} rewrite",
            stop_on_repetition=True,
        )
        reasoning_text = doc.reasoning_content
        if doc.complete:
            html_path.write_text(doc.html, encoding="utf-8")
            note = f"round {round_n}: full rewrite ({len(doc.html)} chars, {doc.turns} turn(s)) for a [structure] problem"
            _print_output_block(f"fixed output, round {round_n}", doc.html)
        else:
            note = f"round {round_n}: rewrite still incomplete after {doc.turns} turn(s) — discarded, file unchanged"
        log(f"[fix]    {note}")
    except (SilentToolCallTimeout, ReasoningLoop, ValueError, httpx.HTTPError) as exc:
        note = _provider_failure_note(round_n, exc)
    _tag_current_run(round_n=round_n, context_mode="rewrite", outcome=note)
    return {
        "round": round_n + 1,
        "fix_history": state["fix_history"] + [note],
        "force_full_file": False,
        "_fix_reasoning": reasoning_text,
    }


_LOOP_NUDGE = (
    "Your last reasoning started repeating the same passage word for word, so it "
    "was stopped and discarded. Don't re-read the same lines again. State one "
    "concrete hypothesis and check it with a tool call — the cause may be in a "
    "file other than world.html — or make an edit."
)


def _imported_modules(state: AgentState) -> dict[str, str]:
    """{deps/<host>/<path>: source} for the modules the last debug pass saw."""
    index = Path(state.get("modules_dir") or "") / "modules.json"
    if not state.get("modules_dir") or not index.is_file():
        return {}
    return {dep_path(url): text for url, text in json.loads(index.read_text(encoding="utf-8")).items()}


def _patch_round(state: AgentState) -> dict:
    round_n = state["round"]
    html_path = _html_path(state["name"])
    current_html = html_path.read_text(encoding="utf-8")
    current_syntax = syntax_findings(current_html)
    edits: list[tuple[str, str]] = []
    refused = 0  # edits the parser turned away — proof the model found the spot, so no escalation

    def _apply(start: int, end: int, replacement: str, how: str, label: str) -> str:
        """Put `replacement` in place of current_html[start:end], verified.

        Verified on the spot rather than a debug round later. Parsing takes
        tens of ms; a debug round costs a Chromium launch, a CDN fetch and a
        fresh model turn — and it's how edits that broke something new used
        to surface. Shared by both edit tools so they can't drift apart.
        """
        nonlocal current_html, current_syntax, refused
        candidate = current_html[:start] + replacement + current_html[end:]
        after = syntax_findings(candidate)
        if after and not current_syntax:
            refused += 1
            return (
                "ERROR: edit NOT applied — the file parses now and this edit would break it:\n"
                f"{after[0]}{_snippet(candidate, after[0])}\nFix the edit and retry."
            )
        fixed_syntax = bool(current_syntax) and not after
        old_text = current_html[start:end]
        current_html, current_syntax = candidate, after
        source.refresh(current_html)
        edits.append((old_text, replacement))
        first, last = _line_of(current_html, start), _line_of(current_html, start + max(0, len(replacement) - 1))
        result = f"OK: {label} applied{how}; it now spans lines {first}-{last}."
        if after:
            return f"{result} The script still does not parse:\n{after[0]}{_snippet(current_html, after[0])}"
        if fixed_syntax:
            return f"{result} Every script parses now — the [syntax] problem is fixed."
        return f"{result} Every script still parses. (Runtime errors are re-checked in the browser after this round.)"

    @tool
    def str_replace(old_str: str, new_str: str) -> str:
        """Replace one exact, unique occurrence of old_str with new_str. Keep both small.
        To ADD new lines rather than change existing ones, use insert_after_line."""
        resolved = _resolve_old_str(current_html, old_str)
        if isinstance(resolved, str):
            return resolved
        start, end, how = resolved
        replacement = new_str
        if how.startswith(" (ignored the excerpt"):
            replacement = _strip_excerpt_prefixes(new_str)
        elif how.startswith(" (read"):
            replacement = _unescape(new_str)
        return _apply(start, end, replacement, how, "edit")

    @tool
    def insert_after_line(line: int, text: str) -> str:
        """Insert `text` as new line(s) after line `line` of world.html, using the line numbers
        the tools show (0 inserts at the very top). Existing lines are untouched — use this to
        add markup or code, e.g. a new <script> element before an existing one."""
        lines = current_html.split("\n")
        if not 0 <= int(line) <= len(lines):
            return f"ERROR: line {line} is out of range — world.html has {len(lines)} lines."
        if not text.strip():
            return "ERROR: text is empty."
        text = _unescape(text) if "\n" not in text and "\\n" in text else text
        offset = sum(len(x) + 1 for x in lines[: int(line)])  # start of the line after `line`
        block = text if text.endswith("\n") else text + "\n"
        if offset > len(current_html):  # after the last line, which has no trailing newline
            offset, block = len(current_html), "\n" + block.rstrip("\n")
        return _apply(offset, offset, block, "", "insert")

    context_text, is_full_file = _build_fix_context(
        current_html, state["errors"], force_full_file=state["force_full_file"]
    )
    total_lines = current_html.count("\n") + 1
    if is_full_file:
        if state["force_full_file"]:
            log(
                f"[fix]    round {round_n}: escalating to the full "
                f"{total_lines}-line file — the previous windowed round made no edits"
            )
        file_block = f"Current world.html (complete, {total_lines} lines):\n```html\n{context_text}\n```"
    else:
        shown_lines = context_text.count("\n") + 1
        file_block = (
            f"Current world.html is {total_lines} lines — showing only the excerpt(s) "
            f"below, around each reported error location:\n\n{context_text}"
        )
        log(
            f"[fix]    round {round_n}: sending {shown_lines} context line(s) "
            f"instead of the full {total_lines}-line file"
        )

    # Read-only view of the file for looking around before editing (grep,
    # read_lines, an allowlisted shell) — a temp copy, never the real file,
    # refreshed whenever an edit lands so a search always sees current text —
    # plus the modules the page imported, under deps/: an error can live in an
    # imported file, and a model that can only see world.html can only guess.
    source = ReadOnlySource(current_html, _imported_modules(state))
    read_tools = source.tools()
    bound = {t.name: t for t in [str_replace, insert_after_line, *read_tools]}

    deps_note = ""
    if source.extra_paths:
        deps_note = (
            "\n\nModules the page imported are readable (not editable) with the same tools:\n"
            + "\n".join(f"- {p}" for p in source.extra_paths)
        )
    messages = [
        SystemMessage(content=_fix_system(round_n)),
        HumanMessage(content=f"{_problems_text(state)}\n\n{file_block}{deps_note}"),
    ]
    try:
        reasoning_chunks: list[str] = []
        tool_names_used: list[str] = []
        failure_note = None
        loop_note = None
        # Calls that failed against the file as it stood (keyed with len(edits),
        # which changes whenever the file does). str_replace is deterministic, so
        # re-sending one of these can only get the same answer: that is a loop,
        # not an attempt, and it's the one thing that ends a round early. A model
        # making any progress — a new call, or the file changing — never is.
        failed_calls: set[tuple[str, int]] = set()
        last_turn_looped = False
        turns = 0
        while True:
            turns += 1
            try:
                with timed(f"fix round {round_n}/{MAX_FIX_ROUNDS} · turn {turns}"):
                    turn = invoke_turn(
                        state["model"],
                        messages,
                        temperature=TEMPERATURE,
                        max_tokens=None,
                        reasoning=bool(state["reasoning"]),
                        tools=list(bound.values()),
                        stop_on_repetition=True,
                    )
            except ReasoningLoop:
                # Proven repetition, not a slow model (see model_call's
                # _RepetitionGuard). The looped text is not replayed; the model
                # is told and gets a fresh turn. Looping again straight away is
                # the same no-progress signal as re-sending a failed call.
                if last_turn_looped:
                    loop_note = f"round {round_n}: ended — reasoning looped verbatim on two turns in a row"
                    log(f"[fix]    {loop_note}")
                    break
                last_turn_looped = True
                messages.append(HumanMessage(content=_LOOP_NUDGE))
                continue
            except (SilentToolCallTimeout, ValueError, httpx.HTTPError) as exc:
                # A provider failure forfeits this round, not the run: edits
                # already applied are kept, and the trajectory still gets written.
                # (a 504 here used to crash run() and lose its .json.)
                failure_note = _provider_failure_note(round_n, exc)
                break
            last_turn_looped = False
            if turn.reasoning_content:
                reasoning_chunks.append(turn.reasoning_content)
            if not turn.tool_calls:
                break

            ai_kwargs = {"reasoning_content": turn.reasoning_content} if turn.reasoning_content else {}
            messages.append(AIMessage(content=turn.text, tool_calls=turn.tool_calls, additional_kwargs=ai_kwargs))
            for call in turn.tool_calls:
                tool_names_used.append(call["name"])
                # An actual gate, not a lookup table: a model can emit a call for a
                # tool it was never bound (seen for real on a free-tier model).
                key = (json.dumps([call["name"], call["args"]], sort_keys=True, default=str), len(edits))
                if key in failed_calls:
                    loop_note = f"round {round_n}: ended — the model re-sent a call that had already failed on the unchanged file"
                    result = "ERROR: identical to a call that already failed on this unchanged file; ending this round."
                elif call["name"] not in bound:
                    result = f"ERROR: {call['name']} is not available — the tools are {', '.join(bound)}."
                else:
                    try:
                        result = bound[call["name"]].invoke(call["args"])
                    except Exception as exc:  # noqa: BLE001 — a malformed tool call shouldn't kill the round
                        result = f"ERROR: {call['name']} call was malformed ({exc}); check the argument names and types."
                if result.startswith(("ERROR", "REFUSED")):
                    failed_calls.add(key)
                log(f"[fix]    round {round_n}: {call['name']}() -> {result}".replace("\n", "\n         "))
                messages.append(ToolMessage(content=result, tool_call_id=call["id"]))
            if loop_note:
                log(f"[fix]    {loop_note}")
                break

    finally:
        source.close()

    if edits:
        html_path.write_text(current_html, encoding="utf-8")
        note = f"round {round_n}: {len(edits)} edit(s) applied"
        log(f"[fix]    {note} to {html_path}")
        for old, new in edits:
            log(f"         - {len(old)} chars -> {len(new)} chars")
        _print_output_block(f"fixed output, round {round_n}", current_html)
    else:
        note = f"round {round_n}: no edits made (tools called: {tool_names_used or 'none'})"
        if not is_full_file and failure_note is None and not refused:
            note += " — windowed excerpt evidently didn't contain the bug; next round gets the complete file"
        log(f"[fix]    {note}")
    if refused:
        note += f"; {refused} edit(s) refused because they would have broken parsing"
    if loop_note:
        note += "; " + loop_note.removeprefix(f"round {round_n}: ")
    if failure_note:
        note = f"{note}; {failure_note}"

    # A windowed round that called no tool and applied no edit is the signal
    # that the excerpt was pointing at the wrong place — not that there was
    # nothing to do. Burning the remaining rounds on the same window is how a
    # real run spent all 3 attempts producing zero edits. Escalate instead.
    # A provider failure says nothing about the window, and a parser-refused
    # edit proves the model found the spot — neither escalates.
    escalate = not is_full_file and not edits and failure_note is None and not refused

    _tag_current_run(
        round_n=round_n,
        context_mode="full_file" if is_full_file else "windowed",
        tool_call_turns=turns,  # LLM turns spent inside this one fix round, not to be confused with the outer round count
        ended_on_repeat=loop_note is not None,
        tools_used=tool_names_used,
        edits_applied=len(edits),
        edits_refused=refused,
        escalate_to_full_file=escalate,
        provider_failure=failure_note,
        outcome=note,
    )
    return {
        "round": round_n + 1,
        "fix_history": state["fix_history"] + [note],
        "force_full_file": escalate,
        "_fix_reasoning": "\n".join(reasoning_chunks),
    }


def _route_after_debug(state: AgentState) -> str:
    if not state["errors"]:
        return "clean"
    if state["round"] > MAX_FIX_ROUNDS:
        return "give_up"
    return "fix"


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("generate", _generate_node)
    graph.add_node("debug", _debug_node)
    graph.add_node("fix", _fix_node)
    graph.set_entry_point("generate")
    graph.add_edge("generate", "debug")
    graph.add_conditional_edges(
        "debug",
        _route_after_debug,
        {"clean": END, "give_up": END, "fix": "fix"},
    )
    graph.add_edge("fix", "debug")
    return graph.compile()


@traceable(name="generate::run", run_type="chain")
def run(
    name: str,
    model: str,
    *,
    reasoning: bool | None = None,
) -> Path:
    """Run the full generate -> debug -> fix loop for one model/name.

    reasoning=None (default) auto-detects via OpenRouter's catalog once
    (detect_reasoning) and reuses that for both the generate and fix nodes,
    so a reasoning-capable model streams its chain of thought on every turn
    of the loop, not just the first. Traced as one parent LangSmith run
    (`generate::run`) with every node's run nested under it, so the whole
    attempt — not just one step of it — is visible as a single trace tree.
    """
    started = datetime.now(timezone.utc)
    stamp = started.strftime("%Y%m%d-%H%M%S")
    log_dir = INPUTS_DIR / name / "logs"
    with log_to_file(log_dir / f"{stamp}.log") as log_path:
        log(f"[run]    {name} | model={model} | max_fix_rounds={MAX_FIX_ROUNDS} | started {started.isoformat()}")
        log(f"[run]    transcript -> {log_path}")
        if reasoning is None:
            reasoning = detect_reasoning(model)
            log(f"[reasoning] auto-detected {model}: {'capable' if reasoning else 'not reasoning-capable'}")

        app = build_graph()
        modules_dir = tempfile.mkdtemp(prefix="wb-modules-")
        try:
            final_state = app.invoke(
                {
                    "name": name,
                    "model": model,
                    "round": 1,
                    "reasoning": reasoning,
                    "errors": [],
                    "fix_history": [],
                    "debug_history": [],
                    "force_full_file": False,
                    "modules_dir": modules_dir,
                }
            )
        finally:
            shutil.rmtree(modules_dir, ignore_errors=True)
        dest = _html_path(name)
        fix_rounds_used = final_state["round"] - 1
        status = "clean" if not final_state["errors"] else "gave_up"
        if final_state["errors"]:
            log(
                f"warn     gave up after {MAX_FIX_ROUNDS} fix round(s); "
                f"{len(final_state['errors'])} error(s) still present in {dest}"
            )
            for e in final_state["errors"]:
                log(f"         {e}")
        else:
            log(f"clean    no console errors after {fix_rounds_used} round(s)")

        # Structured sibling of the transcript. The .log is the full story
        # (every reasoning stream, every generated file); this is the part you
        # actually read when coming back to a run days later — what each round
        # saw and did, in order. Written inside the `with` so the transcript
        # records that it was written, and so a crash before this point still
        # leaves the .log behind.
        trajectory = {
            "name": name,
            "model": model,
            "started_at": started.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "reasoning": reasoning,
            "max_fix_rounds": MAX_FIX_ROUNDS,
            "fix_rounds_used": fix_rounds_used,
            "debug_rounds": final_state["debug_history"],
            "fix_history": final_state["fix_history"],
            "remaining_errors": final_state["errors"],
            "world_html": str(dest),
            "transcript": str(log_path),
        }
        json_path = log_dir / f"{stamp}.json"
        json_path.write_text(json.dumps(trajectory, indent=2) + "\n", encoding="utf-8")
        log(f"[run]    trajectory -> {json_path}")

    # The parent run's own outputs, not just its return value (a bare Path) —
    # opening `generate::run` in LangSmith should show the whole loop's
    # trajectory (how many rounds, what each one did, where it ended up)
    # without having to open every nested generate/debug/fix run to piece it
    # together by hand.
    run_tree = get_current_run_tree()
    if run_tree is not None:
        run_tree.add_metadata(
            {
                "model": model,
                "max_rounds": MAX_FIX_ROUNDS,
                "fix_rounds_used": fix_rounds_used,
                "status": status,
            }
        )
        run_tree.add_outputs(
            {
                "status": status,
                "fix_rounds_used": fix_rounds_used,
                "max_rounds": MAX_FIX_ROUNDS,
                "fix_history": final_state["fix_history"],
                "remaining_error_count": len(final_state["errors"]),
                "remaining_errors": final_state["errors"],
                "output_path": str(dest),
            }
        )
        run_tree.add_tags([status, f"rounds-used-{fix_rounds_used}", f"model:{model}"])
    return dest


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Generate a world.html, then debug+fix browser console errors via a LangGraph loop."
    )
    parser.add_argument("name", help='folder to write under inputs/, e.g. "my-model"')
    parser.add_argument("--model", required=True, help='OpenRouter model id, e.g. "vendor/model-name"')
    parser.add_argument(
        "--reasoning",
        choices=["auto", "on", "off"],
        default="auto",
        help="stream reasoning tokens live on every turn, generate and fix alike "
        "(default: auto-detect once via OpenRouter's model catalog)",
    )
    parser.add_argument("--run", action="store_true", help="after finishing, run the full eval ladder against it")
    args = parser.parse_args(argv)

    reasoning = {"auto": None, "on": True, "off": False}[args.reasoning]
    dest = run(args.name, args.model, reasoning=reasoning)
    log(f"wrote    {dest}")

    if args.run:
        from eval.run import main as run_main

        run_main([args.name])
    else:
        print(f"uv run python -m eval.run {args.name}")


if __name__ == "__main__":
    # app = build_graph()
    # app.get_graph().draw_mermaid_png(output_file_path="./data/harness-dag/generate.png")
    main()
