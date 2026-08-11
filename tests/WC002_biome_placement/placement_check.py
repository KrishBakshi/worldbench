"""Does each biome's placement on the island respect the ecological/
water-flow graph in worldbench-web/components/about/BiomeGraph.tsx (a
spoiler file, never shown to the model)?

Two phases, deliberately split:

1. Extraction (LLM, OpenRouter via LangChain): read the raw world.html
   source and report, per biome, which other biomes it's adjacent to in
   the terrain plus a global elevation ordering (highest to lowest) —
   each claim grounded in cited source evidence (a coordinate, a
   comment, a generation-order clue). Bespoke per-model source structure
   (confirmed by a dry-run experiment: coordinate data ranges from a
   clean array, to camera-preset targets, to nothing at all for
   grid-fill-generated terrain) makes this unregexable — the LLM's job
   here is narrow and checkable, not open-ended judgment.
2. Grading (deterministic, this file, no LLM): compare the extracted
   graph against RULES, the same reference graph as connectivity/
   ordering predicates. Nothing about "is this correct" is left to the
   LLM — it only ever reports what it found in the source.
"""

from __future__ import annotations

import json
import os
import queue
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

load_dotenv()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL")

# Reasoning-capable models (e.g. the nemotron ":free"/"reasoning" variants)
# spend a large share of their token budget on chain-of-thought before the
# actual tool call — a low max_tokens cap truncates the response before it
# ever reaches the answer. Generous on purpose; raise further if a future
# model's reasoning trace is even longer.
MAX_TOKENS = 8000

# Rough, ad hoc run artifacts (not the real harness/outputs/ pipeline) —
# see the __main__ block below. dry_runs/ is where all dry-run/experimental
# activity lives, per CLAUDE.md.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RUNS_DIR = REPO_ROOT / "dry_runs" / "wc002_runs"

BiomeId = Literal[
    "mountains", "forest", "highlands", "jungle", "swamp",
    "grove", "grassland", "delta", "desert", "volcano",
]

# Canonical biomes, same ids/labels as tests/WC001_trying_all_the_biomes/biome_check.py.
BIOME_LABELS: dict[str, str] = {
    "mountains": "Snow Mountains",
    "forest": "Snowy Conifer Forest",
    "highlands": "Highlands",
    "jungle": "Dense Jungle",
    "swamp": "Backwater Swamp",
    "grove": "Flowering Grove",
    "grassland": "Grassland Plateau",
    "delta": "Coastal Delta / Ocean",
    "desert": "Desert Basin",
    "volcano": "Volcano",
}

# Reference graph (BiomeGraph.tsx), restated as checkable predicates —
# one entry per biome, evaluated independently for 1-point-each scoring.
# higher_than: this biome must rank at a strictly higher elevation than each listed one.
RULES: dict[str, dict] = {
    "mountains": {"must_connect": ["forest"], "higher_than": ["forest", "highlands", "jungle", "grassland", "delta"]},
    "forest": {"must_connect": ["mountains", "highlands"], "higher_than": ["highlands", "jungle", "grassland", "delta"]},
    "highlands": {"must_connect": ["forest", "jungle"], "higher_than": ["jungle", "grassland", "delta"]},
    "jungle": {"must_connect": ["highlands", "grassland", "swamp"], "higher_than": ["grassland", "delta"]},
    "swamp": {"must_connect": ["jungle"], "must_not_connect": ["delta"]},
    "grove": {"must_connect_any": ["highlands", "grassland"]},
    "grassland": {"must_connect": ["jungle", "delta"], "higher_than": ["delta"]},
    "delta": {"must_connect": ["grassland"]},
    "desert": {"must_not_connect": ["mountains", "forest", "highlands", "jungle", "delta"]},
    "volcano": {"must_not_connect": ["mountains", "forest", "highlands", "grassland", "delta"]},
}


@dataclass
class CheckResult:
    passed: bool
    reason: str
    details: dict = field(default_factory=dict)


class BiomeNode(BaseModel):
    id: BiomeId
    neighbors: list[BiomeId] = Field(
        description="ids of other biomes this one is directly adjacent to / touches in the terrain"
    )
    evidence: str = Field(
        description="what in the source supports this — a coordinate, a comment, a generation-order clue"
    )


