"""Shared OpenRouter invocation machinery — no CLI of its own.

Not a pipeline stage by itself; `harness/generate.py` (the LangGraph
generate → debug → fix loop, the only generation entrypoint) is the sole
caller of both public functions here:

- `generate(name, model, ...)` — one full completion of prompts/prompt.md,
  with the continuation-round/checkpoint handling described below. Used by
  the graph's `generate` node.
- `invoke_turn(model, messages, ...)` — one raw model turn, optionally
  tool-bound, with the exact same live reasoning-stream printing and
  generation-stats logging as `generate()` gets. Used by the graph's `fix`
  node so a tool-calling fix round is exactly as visible on stderr as a
  generation round — no separate, quieter code path for "the model is
  fixing something" vs. "the model is generating something".

No fixed request timeout is imposed here — every model paces differently,
so we let each request run to completion and instead report what OpenRouter
itself measured for it (prompt/completion tokens, generation time) once
it's done, via the /generation stats endpoint. A dropped connection
mid-stream (intermediate proxy/load balancer hiccup, seen on real long
reasoning runs) retries that one turn up to twice rather than losing
everything already streamed.

Some providers cut a response off mid-file when it hits their own default
output-length cap (`finish_reason: "length"`), independent of any timeout —
this happened for real on stealth/ox-alpha and produced a broken,
unparseable world.html. Rather than trust a single turn, generate() checks
completion after every turn (finish_reason plus a `</html>` presence check)
and, if incomplete, sends the accumulated output plus reasoning back as
conversation history and asks the model to continue exactly where it
stopped — up to 3 turns total. If it's still incomplete after that, nothing
is written to inputs/<name>/world.html; the accumulated content + reasoning
is checkpointed to outputs/<name>/generation.json instead, and re-running
the same command picks up from that checkpoint rather than starting over.

Every turn is traced with LangSmith (`model_call::turn`, see `invoke_turn`
below) — no-ops without LANGSMITH_TRACING=true + LANGSMITH_API_KEY.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import string
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
load_dotenv(REPO_ROOT / ".env")

import httpx  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402
from langchain_openrouter import ChatOpenRouter  # noqa: E402
from langsmith import traceable  # noqa: E402
from openrouter import OpenRouter as OpenRouterClient  # noqa: E402
from openrouter import errors as openrouter_errors  # noqa: E402

from harness.status import log, timed  # noqa: E402

PROMPT_PATH = REPO_ROOT / "prompts" / "prompt.md"
INPUTS_DIR = REPO_ROOT / "inputs"
OUTPUTS_DIR = REPO_ROOT / "outputs"

_FENCE_LINE_RE = re.compile(r"^```[a-zA-Z]*\s*$")

# npm-style lowercase tag + a distinct style for the reasoning stream itself,
# so it reads as "the model thinking out loud" rather than plain log output.
_USE_COLOR = sys.stderr.isatty() and os.environ.get("NO_COLOR") is None
_REASONING_BADGE = "\033[7;1;35m reasoning \033[0m" if _USE_COLOR else "reasoning:"
_REASONING_STYLE = "\033[3;2;38;5;245m" if _USE_COLOR else ""  # italic, dim, true gray (256-color, not terminal-dependent "blue-ish" dim white)
_HIGHLIGHT_STYLE = "\033[1;38;5;215m" if _USE_COLOR else ""  # bold amber — pops out of the gray body
_CODE_STYLE = "\033[2;38;5;80m" if _USE_COLOR else ""  # dim teal — inline `code` and ``` fenced ``` blocks
_BOLD_STYLE = "\033[1;38;5;252m" if _USE_COLOR else ""  # bold near-white — **markdown emphasis**
_RESET = "\033[0m" if _USE_COLOR else ""

# Vocabulary this project's reasoning traces actually revolve around — the
# canonical biomes (BiomeGraph.tsx, mirrored in tests/WC001*/biome_check.py)
# plus the voxel/Three.js building blocks the prompt asks for. Highlighted
# inline so a skimmed reasoning stream still shows *what* the model is
# actually deciding on, not just that text is flowing.
# _HIGHLIGHT_TERMS = frozenset(
#     {
#         # biomes (BiomeGraph.tsx)
#         "mountains", "forest", "highlands", "jungle", "swamp", "grove",
#         "grassland", "grasslands", "delta", "desert", "volcano",
#         # world features named in prompts/prompt.md
#         "ocean", "beach", "beaches", "cliff", "cliffs", "waterfall",
#         "waterfalls", "river", "rivers", "lava", "snow", "blizzard",
#         "sandstorm", "obsidian",
#         # voxel / three.js build vocabulary
#         "three.js", "threejs", "orbitcontrols", "voxel", "voxels", "shader",
#         "geometry", "texture", "lighting", "camera", "mesh", "canvas",
#         "webgl", "particle", "particles", "cube", "cubes",
#     }
# )


class _ReasoningPrinter:
    """Prints reasoning deltas to stderr, styled apart from other log output.

    Deltas arrive as arbitrary chunks that can split a word (or a markdown
    delimiter) across two calls, so parsing can't just regex each delta
    independently — that would light up "moun" and "tains" as two unmatched
    fragments, or miss a ``` split across a chunk boundary. Instead this
    buffers up to the last split boundary (whitespace or a markdown
    delimiter) and only classifies complete tokens.

    Markdown the model reasons in — `inline code`, ``` fenced ``` blocks,
    **bold** — is interpreted rather than printed as literal punctuation:
    delimiters are stripped and swap the active style instead of appearing
    as raw backticks/asterisks in the stream.
    """

    _SPLIT_RE = re.compile(r"(\s+|```|\*\*|`)")

    def __init__(self) -> None:
        self._buffer = ""
        self.opened = False
        self._in_fence = False
        self._in_code = False
        self._in_bold = False

    def _open(self) -> None:
        print(f"\n{_REASONING_BADGE}", file=sys.stderr)
        print(_REASONING_STYLE, end="", file=sys.stderr, flush=True)
        self.opened = True

    def _active_style(self) -> str:
        if self._in_bold:
            return _BOLD_STYLE
        if self._in_fence or self._in_code:
            return _CODE_STYLE
        return _REASONING_STYLE

    def _emit(self, token: str) -> None:
        if token == "```":
            self._in_fence = not self._in_fence
            print(self._active_style(), end="", file=sys.stderr, flush=True)
            return
        if token == "`" and not self._in_fence:
            self._in_code = not self._in_code
            print(self._active_style(), end="", file=sys.stderr, flush=True)
            return
        if token == "**":
            self._in_bold = not self._in_bold
            print(self._active_style(), end="", file=sys.stderr, flush=True)
            return
        if self._in_fence or self._in_code:
            print(token, end="", file=sys.stderr, flush=True)  # code stays in code style, no term-highlighting
            return
        print(token, end="", file=sys.stderr, flush=True)

    def feed(self, delta: str) -> None:
        if not delta:
            return
        if not self.opened:
            self._open()
        self._buffer += delta
        # A trailing run of 1-2 backticks might still grow into a ``` fence
        # once more of the stream arrives (e.g. "``" then "`js" in the next
        # chunk) — the regex below would otherwise split "``" into two lone
        # `-tokens right now, desyncing in_code/in_fence before the third
        # backtick ever shows up. Hold the whole ambiguous run back instead.
        hold = ""
        body = self._buffer
        stripped = body.rstrip("`")
        trailing = len(body) - len(stripped)
        if 0 < trailing < 3:
            hold, body = body[len(stripped):], stripped
        parts = self._SPLIT_RE.split(body)
        self._buffer = parts[-1] + hold
        for part in parts[:-1]:
            if part:
                self._emit(part)

    def close(self) -> None:
        if self._buffer:
            for part in self._SPLIT_RE.split(self._buffer):
                if part:
                    self._emit(part)
            self._buffer = ""
        if self.opened:
            print(f"{_RESET}\n", file=sys.stderr)


