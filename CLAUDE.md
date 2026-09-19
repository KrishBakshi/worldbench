# worldbench: repo guide for Claude

`worldbench` is the **evaluation harness** sibling to `worldbench-web`
(the **display** site). `worldbench-web` shows off `world.html` outputs
from different models for one prompt (a self-contained Three.js floating
biome island) with no scoring. `worldbench` is where those outputs get
actually **checked** against pass/fail criteria — one test per checkable
property of the world.

## Layout

- `prompts/prompt.md` — the model-facing prompt, mirrors
  `worldbench-web/prompts/prompt.md`.
- `tests/<id>_<slug>/` — one folder per test. **Self-contained**: each
  folder holds its own `test.yaml` (id, title, prompt ref, `checks:` list)
  *and* its own content-check script(s) — the logic specific to what that
  test looks for. Nothing content-specific is factored out preemptively.
  - `test.yaml`'s `checks:` list gives, per check, a `script:` (filename,
    relative to that test's own folder) and a `function:` name.
  - Example: `tests/WC001_trying_all_the_biomes/biome_check.py` defines
    `has_all_biomes()`, a regex/keyword check that the world mentions all
    10 canonical biomes (see `BIOMES` in that file — sourced from
    `worldbench-web/components/about/BiomeGraph.tsx`, a spoiler file never
    shown to the model). Verified trustworthy against 12 real outputs
    (see `dry_runs/dry_run_regex_patterns.py` below) before being
    accepted as the check — no LLM fallback was needed.
  - Example: `tests/WC002_biome_placement/placement_check.py` checks
    *where* each biome sits, not just that it exists — does its
    placement respect the water-flow/adjacency graph in
    `BiomeGraph.tsx`. Two phases: (1) an LLM (OpenRouter via LangChain)
    reads the raw source and extracts, per biome, its adjacent biomes +
    a global elevation ordering, each claim cited to source evidence;
    (2) `grade_graph()` — pure Python, no LLM — checks that extraction
    against `RULES`, a connectivity/elevation predicate table mirroring
    the same reference graph. A dry-run experiment first confirmed
    regex/parsing can't do this: across the 12 real outputs, position
    data was either completely absent (2/12) or present in a different
    bespoke shape every time (a `regions=[{cx,cz,base}]` array, a
    `{cam,tgt}` camera-preset list, `center`/`target`/`focus` fields,
    etc.) — no shared schema to regex against. A rendered-screenshot
    vision-LLM approach was tried next and abandoned after camera
    interaction via simulated mouse drag proved unreliable across
    independently hand-rolled control schemes. Extraction is untested
    without `OPENROUTER_API_KEY` set; `grade_graph()` is verified
    directly (hand-built perfect/broken graphs, not the LLM path).
- `checks/` — **generic structural pre-checks only**, shared by every
  test (unlike content checks, which stay in each test's own folder — see
  **Conventions** below for the distinction).
  - `structural.py` — `check_input_ready(dir)`: does the target input
    directory exist → does `world.html` exist inside it → does it look
    like a real Three.js world (non-empty, has a three/canvas/webgl
    marker). Composes three smaller checks, stopping at the first
    failure, so a missing or wrong file fails fast with a clear reason
    instead of a content check silently reporting everything missing.