class ExtractedGraph(BaseModel):
    nodes: list[BiomeNode]
    elevation_order: list[BiomeId] = Field(
        description="all 10 biome ids ordered from highest elevation/altitude to lowest, "
        "based on the terrain's actual height values or generation logic"
    )


REQUEST_TIMEOUT_S = 120  # fail loudly instead of hanging forever on a slow/overloaded free model


def _client(model: str = OPENROUTER_MODEL) -> ChatOpenAI:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set (see .env.example) — required for placement_check.py")
    return ChatOpenAI(
        model=model,  # was hardcoded to OPENROUTER_MODEL, silently ignoring the model= arg callers pass
        base_url=OPENROUTER_BASE_URL,
        api_key=api_key,
        temperature=0,
        max_tokens=MAX_TOKENS,
        request_timeout=REQUEST_TIMEOUT_S,
        max_retries=1,
    )


def extract_graph(
    html_path: str, model: str = OPENROUTER_MODEL, verbose: bool = True, save: bool = False
) -> ExtractedGraph:
    def log(msg: str) -> None:
        if verbose:
            print(f"[placement_check] {msg}", flush=True)

    log(f"reading {html_path}")
    text = Path(html_path).read_text(encoding="utf-8", errors="ignore")
    biome_list = "\n".join(f"- {bid}: {label}" for bid, label in BIOME_LABELS.items())

    prompt = (
        "This is the source of a procedurally generated Three.js floating-island "
        "scene. It contains exactly these 10 biomes (id: label):\n"
        f"{biome_list}\n\n"
        "For each biome, report which other biomes (by id) it is directly adjacent "
        "to / touches in the generated terrain, citing the specific evidence in the "
        "source you based that on (a coordinate, a comment, a generation-order "
        "clue, an adjacency implied by a fill/flood algorithm). Then report a single "
        "global ordering of all 10 biome ids from highest elevation/altitude to "
        "lowest, based on actual height/elevation values or generation logic in the "
        "source — not the biomes' typical real-world elevation.\n\n"
        f"Source:\n{text}"
    )

    # What we're sending, captured independently of LangChain's internal
    # serialization — the same content it builds its actual wire request
    # from (model, prompt, and the schema with_structured_output derives
    # from ExtractedGraph), saved for audit even though the exact HTTP
    # bytes LangChain sends aren't part of its public API.
    request_record = {
        "model": model,
        "html_path": html_path,
        "max_tokens": MAX_TOKENS,
        "temperature": 0,
        "prompt": prompt,
        "response_schema": ExtractedGraph.model_json_schema(),
    }

    log(f"calling {model} via OpenRouter (hard timeout={REQUEST_TIMEOUT_S}s, max_tokens={MAX_TOKENS})...")
    t0 = time.monotonic()
    # include_raw=True: also get the actual AIMessage the API returned
    # (content, tool_calls, response_metadata, token usage, ...), not just
    # the parsed Pydantic object — that raw message is what gets saved as
    # the response record below.
    llm = _client(model).with_structured_output(ExtractedGraph, include_raw=True)

    # request_timeout on the client is a *soft* idle-read timeout — a slow/
    # queued free-tier model trickling occasional bytes resets it and it
    # never fires (confirmed: a real call ran past 120s with no error). A
    # ThreadPoolExecutor doesn't fix this either — Python can't forcibly
    # kill a thread stuck in a blocking socket read, so waiting on the
    # future would just move the hang to the executor's own shutdown.
    # A daemon thread sidesteps that: the interpreter can abandon it
    # without waiting, so the hard deadline below is real. Heartbeat every
    # 10s so a live call is visibly not the same as a hung one — that
    # feedback is what was missing when this gave no output at all.
    result_queue: queue.Queue = queue.Queue(maxsize=1)

    def _call():
        try:
            result_queue.put(("ok", llm.invoke(prompt)))
        except Exception as e:
            result_queue.put(("error", e))

    worker = threading.Thread(target=_call, daemon=True)
    worker.start()

    while worker.is_alive():
        elapsed = time.monotonic() - t0
        if elapsed >= REQUEST_TIMEOUT_S:
            log(f"no response after {elapsed:.0f}s — giving up (model may be overloaded/queued; try a non-free model)")
            if save:
                run_dir = _save_run(request_record, {"error": f"timed out after {REQUEST_TIMEOUT_S}s, no response"})
                log(f"saved request (timed out, no response) to {run_dir}")
            raise TimeoutError(f"{model} did not respond within {REQUEST_TIMEOUT_S}s")
        worker.join(timeout=10)
        if worker.is_alive():
            log(f"still waiting... {time.monotonic() - t0:.0f}s elapsed")

    status, payload = result_queue.get()
    if status == "error":
        log(f"call failed after {time.monotonic() - t0:.1f}s")
        if save:
            _save_run(request_record, {"error": str(payload)})
        raise payload

    raw_message, parsed, parsing_error = payload["raw"], payload["parsed"], payload["parsing_error"]
    log(f"got response in {time.monotonic() - t0:.1f}s")

    response_record = {
        "elapsed_s": round(time.monotonic() - t0, 1),
        "parsing_error": str(parsing_error) if parsing_error else None,
        "message": raw_message.model_dump(),
    }
    if save:
        run_dir = _save_run(request_record, response_record)
        log(f"saved request/response to {run_dir}")

    if parsing_error is not None or parsed is None:
        raise ValueError(f"model response did not parse as ExtractedGraph: {parsing_error}")
    return parsed