_PREFIX_OK_RE = re.compile(r"<!DOCTYPE\s+html\b|<html\b|<head\b", re.I)


def _extract_html(text: str) -> str:
    """Unwrap a wrapping ```html fence if the model added one.

    A fence on the first line, or right after a doctype/html-open prefix
    (stealth/ox-alpha emits `<!DOCTYPE html>` then an opening fence), is
    wrapping and gets stripped. A fence *after* the document has started
    (mid-script ``const w = Math.max(8*`` then ```html) is a restart —
    two drafts glued together — and is left in the file so world_lint
    can send it to the fix loop. Stripping every fence-only line used to
    delete that restart marker and silently concatenate the two drafts.
    """
    lines = text.strip("\n").split("\n")
    if lines and _FENCE_LINE_RE.match(lines[0].strip()):
        lines = lines[1:]
    else:
        prefix_at = None
        for i, line in enumerate(lines[:8]):
            stripped = line.strip()
            if not stripped:
                continue
            if _FENCE_LINE_RE.match(stripped):
                prefix_at = i
                break
            if not _PREFIX_OK_RE.match(stripped):
                break
        if prefix_at is not None:
            lines = lines[:prefix_at] + lines[prefix_at + 1 :]
    if lines and _FENCE_LINE_RE.match(lines[-1].strip()):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def detect_reasoning(model: str) -> bool | None:
    """Public wrapper — see _is_reasoning_model. Used by callers (e.g. the
    fix node) that want the same auto-detected reasoning-visibility
    behavior generate() gets, without duplicating the catalog lookup."""
    return _is_reasoning_model(model)


