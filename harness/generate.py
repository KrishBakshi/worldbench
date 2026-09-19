"""LangGraph generate -> debug -> fix loop for one world.html. The only
generation entrypoint — there is no separate one-shot `generate` command;
a one-shot completion is just what the `generate` node below does before
handing off to `debug`.

    generate  -- one call to the model under test (harness.model_call),
                 writes inputs/<name>/world.html. Reasoning tokens stream
                 live to stderr; the full generated file is printed too.
    debug     -- static structure lint (harness.world_lint: leftover
                 markdown fences, unclosed <script>, leaked commentary,
                 truncated last statement) then headless console capture
                 (harness.browser_debug). No rendering check.
    fix       -- only runs when debug found errors. A tool-calling agent
                 (same model under test, same live reasoning stream as
                 generate) reads the current file + the error list and
                 calls write_world_html with the complete corrected file.
                 Loops back to debug. [structure] errors mean the model
                 glued two drafts together or cut off mid-JS — rewrite
                 the whole document, don't patch the fence.

Stops when a debug pass comes back clean, or after --max-fix-rounds fix
attempts — whichever comes first. The file on disk at inputs/<name>/world.html
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
    uv run python -m harness.generate <name> --model <openrouter-id> \\
        --max-fix-rounds 5 --run
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
load_dotenv(REPO_ROOT / ".env")

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage  # noqa: E402
from langchain_core.tools import tool  # noqa: E402
from langgraph.graph import END, StateGraph  # noqa: E402
from langsmith import get_current_run_tree, traceable  # noqa: E402

from harness.model_call import detect_reasoning, generate as generate_completion, invoke_turn  # noqa: E402
from harness.world_lint import check_world  # noqa: E402
from harness.status import log, timed  # noqa: E402

INPUTS_DIR = REPO_ROOT / "inputs"
# A dry run against nex-n2.5-mini:free needed 3 fix attempts to genuinely
# converge (round 1 fixed the original bug but its own second edit
# introduced a new one; round 2's fix unmasked a second, pre-existing,
# unrelated syntax error the parser had never reached before; round 3's
# fix unmasked a runtime race condition only reachable once the file
# finally parsed) — one bug hiding behind another, fixed one layer at a
# time, is the normal shape of this loop. A 4th attempt was tried in that
# same dry run and made things worse (misdiagnosed the race condition,
# traded a working error message for a different one) rather than better,
# so more rounds isn't free insurance — 3 is deliberately not "3 undersells
# it," it's "the loop reports an honest remaining error instead of a
# model spending a 4th attempt badly guessing." Raise it only alongside
# evidence a specific class of bug needs more layers, not preemptively.
DEFAULT_MAX_FIX_ROUNDS = 3
MAX_ERRORS_IN_PROMPT = 15  # dedup already collapses per-frame spam; cap for prompt size
MAX_TOOL_CALLS_PER_FIX_ROUND = 4  # bound on how many str_replace/write_world_html calls one round may make
FIX_CONTEXT_LINES = 40  # lines of context on each side of an error location, for the windowed fix prompt


class AgentState(TypedDict):
    name: str
    model: str
    round: int
    max_rounds: int
    reasoning: bool | None
    errors: list[str]
    fix_history: list[str]
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
    result = generate_completion(state["name"], state["model"], reasoning=state["reasoning"])
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
    with timed(f"debug round {state['round']}"):
        errors = check_world(_html_path(state["name"]))
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
    return {"errors": errors}


_FIX_SYSTEM = (
    "You are fixing a self-contained Three.js world.html file. You will be "
    "given a list of problems and either the complete current file or, for "
    "runtime problems with a known source location, only a windowed excerpt "
    "around each one (the file may be hundreds of lines; you don't need the "
    "whole thing to fix a specific throw). Each problem is tagged:\n"
    "  [structure] — generation artifact: truncated JS, leftover markdown "
    "fences (```html), two drafts glued together, unclosed <script>, or "
    "prose leaked into the file. The document is not valid and cannot be "
    "fixed by patching around the damage. You'll be shown the complete file "
    "for this case. Call write_world_html with ONE complete HTML file from "
    "<!DOCTYPE html> to </html>.\n"
    "  [uncaught] / [console.error] / [navigation] — browser runtime error. "
    "Call str_replace with the exact old text and the corrected replacement. "
    "If you were shown a windowed excerpt, its lines are prefixed with "
    "`NNNNN: ` for your own orientation only — old_str/new_str must be the "
    "exact source text WITHOUT that line-number prefix. Prefer several small "
    "str_replace calls over one large rewrite — you may call it up to "
    f"{MAX_TOOL_CALLS_PER_FIX_ROUND} times in this turn if the fix needs more "
    "than one edit. If str_replace reports old_str wasn't found or wasn't "
    "unique, look again and retry with more context.\n"
    "Stop calling tools once you believe every listed problem is fixed."
)

_LOCATION_RE = re.compile(r"\(line (\d+)(?:, col \d+)?\)")


def _error_line_numbers(errors: list[str]) -> list[int]:
    lines = []
    for e in errors:
        m = _LOCATION_RE.search(e)
        if m:
            lines.append(int(m.group(1)))
    return lines


def _build_fix_context(html: str, errors: list[str]) -> tuple[str, bool]:
    """Return (text_shown_to_model, is_full_file).

    The common case — a runtime problem with a known `(line N)` location and
    no [structure] problem alongside it — gets only a windowed excerpt
    (+/- FIX_CONTEXT_LINES) around each error, not the whole file: that's
    the actual point of this function, industry-standard for a coding
    harness working against files far larger than any one bug. Falls back
    to the complete file in the two cases where a window genuinely isn't
    enough: any [structure] problem present (the whole document is what's
    broken, a full rewrite needs to see all of it), or no error in this
    batch carries a location to window around at all.
    """
    if any(e.startswith("[structure]") for e in errors):
        return html, True

    line_numbers = _error_line_numbers(errors)
    if not line_numbers:
        return html, True

    lines = html.split("\n")
    total = len(lines)
    windows = sorted([max(1, n - FIX_CONTEXT_LINES), min(total, n + FIX_CONTEXT_LINES)] for n in set(line_numbers))
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


@traceable(name="generate::fix_node", run_type="chain")
def _fix_node(state: AgentState) -> dict:
    html_path = _html_path(state["name"])
    current_html = html_path.read_text(encoding="utf-8")
    errors_text = "\n".join(f"- {e}" for e in state["errors"][:MAX_ERRORS_IN_PROMPT])

    written: dict[str, str] = {}
    edits: list[tuple[str, str]] = []

    @tool
    def write_world_html(content: str) -> str:
        """Replace the entire file — only for [structure] problems (a document that isn't valid HTML/JS at all)."""
        written["content"] = content
        return "OK: file replaced."

    @tool
    def str_replace(old_str: str, new_str: str) -> str:
        """Replace one exact, unique occurrence of old_str with new_str — for [uncaught]/[console.error]/[navigation] problems."""
        nonlocal current_html
        count = current_html.count(old_str)
        if count == 0:
            return "ERROR: old_str not found in the current file. Check exact text/whitespace and retry."
        if count > 1:
            return f"ERROR: old_str matches {count} places, not 1. Include more surrounding context to make it unique."
        current_html = current_html.replace(old_str, new_str, 1)
        edits.append((old_str, new_str))
        return "OK: edit applied."

    context_text, is_full_file = _build_fix_context(current_html, state["errors"])
    total_lines = current_html.count("\n") + 1
    if is_full_file:
        file_block = f"Current world.html (complete, {total_lines} lines):\n```html\n{context_text}\n```"
        available_tools = [str_replace, write_world_html]
    else:
        shown_lines = context_text.count("\n") + 1
        file_block = (
            f"Current world.html is {total_lines} lines — showing only the excerpt(s) "
            f"below, around each reported error location:\n\n{context_text}"
        )
        available_tools = [str_replace]  # a windowed round physically cannot rewrite the whole file
        log(
            f"[fix]    round {state['round']}: sending {shown_lines} context line(s) "
            f"instead of the full {total_lines}-line file"
        )

    history_note = ""
    if state["fix_history"]:
        history_note = (
            "Previous attempts this session (do not repeat an edit that didn't "
            "fix the problem — diagnose why it's still failing instead):\n"
            + "\n".join(state["fix_history"])
            + "\n\n"
        )

    messages = [
        SystemMessage(content=_FIX_SYSTEM),
        HumanMessage(content=f"{history_note}Problems:\n{errors_text}\n\n{file_block}"),
    ]

    reasoning_chunks: list[str] = []
    tool_names_used: list[str] = []
    hit_cap = True
    for call_n in range(MAX_TOOL_CALLS_PER_FIX_ROUND):
        with timed(f"fix round {state['round']} · turn {call_n + 1}/{MAX_TOOL_CALLS_PER_FIX_ROUND}"):
            turn = invoke_turn(
                state["model"],
                messages,
                temperature=0.2,
                max_tokens=None,
                reasoning=bool(state["reasoning"]),
                tools=available_tools,
            )
        if turn.reasoning_content:
            reasoning_chunks.append(turn.reasoning_content)
        if not turn.tool_calls:
            hit_cap = False
            break

        ai_kwargs = {"reasoning_content": turn.reasoning_content} if turn.reasoning_content else {}
        messages.append(AIMessage(content=turn.text, tool_calls=turn.tool_calls, additional_kwargs=ai_kwargs))
        available_names = {t.name for t in available_tools}
        for call in turn.tool_calls:
            tool_names_used.append(call["name"])
            # Not just a lookup table — an actual gate. A windowed round only
            # binds str_replace (see is_full_file above), but nothing stops a
            # model from emitting a tool_call for a tool it read about in the
            # system prompt text yet was never bound this round (seen for
            # real on a free-tier model). Dispatching by name alone would
            # silently defeat that guarantee; reject it here instead.
            if call["name"] not in available_names:
                result = (
                    f"ERROR: {call['name']} is not available this round "
                    f"(only {sorted(available_names)} are bound) — you were shown a windowed "
                    "excerpt, not the full file, so a full rewrite isn't possible here."
                )
            elif call["name"] == "str_replace":
                try:
                    result = str_replace.invoke(call["args"])
                except Exception as exc:  # noqa: BLE001 — a malformed tool call shouldn't kill the round
                    result = f"ERROR: str_replace call was malformed ({exc}); retry with old_str/new_str string args."
            elif call["name"] == "write_world_html":
                try:
                    result = write_world_html.invoke(call["args"])
                except Exception as exc:  # noqa: BLE001 — a malformed tool call shouldn't kill the round
                    result = f"ERROR: write_world_html call was malformed ({exc}); retry with a content string arg."
            else:
                result = f"ERROR: unknown tool {call['name']!r}"
            log(f"[fix]    round {state['round']}: {call['name']}() -> {result}")
            messages.append(ToolMessage(content=result, tool_call_id=call["id"]))

        if "content" in written:
            hit_cap = False
            break  # a full rewrite makes further str_replace calls against stale content meaningless
    if hit_cap:
        log(f"[fix]    round {state['round']}: hit the {MAX_TOOL_CALLS_PER_FIX_ROUND}-tool-call cap without the model stopping on its own")

    fix_reasoning = "\n".join(reasoning_chunks)

    if "content" in written:
        html_path.write_text(written["content"], encoding="utf-8")
        note = f"round {state['round']}: full rewrite (write_world_html) for a [structure] problem"
        log(f"[fix]    {note}")
        _print_output_block(f"fixed output, round {state['round']}", written["content"])
    elif edits:
        html_path.write_text(current_html, encoding="utf-8")
        note = f"round {state['round']}: {len(edits)} str_replace edit(s) applied"
        log(f"[fix]    {note} to {html_path}")
        for old, new in edits:
            log(f"         - {len(old)} chars -> {len(new)} chars")
        _print_output_block(f"fixed output, round {state['round']}", current_html)
    else:
        note = f"round {state['round']}: no edits made (tools called: {tool_names_used or 'none'})"
        log(f"[fix]    {note}")

    _tag_current_run(
        round_n=state["round"],
        context_mode="full_file" if is_full_file else "windowed",
        tool_call_turns=call_n + 1,  # LLM turns spent inside this one fix round, not to be confused with the outer round count
        max_tool_call_turns=MAX_TOOL_CALLS_PER_FIX_ROUND,
        hit_tool_call_cap=hit_cap,
        tools_used=tool_names_used,
        edits_applied=len(edits),
        full_rewrite="content" in written,
        outcome=note,
    )
    return {
        "round": state["round"] + 1,
        "fix_history": state["fix_history"] + [note],
        "_fix_reasoning": fix_reasoning,
    }


def _route_after_debug(state: AgentState) -> str:
    if not state["errors"]:
        return "clean"
    if state["round"] > state["max_rounds"]:
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
    max_rounds: int = DEFAULT_MAX_FIX_ROUNDS,
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
    if reasoning is None:
        reasoning = detect_reasoning(model)
        log(f"[reasoning] auto-detected {model}: {'capable' if reasoning else 'not reasoning-capable'}")

    app = build_graph()
    final_state = app.invoke(
        {
            "name": name,
            "model": model,
            "round": 1,
            "max_rounds": max_rounds,
            "reasoning": reasoning,
            "errors": [],
            "fix_history": [],
        }
    )
    dest = _html_path(name)
    fix_rounds_used = final_state["round"] - 1
    status = "clean" if not final_state["errors"] else "gave_up"
    if final_state["errors"]:
        log(
            f"warn     gave up after {max_rounds} fix round(s); "
            f"{len(final_state['errors'])} error(s) still present in {dest}"
        )
        for e in final_state["errors"]:
            log(f"         {e}")
    else:
        log(f"clean    no console errors after {fix_rounds_used} round(s)")

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
                "max_rounds": max_rounds,
                "fix_rounds_used": fix_rounds_used,
                "status": status,
            }
        )
        run_tree.add_outputs(
            {
                "status": status,
                "fix_rounds_used": fix_rounds_used,
                "max_rounds": max_rounds,
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
    parser.add_argument("name", help='folder to write under inputs/, e.g. "opus-5"')
    parser.add_argument("--model", required=True, help='OpenRouter model id, e.g. "anthropic/claude-opus-5"')
    parser.add_argument("--max-fix-rounds", type=int, default=DEFAULT_MAX_FIX_ROUNDS)
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
    dest = run(args.name, args.model, max_rounds=args.max_fix_rounds, reasoning=reasoning)
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