- `harness/` — **generation only.** Everything downstream of "we have a
  world.html" (ingest/validate/score/run) lives in `eval/`, described
  next — this split keeps "make a world" and "grade a world" as
  separately runnable concerns that only touch through a file on disk
  (`inputs/<name>/world.html`), never through shared in-process state.
  - `status.py` — `log()`/`timed()`: flushed-stderr progress printing.
    The one module both sides import (`harness.generate`,
    `harness.model_call`, `eval.validate`, `eval.run`, every test's
    `probe.py`/`main.py`) — a leaf logging utility, not generation logic,
    so it stays put rather than duplicating or relocating it.
  - `model_call.py` — **shared OpenRouter invocation machinery, no CLI of
    its own.** `generate(name, model)` does one full completion of
    `prompts/prompt.md` — up to 3 turns of "continue where you left off"
    if a response comes back truncated (`finish_reason == "length"` or no
    `</html>` in the tail), checkpointed to
    `outputs/<name>/generation.json` so a truncated run resumes rather
    than restarting — and writes `inputs/<name>/world.html`.
    `invoke_turn(model, messages, ...)` is one raw turn, optionally
    tool-bound, with the exact same live-reasoning-stream printing and
    per-turn LangSmith trace (`model_call::turn`) either way — this is
    what lets `generate.py`'s `fix` node be exactly as visible as a
    generation turn, not a quieter code path. Both are called only from
    `generate.py`'s graph nodes; there's no standalone one-shot command.
  - `generate.mmd` — hand-authored Mermaid diagram of this loop,
    including the `debug` node's two checks and the `fix` node's
    internal bounded tool loop (neither shows up in LangGraph's own
    auto-rendered graph, which only draws the three top-level
    StateGraph nodes). Render at https://mermaid.live or any viewer that
    understands Mermaid syntax (GitHub included). Keep it in sync by
    hand when a node's internal shape changes — the node/edge topology
    itself rarely does.
  - `generate.py` — **the only generation entrypoint.** A LangGraph
    (`StateGraph`) generate → debug → fix loop, three nodes: `generate`
    (calls `model_call.generate()`), `debug` (`world_lint.check_world()`
    — static structural lint, described below — then
    `browser_debug.check_console_errors()`), `fix` (only reached when
    `debug` found problems). `fix` loops back to `debug`; the graph ends
    when a `debug` pass comes back clean or `--max-fix-rounds` is
    exhausted (default 3 fix attempts — see `DEFAULT_MAX_FIX_ROUNDS`'s
    comment in `generate.py`: a dry run needed exactly 3 to converge a
    real multi-layer bug, and a 4th attempt in that same run made things
    worse, not better, so the default stays evidence-based rather than
    padded "just in case") — whichever first. The file on disk is always
    the latest attempt, clean or not, even on give-up. Every node is a
    named `@traceable` run nested under one parent (`generate::run`) per
    invocation, and every node also prints to stderr as it happens
    (reasoning stream, the full generated/fixed HTML, every debug error)
    — terminal and LangSmith see the same information, nothing is only
    in one or the other.
    - **`fix` is a small bounded tool-calling agent, not one tool call.**
      Two tools, chosen per problem tag: `write_world_html(content)` — a
      full-file rewrite, only for `[structure]` problems (the document
      itself isn't valid — a full rewrite is the only fix that can work,
      see `world_lint.py` below); `str_replace(old_str, new_str)` — one
      exact, unique in-place edit, for `[uncaught]`/`[console.error]`/
      `[navigation]` runtime problems, so a fix round edits the specific
      broken lines instead of re-transcribing the entire file (cheaper,
      faster, and doesn't risk silently mangling unrelated code the way
      a full rewrite can). `str_replace` reports back `ERROR: not
      found`/`not unique` rather than failing silently, so the model can
      retry with more context — up to `MAX_TOOL_CALLS_PER_FIX_ROUND` (4)
      tool calls in one turn, since one bug can need more than one edit.
    - **The fix prompt itself doesn't send the whole file for runtime
      problems — `_build_fix_context()` sends only a windowed excerpt
      (+/- `FIX_CONTEXT_LINES`, 40) around each error's source line.**
      That location comes from `browser_debug.py` (below), not a guess —
      confirmed against a real broken `world.html` that this cut a
      52KB file down to a 3.5KB excerpt for a real bug, still centered
      exactly on the right line. `write_world_html` isn't even bound as
      a tool on a windowed round (not just discouraged by the prompt —
      physically absent from `tools=`), since calling it with only a
      window in hand would silently truncate the file to that window.
      Falls back to the complete file in the two cases a window can't
      cover: any `[structure]` problem in the batch (the whole document
      is what's broken), or no error in the batch carries a location at
      all. **"Not bound" alone isn't enough — the dispatch loop checks
      `call["name"]` against `available_tools` before invoking anything**,
      returning an `ERROR:` ToolMessage instead of executing it. Not
      theoretical: a free-tier model, mid-dry-run, still emitted a
      `write_world_html` tool_call on a windowed (`str_replace`-only)
      round — read about it in the system prompt text despite never
      being offered it via the API — and with a malformed argument shape
      (`{"value": ...}` instead of `{"content": ...}`) that would have
      crashed the whole node via an uncaught pydantic error. Both the
      unbound-tool call and a malformed-args call are now caught and
      reported back to the model as a normal tool result, not a crash.
    - **A short note per fix round is carried forward within the same
      `run()` call** (`AgentState.fix_history`, e.g. `"round 2: 1
      str_replace edit(s) applied"`) and shown to the next fix round —
      not the raw reasoning trace (providers don't guarantee a raw
      reasoning stream replays coherently as later input, and the
      traces run long), just enough for the model to know a previous
      attempt already happened and not blindly repeat it. Scoped to one
      `run()` invocation only, never persisted — see `model_call.py`'s
      `invoke_turn` note above on the same principle.
  - `world_lint.py` — `check_world(html_path)`: static, no browser.
    Catches the failure class browser console errors *can't* diagnose:
    a model that hit its length cap, panicked, and restarted mid-file
    still often closes with a real `</html>`, so `model_call`'s own
    completeness check (`_looks_complete`) sees it as finished — but
    what's actually on disk is two drafts glued together (an unfinished
    statement jammed into a stray ` ``` ` fence, then a second
    `<!DOCTYPE html>`). A browser reports that as a generic syntax error
    or import failure, which then gets handed to the `fix` node as if it
    were a small runtime bug — asking it to patch surgically, which
    cannot unglue two documents. `check_world()` names this class of
    failure directly (leftover markdown fences, unclosed `<script>`,
    leaked commentary like "Let me provide a clean continuation", a
    truncated last statement) and tags it `[structure]`, so `fix` knows
    to call `write_world_html` (full rewrite) instead of `str_replace`.
  - `browser_debug.py` — `check_console_errors(html_path)`: loads a
    world.html in headless Chromium and collects distinct
    `console.error`/uncaught-exception messages. Deliberately does
    **not** verify anything about rendering (no screenshot, no
    render/camera wait, no GPU flag tuning) — a JS error fires from the
    engine regardless of whether WebGL ever paints a pixel, which is what
    lets this sidestep the swiftshader/rAF-throttling uncertainty that
    stalled an earlier headless-rendering spike (see project memory
    `avoid-headless-browser-infra`). Per-frame throws inside the render
    loop repeat identically every frame and are deduplicated to one
    entry, not left to flood the result (604 identical copies of one bug,
    seen for real, collapsed to 1). Network-dependent (fetches the
    Three.js CDN scripts for real) — treat a flaky/inconsistent error
    message on repeated runs as a CDN-fetch symptom before assuming the
    check itself is unreliable.
    - **Every returned error string carries a `(line N, col N)` suffix
      when a location could be found** — this is what `generate.py`'s
      `_build_fix_context()` windows around. Getting it wasn't a single
      obvious API: Playwright's `pageerror` gives a full call stack for
      a runtime error (`TypeError`, `ReferenceError`, ...) but an
      **empty** stack for a parse-time `SyntaxError` — verified directly
      against a real broken `world.html`, not assumed, since V8 never
      builds a call stack for a script that failed to parse at all. A
      `window.addEventListener('error'/'unhandledrejection')` listener
      injected via `add_init_script` gets `lineno`/`colno` for both
      cases, correlated back to the matching `pageerror` event by a FIFO
      queue (both fire for the same underlying event, in the same
      order). `console.error()` calls get their location straight from
      Playwright's own `msg.location` — no injection needed there.
- `eval/` — **evaluation only**, one script per pipeline stage. Never
  imports from `harness/` (generation doesn't need eval, and eval treats
  whatever's in `inputs/<name>/world.html` as a given, however it got
  there — `generate.py` or hand-placed).
  - `loader.py` — `load_check(module_path, function_name)`: dynamically
    imports a check function from a test's own script by file path (not
    package import, since each test's checks live in that test's own
    folder). Shared by `validate.py` and
    `scripts/dry_run_regex_patterns.py` — the loading logic lives here
    once, dev scripts import it from here, never the reverse.
  - `ingest.py` — `ingest(name)` copies `inputs/<name>/world.html`
    (`name` = `<model>__<test_dir_name>`, `test_dir_name` matching a
    folder under `tests/` exactly, e.g.
    `opus-5__WC001_trying_all_the_biomes`) into `outputs/<name>/world.html`.
  - `validate.py` — `validate(output_dir, test_dir_name)`: two-stage. (1)
    `checks.structural.check_input_ready()` — fail fast if the input
    itself is missing or wrong; (2) only if that passes, reads the test's
    `test.yaml`, loads + runs every listed check via `loader.py` +
    `audit.py`. Writes `validation.json` into `output_dir` and returns
    the same dict.
  - `score.py` — **real, not a stub.** `score_result(check_result)` turns
    one `CheckResult` into points: a check earns per-item scoring by
    putting `score`/`max_score` in its own `details` (as
    `biome_check.has_all_biomes` does — one point per biome found, e.g.
    9/10 if one is missing); any check that doesn't falls back to plain
    1/0 pass-fail (e.g. `checks/structural.py`'s checks). `score_report()`
    aggregates several named results for one test's output into a
    `report.json`-shaped dict. `scripts/dry_run_regex_patterns.py` already
    uses this to print `score/max_score` per world, not just pass/fail.
  - `run.py` — **real CLI entrypoint.** `uv run python -m eval.run
    <model>__<test_dir_name>` — ingest + validate + score for one input
    folder under `inputs/`, printing per-check pass/fail + score and
    writing `validation.json`. This is the actual way to run a test
    against a single input; `dry_runs/dry_run_regex_patterns.py` is for
    sanity-checking a check against a whole corpus, not for this.
  - `audit.py` — **real, not a stub.** `run_audited_check(check_fn,
    html_path, test_id=, model=)` runs a check and wraps it in a
    LangSmith `@traceable` run (named `<test_id>::<function_name>`,
    tagged with `model`/`test_id`), recording the check's full
    `CheckResult` (including `details.found`/`details.missing`) plus its
    score as the run's output — so any run, pass or fail, is auditable:
    open it in LangSmith and see exactly which item(s) were absent and
    what the score was, without re-running anything. No-ops safely
    without `LANGSMITH_TRACING=true` + `LANGSMITH_API_KEY` set (see
    `.env.example`) — same function runs the check either way.
    `dry_runs/dry_run_regex_patterns.py` already calls checks through
    this, not directly.
  - **`invoke_turn()`'s transient-error retry carries reasoning forward,
    never resets it.** If a stream dies mid-turn (dropped connection, or
    a 502/503/504 from the provider) after a reasoning model has already
    spent real time thinking, the retry doesn't resend the original
    request from scratch — `_splice_partial_turn()` appends whatever
    content/reasoning had accumulated as one exchange and asks the model
    to continue, the same "resume, don't restart" shape `generate()`'s
    own truncation-recovery uses. This lives entirely inside one
    `invoke_turn()` call, deliberately — nothing is written to disk or
    carried past the process; a run that ultimately gives up is meant to
    be discarded, not resumed later.
- `inputs/` — gitignored drop zone. **Real harness/eval input only** —
  never dry-run data (see `dry_runs/` below). Written by `harness/`
  (`generate.py`) or by hand; read by `eval/` (`ingest.py`) — the seam
  between the two halves.
- `outputs/` — gitignored, per-run/per-model/per-test results.
- `scripts/`
  - `export_to_web.py` — copies a passing output + writes `meta.mdx` into
    `worldbench-web/public/tests/<slug>/`. The seam between the two repos.
- `dry_runs/` — **everything dry-run related lives here and nowhere
  else** — not `scripts/`, not the top-level `inputs/`.
  - `dry_run_regex_patterns.py` — **dev tool, not part of the pipeline.**
    Its own code should never be imported by anything else — the one
    piece of shared logic it needs (dynamic check loading) lives in
    `eval/loader.py` and is imported from there. Imports every
    `world.html` from `worldbench-web/public/tests/*` (skips the
    gitignored `old/` archive there — it's a prior pipeline's output, not
    real data for the current prompt) into `dry_runs/inputs/<slug>/`, then
    runs a given test's check against all of them and reports pass/fail.
    Used to answer "is this check trustworthy, or does it need an LLM
    fallback?" before trusting a new check. Extend the `CHECKS` dict at
    the top of the file as more tests get real check scripts.
  - `inputs/` — gitignored, generated fresh on every run (wiped and
    rebuilt each time) — never hand-edited, never real harness input.

## Future / deferred

- Nothing currently deferred here — `harness/generate.py`'s generate →
  debug → fix loop is the only generation path (there is deliberately no
  separate plain one-shot command; a one-shot completion is just what its
  `generate` node does before handing off to `debug`). If a new
  generation mode is proposed, default to the same split:
  generation-mechanics stay in `harness/`, grading stays in `eval/`, and
  the two talk only through `inputs/<name>/world.html` on disk.

## Claude's own testing

- **Never call a paid OpenRouter model when Claude is smoke-testing /
  exercising code itself** (e.g. sanity-checking `harness/generate.py`
  or `harness/model_call.py` after an edit). OpenRouter bills per token
  and paid models add up fast
  when hit repeatedly during dev iteration. Use a free-tier model (id ends
  in `:free`) for that instead — pick from
  https://openrouter.ai/models?q=free, e.g. (list as of writing, check the
  URL for the current roster since it changes):
  `z-ai/glm-5.2:free`, `google/gemma-4-31b-it:free`,
  `google/gemma-4-26b-a4b-it:free`, `nvidia/nemotron-3-nano-30b-a3b:free`,
  `nvidia/nemotron-3-super-120b-a12b:free`,
  `nvidia/nemotron-3-ultra-550b-a55b:free`,
  `nvidia/nemotron-nano-9b-v2:free`, `liquid/lfm-2.5-2.6b:free`,
  `cohere/north-mini-code:free`, `thinkingmachines/inkling:free`.
  This restriction is about Claude's own dev-loop testing, not about what
  models the harness evaluates for real — `inputs/` already holds real
  paid-model outputs (opus-5, gpt-5-6-sol, grok-4-6, etc.) and that's the
  actual point of worldbench; don't apply this rule to real evaluation
  runs the user asks for.

## Conventions

- **Content checks are colocated with their test**; **structural checks
  are shared.** The distinction that matters: a check is only shared
  infrastructure if it's identical regardless of which test is running
  (e.g. "does the input file exist and look like a world.html" —
  `checks/structural.py`). A check that depends on what a specific test
  is looking for (e.g. "does this world have all 10 biomes") stays in
  that test's own folder. Don't add a new file to `checks/` unless it's
  genuinely test-agnostic; don't move a test-specific check into
  `checks/` just because it feels reusable in theory.
- **Before trusting a new check**, run it against real data first (extend
  `dry_runs/dry_run_regex_patterns.py`'s `CHECKS` dict and run it) and
  hand-audit *why* things matched, not just the pass/fail count — regex
  keyword checks can produce false positives from unrelated identifiers
  (e.g. a stray `fir` keyword matched inside `firefly`; a bare `delta`
  keyword matched animation-loop variables like `deltaY`). Only reach for
  an LLM-based check if the regex genuinely can't be made reliable.
- **All dry-run activity — scripts and imported test data alike — stays
  inside `dry_runs/` and nowhere else.** Don't add a dry-run script to
  `scripts/`, and don't import dry-run data into the top-level `inputs/`
  — that directory is reserved for real `eval/ingest.py` input.
- **`harness/` is generation, `eval/` is grading — they don't import from
  each other's internals.** `harness/generate.py` only chains into
  `eval.run` at the CLI boundary (`--run`), the same way a human would run
  two separate commands. A new generation-side script goes in `harness/`;
  a new scoring/grading-side script goes in `eval/`. `harness/status.py`
  is the one exception — a leaf logging util both sides import, not
  generation or evaluation logic itself.
- **Every generation node (generate/debug/fix) prints what it did to
  stderr *and* is a named LangSmith `@traceable` run** — chain-of-thought
  reasoning, the full generated/fixed HTML, and every debug error, all in
  both places, never only in one. If you add a new node or extend an
  existing one, keep both: a silent node (nothing printed) or an untraced
  one (no `@traceable`) reintroduces exactly the black-box behavior this
  was built to avoid.
- Python via **uv** (`pyproject.toml` / `uv.lock`) — run scripts with
  `uv run python <path>`, not a bare venv/pip.