def _is_reasoning_model(model: str) -> bool | None:
    """Ask OpenRouter's catalog whether `model` is reasoning-capable.

    `Model.reasoning` (per the OpenRouter SDK) is populated only for
    reasoning-capable models and omitted for everything else, so this is
    catalog fact, not a name-pattern guess. Returns None on lookup failure
    (unknown slug, network hiccup, no API key yet) so the caller can decide
    whether to fall back to plain generation rather than fail generation
    outright over a catalog lookup.
    """
    if "/" not in model:
        return None
    author, slug = model.split("/", 1)
    try:
        client = OpenRouterClient(api_key=os.environ.get("OPENROUTER_API_KEY"))
        info = client.models.get(author=author, slug=slug)
    except Exception as exc:  # noqa: BLE001 — best-effort catalog probe, never fatal
        log(f"warn     could not look up {model!r} on OpenRouter ({exc}); assuming non-reasoning")
        return None
    return info.data.reasoning is not None


def _fetch_generation_stats(generation_id: str, *, attempts: int = 6) -> dict | None:
    """Pull token counts + generation time for `generation_id` from OpenRouter.

    OpenRouter's /generation endpoint isn't indexed the instant a completion
    finishes — a request right after the call routinely 404s for several
    seconds — so retry with backoff rather than giving up on the first miss.
    Returns None (never raises) if stats still aren't available after all
    attempts; they're a nice-to-have report, not something generation
    should fail over.
    """
    client = OpenRouterClient(api_key=os.environ.get("OPENROUTER_API_KEY"))
    for attempt in range(attempts):
        try:
            data = client.generations.get_generation(id=generation_id).data
        except openrouter_errors.OpenRouterError:
            if attempt + 1 < attempts:
                time.sleep(1.0 + attempt)  # 1, 2, 3, 4, 5s — ~15s total headroom
                continue
            return None
        return {
            "prompt_tokens": data.native_tokens_prompt,
            "completion_tokens": data.native_tokens_completion,
            "reasoning_tokens": data.native_tokens_reasoning,
            "generation_time_ms": data.generation_time,
        }
    return None


def _log_generation_stats(generation_id: str | None) -> None:
    if not generation_id:
        log("stats    no generation id returned; skipping OpenRouter usage lookup")
        return
    stats = _fetch_generation_stats(generation_id)
    if stats is None:
        log(f"stats    OpenRouter had no usage yet for {generation_id}")
        return
    prompt_t = stats["prompt_tokens"] or 0
    completion_t = stats["completion_tokens"] or 0
    reasoning_t = stats["reasoning_tokens"] or 0
    gen_time_s = (stats["generation_time_ms"] or 0) / 1000
    total_t = prompt_t + completion_t
    extra = f"  (of which reasoning {reasoning_t})" if reasoning_t else ""
    log(
        f"stats    tokens {total_t} (prompt {prompt_t} + completion {completion_t}){extra}"
        f"  |  generation time {gen_time_s:.1f}s"
    )


# Long reasoning generations (tens of minutes of streaming) occasionally get
# cut by an intermediate proxy/load balancer closing the connection before
# the response finishes — an infra hiccup, not a bad request — so it's worth
# retrying that one turn rather than losing everything already streamed.
_TRANSIENT_ERRORS = (httpx.TransportError,)
_MAX_RETRIES = 2