def _save_run(request_record: dict, response_record: dict) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    run_dir = RUNS_DIR / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "request.json").write_text(json.dumps(request_record, indent=2, default=str))
    (run_dir / "response.json").write_text(json.dumps(response_record, indent=2, default=str))
    return run_dir


def grade_graph(graph: ExtractedGraph) -> CheckResult:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for node in graph.nodes:
        for neighbor in node.neighbors:
            adjacency[node.id].add(neighbor)
            adjacency[neighbor].add(node.id)

    rank = {biome_id: i for i, biome_id in enumerate(graph.elevation_order)}

    found: dict[str, str] = {}
    missing: dict[str, str] = {}
    for biome_id, rules in RULES.items():
        ok, why = _grade_biome(biome_id, rules, adjacency, rank)
        if ok:
            found[biome_id] = why
        else:
            missing[biome_id] = why

    score = len(found)
    max_score = len(RULES)
    passed = not missing
    reason = "All biomes correctly placed" if passed else f"Missing {len(missing)}/{max_score} biomes: {', '.join(missing)}"
    return CheckResult(
        passed=passed,
        reason=reason,
        details={"found": found, "missing": missing, "score": score, "max_score": max_score},
    )


def _grade_biome(biome_id: str, rules: dict, adjacency: dict[str, set[str]], rank: dict[str, int]) -> tuple[bool, str]:
    for required in rules.get("must_connect", []):
        if required not in adjacency.get(biome_id, set()):
            return False, f"not connected to {required}"

    if "must_connect_any" in rules:
        options = rules["must_connect_any"]
        if not any(o in adjacency.get(biome_id, set()) for o in options):
            return False, f"not connected to any of {options}"

    for forbidden in rules.get("must_not_connect", []):
        if forbidden in adjacency.get(biome_id, set()):
            return False, f"incorrectly connected to {forbidden}"

    for higher in rules.get("higher_than", []):
        if biome_id not in rank or higher not in rank:
            return False, f"missing elevation data for {biome_id} or {higher}"
        if rank[biome_id] >= rank[higher]:
            return False, f"not at a higher elevation than {higher}"

    return True, "placement consistent with reference graph"


def check_biome_placement(
    html_path: str, model: str = OPENROUTER_MODEL, verbose: bool = True, save: bool = False
) -> CheckResult:
    graph = extract_graph(html_path, model=model, verbose=verbose, save=save)
    if verbose:
        print("[placement_check] grading extracted graph...", flush=True)
    return grade_graph(graph)


if __name__ == "__main__":
    import sys

    # Standalone run = a rough, ad hoc experiment, not the real harness
    # pipeline — save=True here writes request.json/response.json into a
    # fresh dry_runs/wc002_runs/<timestamp>/ directory (see _save_run).
    path = sys.argv[1] if len(sys.argv) > 1 else "/Users/krish/Workspace/worldbench/dry_runs/inputs/deepseek-v4-pro/world.html"
    result = check_biome_placement(path, save=True)
    print(f"\npassed={result.passed} score={result.details['score']}/{result.details['max_score']}")
    print(result.reason)