# langchain_openrouter raises a plain ValueError for ANY mid-stream error
# OpenRouter's own API surfaces (chat_models.py's `_stream`), wrapping
# whatever HTTP-style code the provider reported into the message text —
# there's no dedicated exception type to catch. Seen for real on a long
# reasoning fix-round: "...Upstream idle timeout exceeded (code: 504)",
# a transient upstream hiccup identical in kind to the httpx.TransportError
# case above, just from a different layer. Only retry the codes that are
# actually transient (502/503/504 gateway-ish failures) — a ValueError for
# a genuine 4xx (bad request, content policy, etc.) should still fail fast.
_TRANSIENT_STREAM_ERROR_RE = re.compile(r"\(code:\s*50[234]\)")


def _is_transient_stream_error(exc: Exception) -> bool:
    return isinstance(exc, ValueError) and bool(_TRANSIENT_STREAM_ERROR_RE.search(str(exc)))


# When a transient error kills a stream partway through, a long-reasoning
# model may already have spent 5-10 minutes thinking before the connection
# dropped. Blindly resending the original request throws that thinking away
# and pays for it again. Instead, splice whatever was accumulated (content +
# reasoning_content) back in as one exchange and ask the model to continue —
# the exact same "resume, don't restart" shape generate()'s own
# truncation-recovery already uses, just triggered by a dropped connection
# instead of a length cap. Scoped to this one invoke_turn() call only: never
# written to disk, never carried past this process.
_INTERRUPTED_CONTINUE_INSTRUCTION = (
    "The connection dropped partway through your last response. Continue "
    "exactly from where you left off — do not restart your reasoning or "
    "repeat anything already said."
)


def _splice_partial_turn(messages: list, full) -> list:
    """Return `messages` with whatever `full` (a possibly-partial AIMessageChunk,
    or None) accumulated appended as a continuation exchange."""
    if full is None:
        return messages
    partial_text = full.content if isinstance(full.content, str) else str(full.content or "")
    partial_reasoning = full.additional_kwargs.get("reasoning_content")
    if not partial_text and not partial_reasoning:
        return messages
    ai_kwargs = {"reasoning_content": partial_reasoning} if partial_reasoning else {}
    return messages + [
        AIMessage(content=partial_text, additional_kwargs=ai_kwargs),
        HumanMessage(content=_INTERRUPTED_CONTINUE_INSTRUCTION),
    ]


@dataclass
class TurnResult:
    text: str
    reasoning_content: str | None
    reasoning_details: object
    finish_reason: str | None
    generation_id: str | None
    tool_calls: list = field(default_factory=list)


@traceable(name="model_call::turn", run_type="llm")
def invoke_turn(
    model: str,
    messages: list,
    *,
    temperature: float,
    max_tokens: int | None,
    reasoning: bool,
    tools: list | None = None,
) -> TurnResult:
    """One model turn, optionally tool-bound. Streams + prints reasoning live
    (see _ReasoningPrinter) whenever reasoning=True — a tool-calling turn
    (the fix loop) gets exactly the same live chain-of-thought visibility on
    stderr as a plain generation turn, not a quieter black-box path.

    Traced as a LangSmith `llm` run either way: with LANGSMITH_TRACING unset
    this call costs nothing extra, but when it's on, the full reasoning
    trace, output text, and any tool call made are all recorded on this run
    — nothing about a turn is only visible in the terminal.
    """
    for attempt in range(_MAX_RETRIES + 1):
        common = dict(model=model, temperature=temperature, max_tokens=max_tokens)
        full = None  # set only on the reasoning/streaming path below; stays None otherwise
        try:
            if not reasoning:
                llm = ChatOpenRouter(**common)
                if tools:
                    llm = llm.bind_tools(tools)
                result = llm.generate([messages])
                message = result.generations[0][0].message
                content = message.content
                text = content if isinstance(content, str) else str(content)
                return TurnResult(
                    text,
                    None,
                    None,
                    message.response_metadata.get("finish_reason"),
                    message.response_metadata.get("id"),
                    list(getattr(message, "tool_calls", None) or []),
                )

            llm = ChatOpenRouter(streaming=True, reasoning={"enabled": True}, **common)
            if tools:
                llm = llm.bind_tools(tools)
            printer = _ReasoningPrinter()
            # AIMessageChunk accumulated via __add__, which merges content/reasoning/tool_call_chunks/metadata for us
            try:
                for chunk in llm.stream(messages):
                    printer.feed(chunk.additional_kwargs.get("reasoning_content") or "")
                    full = chunk if full is None else full + chunk
            finally:
                printer.close()  # always reset the terminal style, even if the stream dies mid-word
            content = full.content if isinstance(full.content, str) else str(full.content)
            return TurnResult(
                content,
                full.additional_kwargs.get("reasoning_content"),
                full.additional_kwargs.get("reasoning_details"),
                full.response_metadata.get("finish_reason"),
                full.response_metadata.get("id"),
                list(full.tool_calls or []),
            )
        except _TRANSIENT_ERRORS as exc:
            if attempt >= _MAX_RETRIES:
                raise
            carried = full is not None and (full.content or full.additional_kwargs.get("reasoning_content"))
            log(
                f"warn     connection dropped mid-generation ({exc}); "
                + (
                    f"carrying forward {len(str(full.content or ''))} chars + reasoning already produced; "
                    if carried
                    else ""
                )
                + f"retrying this turn ({attempt + 1}/{_MAX_RETRIES})"
            )
            messages = _splice_partial_turn(messages, full)
        except ValueError as exc:
            if not _is_transient_stream_error(exc) or attempt >= _MAX_RETRIES:
                raise
            carried = full is not None and (full.content or full.additional_kwargs.get("reasoning_content"))
            log(
                f"warn     transient upstream error mid-stream ({exc}); "
                + (
                    f"carrying forward {len(str(full.content or ''))} chars + reasoning already produced; "
                    if carried
                    else ""
                )
                + f"retrying this turn ({attempt + 1}/{_MAX_RETRIES})"
            )
            messages = _splice_partial_turn(messages, full)
    raise AssertionError("unreachable")


# A response can end up incomplete either because the provider truncated it
# (finish_reason == "length") or, less reliably, because a provider just
# doesn't populate finish_reason correctly — so also check for the closing
# tag the prompt requires every real output to end with.
_MAX_ROUNDS = 3
_CONTINUE_INSTRUCTION = (
    "Your previous reply was cut off before the file was finished. Continue "
    "the HTML file starting at the exact next character after where you "
    "stopped. Do not repeat any earlier text, do not restart, do not add "
    "prose, commentary, or code fences — output only the raw continuation, "
    "so that concatenating it directly onto your previous output "
    "reconstructs the complete, valid file."
)


def _looks_complete(html: str, finish_reason: str | None) -> bool:
    if finish_reason == "length":
        return False
    return "</html>" in html[-2000:].lower()


def _state_path(name: str) -> Path:
    return OUTPUTS_DIR / name / "generation.json"


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _load_state(name: str, model: str, prompt_hash: str) -> dict | None:
    path = _state_path(name)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("model") != model or data.get("prompt_sha256") != prompt_hash:
        log(f"warn     checkpoint at {path} is for a different model/prompt; starting fresh")
        return None
    return data


def _save_state(
    name: str,
    *,
    model: str,
    prompt_hash: str,
    content: str,
    reasoning_content: str,
    reasoning_details: object,
    finish_reason: str | None,
    generation_ids: list[str],
    round_n: int,
) -> None:
    path = _state_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "model": model,
                "prompt_sha256": prompt_hash,
                "round": round_n,
                "finish_reason": finish_reason,
                "generation_ids": generation_ids,
                "content": content,
                "reasoning_content": reasoning_content,
                "reasoning_details": reasoning_details,
                "saved_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _clear_state(name: str) -> None:
    path = _state_path(name)
    if path.is_file():
        path.unlink()


@dataclass
class GenerationResult:
    path: Path
    html: str
    reasoning_content: str
    generation_ids: list[str]
    rounds: int


def generate(
    name: str,
    model: str,
    *,
    temperature: float = 1.0,
    max_tokens: int | None = None,
    reasoning: bool | None = None,
) -> GenerationResult:
    """Call `model` on OpenRouter with prompts/prompt.md, write inputs/<name>/world.html.

    reasoning=None (default) auto-detects via OpenRouter's model catalog and
    streams reasoning tokens live when `model` turns out to be
    reasoning-capable; pass True/False to force it either way without a
    catalog lookup.

    Up to _MAX_ROUNDS turns: if a turn comes back incomplete (see
    _looks_complete), the accumulated output + reasoning is sent back as
    conversation history and the model is asked to continue exactly where
    it stopped. If a matching checkpoint exists at outputs/<name>/generation.json
    from a prior incomplete run, that's resumed from instead of starting over.

    Returns a GenerationResult (written path + the full html/reasoning, so
    the caller can log or trace them without re-reading the file) with
    inputs/<other>/ folders untouched, so `uv run python -m eval.run <other>`
    keeps working against whatever was ingested there before. Raises if
    still incomplete after _MAX_ROUNDS — nothing is written to
    inputs/<name>/world.html in that case, since a half-file there is worse
    than no file (it silently fails downstream checks instead of failing
    loudly here).
    """
    if reasoning is None:
        reasoning = bool(_is_reasoning_model(model))

    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    prompt_hash = _prompt_hash(prompt)

    state = _load_state(name, model, prompt_hash)
    if state:
        content = state["content"]
        reasoning_content = state.get("reasoning_content") or ""
        reasoning_details = state.get("reasoning_details")
        generation_ids = state.get("generation_ids", [])
        round_n = state.get("round", 0)
        log(f"resume   found checkpoint for {name} (round {round_n}/{_MAX_ROUNDS}, {len(content)} chars so far); continuing")
    else:
        content, reasoning_content, reasoning_details = "", "", None
        generation_ids, round_n = [], 0

    finish_reason = state.get("finish_reason") if state else None
    while round_n < _MAX_ROUNDS:
        round_n += 1
        if content:
            ai_kwargs = {}
            if reasoning_content:
                ai_kwargs["reasoning_content"] = reasoning_content
            if reasoning_details:
                ai_kwargs["reasoning_details"] = reasoning_details
            messages = [
                HumanMessage(content=prompt),
                AIMessage(content=content, additional_kwargs=ai_kwargs),
                HumanMessage(content=_CONTINUE_INSTRUCTION),
            ]
        else:
            messages = [HumanMessage(content=prompt)]

        with timed(f"generate {name} round {round_n}/{_MAX_ROUNDS} ({model}){' [reasoning]' if reasoning else ''}"):
            turn = invoke_turn(
                model, messages, temperature=temperature, max_tokens=max_tokens, reasoning=reasoning
            )
        content += turn.text
        if turn.reasoning_content:
            reasoning_content = (
                f"{reasoning_content}\n{turn.reasoning_content}" if reasoning_content else turn.reasoning_content
            )
        if turn.reasoning_details:
            reasoning_details = turn.reasoning_details
        if turn.generation_id:
            generation_ids.append(turn.generation_id)
        finish_reason = turn.finish_reason

        complete = _looks_complete(content, finish_reason)
        log(f"round    {round_n}/{_MAX_ROUNDS}  +{len(turn.text)} chars  finish_reason={finish_reason}  {'complete' if complete else 'incomplete'}")
        if complete:
            break
        _save_state(
            name,
            model=model,
            prompt_hash=prompt_hash,
            content=content,
            reasoning_content=reasoning_content,
            reasoning_details=reasoning_details,
            finish_reason=finish_reason,
            generation_ids=generation_ids,
            round_n=round_n,
        )

    for gid in generation_ids:
        _log_generation_stats(gid)

    if not _looks_complete(content, finish_reason):
        log(f"error    still incomplete after {_MAX_ROUNDS} round(s); checkpoint saved to {_state_path(name)}")
        log("         re-run the same command to resume from this checkpoint")
        raise RuntimeError(f"generation for {name!r} did not complete after {_MAX_ROUNDS} rounds")

    _clear_state(name)
    html = _extract_html(content)
    from harness.world_lint import lint_world_html  # local: avoid import cycle at module load

    structure = lint_world_html(html)
    if structure:
        log(
            f"warn     generated file has {len(structure)} structure finding(s); "
            "debug/fix will try to rewrite it"
        )
        for finding in structure[:5]:
            log(f"         {finding}")

    dest_dir = INPUTS_DIR / name
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "world.html"
    dest.write_text(html, encoding="utf-8")
    return GenerationResult(
        path=dest,
        html=html,
        reasoning_content=reasoning_content,
        generation_ids=generation_ids,
        rounds=round_n,
    )
