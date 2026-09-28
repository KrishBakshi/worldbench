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
  - `test.yaml` may set `needs_capture: true`: the test reads the shared
    capture (below), so `eval/validate.py` captures before running it.
  - Ladder (max 280, every max fixed so totals compare across models):
    WC000 voxel island 40 (LLM source judge 20 + VLM bug-hunt 20), WC002
    coverage + placement 20, WC003 micro-contents 100, WC004 physics 100,
    WC005 temporal cycles 20. **There is no WC001**: its keyword coverage
    check was folded into WC002 and deleted — every scored model got 10/10
    and a one-line fake (`const pine=1,...,lava=9`) got 10/10 too.
  - **WC000's regex voxel check (`voxel_check.py`) was removed**, not tuned:
    43 of its 83 pattern branches matched exactly one model's file, and
    consistently renaming variables (behaviour-preserving) moved scores by
    up to 14/38. `voxel_judge.py` asks an LLM for a probability + verbatim
    quote per item instead. Don't reintroduce identifier-keyed regex for a
    property of the built world.
  - Example: `tests/WC002_biome_placement/` — coverage + placement. (1)
    classify (LLM) slices the JS per biome; `coverage.py` counts a biome
    covered only if marked present AND its quoted layout code is really in
    the source; (2) extract (LLM) gives neighbors + elevation order; (3)
    `grade_graph()` — pure Python — 1 point per covered biome + 1 if its
    `RULES` pass. An uncovered biome is 0/2 and drawn grey "not covered"
    (three node states in `plot.py`), and rules pointing at it are
    *skipped*, not failed, so one absence costs 2 points, not 4–5.
    Regex/parsing was ruled out first: across 12 real outputs position
    data was absent (2/12) or a different bespoke shape every time.
  - WC003/WC004/WC005 are **code probe + visual judge**: each item's points
    are split between a verified code quote and what the captured frames
    show. WC004 motion is hybrid too: capture takes a near + far burst per
    biome (frames ~2s apart, camera still, changed-pixel overlay) on the
    **daytime preview** — at night most moving things are invisible — and a
    VLM "it moves" only counts if the burst's pixels really changed. Kept
    small on purpose (one zoom-out, no pivots, no waiting for weather
    cycles); don't grow it into a camera-choreography project. WC005's
    cloud/weather items stay code-only. WC005 measures "does X change" from pixels
    (brightness, frame diff, chromaticity) rather than asking the VLM: on
    kimi-k-3 the VLM called lighting "identical" across frames whose mean
    brightness was 11.9 / 35.0 / 11.6 / 11.5.
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
    - `log_to_file(path)` — a context manager that tees everything `log()`
      prints into `path` as well as stderr. **Teeing lives at the sink, not
      in `generate.py`**, because `log()` is already the one choke point
      every node prints through: capturing here makes a transcript complete
      by construction (including output added later) instead of a second
      thing each new node must remember to write to. Flushed per line, so a
      run killed mid-way still leaves a usable transcript; a closed or
      broken sink is swallowed rather than taking down the run it was only
      meant to record.
  - `code_tools.py` — **read-only code-inspection tools shared by both
    sides** (the fix loop here and `eval/evidence_agent.py`): `grep`,
    `read_lines`, and an allowlisted `shell`. A security boundary, so it
    exists once. The agent never sees the real file — `ReadOnlySource`
    copies it into a fresh temp dir outside the repo and makes file and dir
    read-only. `shell` never starts an interpreter (no `shell=True`):
    `|` pipelines of text readers only (`grep`, `sed -n 'A,Bp'`, `head`,
    `tail`, `wc`, `nl`, `cut`, `sort`, `uniq`, `tr`, `cat`); `;`, `&&`,
    redirection and subshells are refused; write flags (`sed -i`,
    `sort -o`, …) are refused; paths can't leave the temp dir; the env is
    scrubbed (no HOME, no API keys). There is deliberately no way to *run*
    the inspected JS — reading untrusted generated code and executing it are
    different risks. Adversarially tested: 22 escape/write attempts refused,
    the real file byte-identical afterwards.
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
    - **A streamed turn has two phases and both are now visible.**
      `_ReasoningPrinter` echoes the reasoning stream; `_ContentProgress`
      reports the content phase as size/elapsed/rate rather than echoing it
      (the full file is already printed once the turn ends — echoing would
      double it). The reasoning→content boundary prints one line,
      `reasoning ended (N chars) — writing content now`.
      **This exists because the boundary reads as a hang.** Reported as:
      "the reasoning stops streaming, but the completion
      tokens are still coming." That is a reasoning model behaving
      normally — it finished thinking and started writing — but the stream
      loop fed *only* `reasoning_content` to the printer and accumulated
      content silently, so the terminal went dark from that moment until
      the whole turn finished. On a large model writing a ~50KB
      `world.html`, that silent stretch is the longest phase of the run and
      is indistinguishable from a wedged stream. Nothing was wrong with the
      model or the provider; the harness just wasn't reporting the phase it
      had entered.
      - `_ContentProgress` also records the **largest gap between chunks**
        and warns on any gap over `_STALL_WARN_S` (20s). That is the one
        number separating "this model is slow" from "this stream is
        wedged" — the question a silent terminal cannot answer.
      - In-place repainting is skipped when stderr isn't a TTY, so a
        redirected or teed run gets clean milestone lines (every
        `_PROGRESS_LOG_EVERY_CHARS`, via `log()`) instead of carriage
        returns in the transcript file.
      - `_ReasoningPrinter.close()` resets `opened`, so a provider that
        **interleaves** reasoning and content re-prints the badge and
        re-arms the style instead of emitting unstyled stray text. The
        printer is now closed at each transition, not only at end of
        stream, which is what makes this matter.
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
    when a `debug` pass comes back clean or `MAX_FIX_ROUNDS` (5) fix
    rounds are used — whichever first. **5 is a hard cap with no CLI
    override, and the model is told about it**: `generation_system()` (a
    system message at generation — `prompts/prompt.md` stays the untouched
    world spec) and every fix prompt (`_budget_text`: "round k of 5", the
    last round says so) state the budget and that a crash hides the errors
    after it. The point is that a model can plan across the budget instead
    of discovering it one surfaced bug per round. **Nothing inside a round
    is capped** — the old 4-tool-calls-per-round limit cut models off
    mid-fix. The one early stop is a provable loop: re-sending a call that
    already failed against the unchanged file (`failed_calls`) ends the
    round, since `str_replace` is deterministic and can only answer the
    same way. The file on disk is always
    the latest attempt, clean or not, even on give-up. Every node is a
    named `@traceable` run nested under one parent (`generate::run`) per
    invocation, and every node also prints to stderr as it happens
    (reasoning stream, the full generated/fixed HTML, every debug error)
    — terminal and LangSmith see the same information, nothing is only
    in one or the other.
    - **`fix` has two modes, routed by problem tag.** `[structure]`
      (document damage: glued drafts, leaked fence/prose, unbalanced
      `<script>`) → `_rewrite_round`: the model writes the whole file as
      **streamed content** via `model_call.complete_document()` (continued
      across turns if cut off), never as a tool argument. Everything else
      (`[syntax]`, `[uncaught]`, `[console.error]`, `[navigation]`) →
      `_patch_round`: small `str_replace(old_str, new_str)` edits, as many
      as the model needs. There is no
      `write_world_html` tool any more — **that is the 504 fix.** Providers
      buffer tool-call arguments until the call is complete, so in a
      real run a 54KB rewrite-as-tool-argument left the
      connection silent until OpenRouter's "Upstream idle timeout exceeded
      (504)" killed it — three times, 521s, then a crash. Content streams;
      the connection is never idle.
    - **Every `str_replace` is verified the moment it's made**, not a debug
      round later: the result says whether all scripts still parse
      (`world_lint.syntax_findings`, ~30ms), with a numbered snippet if
      not. An edit that would break a file that currently parses is
      **refused** and the file left unchanged — the "fix one bug, introduce
      another" pattern seen in real runs used to cost a full round to
      surface. A refused edit doesn't trigger the full-file escalation
      below (it proves the model found the spot).
    - **`str_replace` is built to land on the first try** — a failed edit
      burns a whole model turn (one real round lost 2 turns to
      `old_str not found`). Excerpt `  393: ` prefixes copied into old_str
      are stripped; a whitespace-only mismatch with exactly one match is
      applied; otherwise the error shows the closest matching file text
      (`difflib`, line-aligned) to copy from, or the line numbers of every
      match when it isn't unique.
    - **A provider failure forfeits the round, not the run.** Edits already
      applied are kept and `run()` still writes its trajectory `.json`
      (a 504 used to crash `run()` and lose it).
    - **The fix prompt itself doesn't send the whole file for runtime
      problems — `_build_fix_context()` sends only a windowed excerpt
      (+/- `FIX_CONTEXT_LINES`, 40) around each error's source line.**
      That location comes from `browser_debug.py` (below), not a guess —
      confirmed against a real broken `world.html` that this cut a
      52KB file down to a 3.5KB excerpt for a real bug, still centered
      exactly on the right line. `[syntax]` findings carry the same
      kind of location suffix, so a parse error is windowed too.
      Falls back to the complete file in the three cases a window can't
      cover: any `[structure]` problem in the batch (the whole document
      is what's broken), no error in the batch carries a location at
      all, or `force_full_file` — **a windowed round that called no tool
      and applied no edit escalates the next round to the complete
      file.** That outcome is evidence the window is pointing where the
      bug isn't, not that the model was idle; without the escalation a
      run re-sends the same useless excerpt until the round budget is
      exhausted, which is exactly how a real run spent all 3
      attempts producing zero edits. The escalation is a safety net for
      when caller-frame windowing (see `browser_debug.py` below) still
      misses — it is not a substitute for it, since a fix round spent
      discovering the window was wrong is still a round spent.
    - **Windows also cover where the identifiers on a throw line were
      bound, not only where execution went** (`_definition_sites()`,
      `DEF_CONTEXT_LINES` 12). A stack trace is control flow ("who called
      this"); it never answers "where did this bad value come from."
      A real run is the case: `Cannot read properties of
      undefined (reading 'color')` threw at line 350 on
      `terrainGeo.attributes.color` with a caller frame at 1037, but the
      defect is line 996, `terrainGeo=buildTerrain(0);` — assigning a
      **Mesh** to something used as a **Geometry** (`buildTerrain` ends
      `return m`). Windows were 310–390 and 997–1077: the fix site missed
      **by one line**, and no stack frame would ever have pointed at it.
      Scanning the throw line's identifiers for their declaration/
      assignment sites now pulls in 996 and 572, at 205 of 1170 lines —
      still windowed, not a full-file fallback.
      - **`DEF_SITE_MAX_HITS` (3) is what makes this safe, not a nicety.**
        An identifier bound all over the file localizes nothing: the same
        scan for that file's *other* bug (`z is not defined`) returns 21
        hits — loop counters, destructured coords — and would drag in most
        of the document. Over the cap, the identifier is dropped rather
        than windowed. With `DEF_SITE_MIN_IDENT_LEN` (3) and `_JS_NOISE`
        (keywords, globals, the Three.js surface) this keeps worst-case
        context at ~8–30% across the whole real `inputs/` corpus. Only the
        throw line is scanned, never caller frames — a caller's locals are
        a different scope and add noise.
      - Note what this deliberately does **not** fix: that same file's
        other bug is dead scaffolding
        (`const b1=[...,z]; // placeholder, rebuilt below`) whose correct
        repair is *deletion*, and it was already fully visible in its own
        window. Not every give-up is a context problem — check whether the
        model could see the bug before widening anything.
    - **The dispatch loop rejects any tool name but `str_replace`**,
      returning an `ERROR:` ToolMessage instead of executing it, and a
      malformed-args call is reported back rather than crashing the node.
      Not theoretical: a free-tier model once emitted a call for a tool it
      had only read about in the prompt text, with a malformed argument
      shape that would have crashed the node via an uncaught pydantic error.
    - **A short note per fix round is carried forward within the same
      `run()` call** (`AgentState.fix_history`, e.g. `"round 2: 1
      str_replace edit(s) applied"`) and shown to the next fix round —
      not the raw reasoning trace (providers don't guarantee a raw
      reasoning stream replays coherently as later input, and the
      traces run long), just enough for the model to know a previous
      attempt already happened and not blindly repeat it. Scoped to one
      `run()` invocation only, never persisted — see `model_call.py`'s
      `invoke_turn` note above on the same principle.
  - `world_lint.py` — `check_world(html_path)`: static lint, then the
    browser — **skipped when a script doesn't parse** (nothing past a
    parse failure runs; the console would only restate it). Two tags:
    - `[structure]` — the *document* is damaged: a model that hit its
      length cap and restarted mid-file still often closes with a real
      `</html>`, so `_looks_complete` passes it, but on disk are two drafts
      glued together (leftover ` ``` ` fence, second `<!DOCTYPE html>`,
      leaked commentary like "Let me provide a clean continuation",
      unbalanced `<script>`). Patching can't unglue that → `fix` rewrites.
    - `[syntax]` — a script doesn't parse, per a **real parser**
      (`node --check`, `.mjs`/`.cjs` by script type), always with a
      `(line N; see also line …)` location → `fix` patches it.
      **Never reintroduce character counting here.** The old
      `_unbalanced()` counted braces without understanding comments; an
      apostrophe in `// Swamp on jungle's far side` made it report
      `1 extra '{'` for three rounds against a script that parsed — which
      forced full-file context, told the model to rewrite, and led straight
      to the 504 above. A false finding costs every round it survives.
    - The parser's line is exact except for brace errors (`Unexpected end
      of input` points at the last line; inside a class a missing `}`
      surfaces at the next method header, 58 lines late in a real run). A
      comment/string/template/regex-aware lexer yields candidate sites from
      the code's own intent — a `}` less indented than its `{`
      (missing), more indented (extra), a `function`/`class` one brace
      level deeper than earlier ones at its indent (flat,
      unindented code) — and each candidate's one-brace repair is **re-parsed
      before it's reported** (`_confirmed_location`), so sloppy-but-valid
      indentation can't produce a false lead. Measured on 193 synthetic
      single-brace breakages of the 17 real worlds: 90/91 missing-`}` and
      97/102 extra-`}` land inside a fix window. Earliest-first beat
      nearest-to-error-first (tried; it moved a real-run missing-`}` case
      from its true line 393 to 444).
    - Without `node` on PATH, `[syntax]` falls back to the lexer's bracket
      balance (hint-worded); the browser's SyntaxError is the backstop.
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
      order).
    - **`console.error` gets a stack too.** An init-script wrapper records
      `new Error().stack` per call, matched to its console message by first
      argument (not arrival order — the browser logs errors of its own that
      never pass through the wrapper). When the message was logged from
      inside a library, its own location is the library's line (e.g. line
      10912 of `three.module.js`), which `fix` can't edit and
      `_build_fix_context` drops as out of range — so the page's own frames
      become the location instead. Seen for real: `computeBoundingSphere():
      radius is NaN` in a real run was unlocalizable and survived to
      give-up; with frames it points at `createAnimal` and both spawn
      sites, and a free-model fix round repaired it in one edit.
    - **The suffix reports caller frames too, not just the throw site:**
      `(line 104, col 27; called from line 383, line 397)`. This is not
      cosmetic. For a whole class of JS errors the throw site is correct
      code and the defect is in the *caller*, so a fix window centered on
      the throw site shows the model nothing wrong. Seen for real:
      `jit=(c,rnd)=>c*(0.9+rnd()*0.2)` on line 104
      was called as `jit(color, Rv())` — the RNG's *result* instead of
      the RNG — on lines 383/397/412. `rnd is not a function` reported
      line 104, the window covered 64–144, and all 3 fix rounds made zero
      edits, which was the only honest answer available. The frames were
      in `exc.stack` all along and were being discarded. Now parsed
      always (not just as a fallback for a missing primary location),
      filtered to this document (CDN/`three.module.js` frames aren't
      editable by `fix` and would waste the context budget), deduped for
      recursion, capped at `MAX_CALLER_FRAMES` (4) so a deep in-file
      stack can't quietly expand a "windowed" excerpt into the whole
      file. `_loc_suffix()` and `generate.py`'s `_LOCATION_RE` are two
      ends of one format — change them together.
- `eval/` — **evaluation only**, one script per pipeline stage. Never
  imports from `harness/` (generation doesn't need eval, and eval treats
  whatever's in `inputs/<name>/world.html` as a given, however it got
  there — `generate.py` or hand-placed). `harness/status.py` is the one
  import both sides share.
  - `capture/` — **the shared capture stage**, run once per world before
    any `needs_capture` test; writes `outputs/<model>/capture/` (views +
    `manifest.json`, reused while `world.html`'s sha256 is unchanged).
    This reverses the earlier "avoid headless browser infra" stance on
    purpose: visual judging was chosen, so capture is built once, well,
    instead of each test hand-rolling Playwright.
    - `preview.py` — an LLM patches the world's **own** clock to obey
      `window.__WB_TIME` (filled by `hook.js` from `?wb_tod=&wb_season=`).
      Guards: every `new_str` must read `__WB_TIME`, ≤ 600 added chars per
      edit, ≤ 6 edits, each `old_str` unique — a patcher that added its own
      lighting would hand WC005 a cycle the model never wrote.
    - `run.py` — renders tod 0/.25/.5/.75 and takes the **brightest** as
      day (`pick_day_tod`) instead of trusting the patch's phase mapping.
      On kimi-k-3 the patch mapped noon to tod .25 (dropped a +0.6 offset);
      the brightness pick caught it. Then overview, 4 orbit directions, 4
      seasons, then the agent. Deterministic views before agent views.
    - `hook.js` — init script: seeded `Math.random` (an unseeded world
      builds a different island per reload), `window.__wb` scene/camera via
      Three's `__THREE_DEVTOOLS__` observe hook (no edit to the model's
      code), and `__WB_TIME`.
    - `browser.py` — headless Chrome via the **Chrome DevTools MCP server**
      (`npx chrome-devtools-mcp`, MCP stdio). No coordinate drag tool, so
      orbit/pan/zoom dispatch synthetic pointer/wheel events on the canvas
      (OrbitControls doesn't check `isTrusted`; verified on 3 models). The
      server only writes screenshots inside declared MCP roots —
      `_repo_roots` declares the repo.
    - `navigator.py` — per-biome LLM agent (legend click / orbit / pan /
      zoom / save / give_up), "caveman mode": fresh short context per
      biome, terse prompt, one tool call per turn, only the newest frame
      kept as an image, filtered a11y tree, 8-step budget. **Its "found"
      is not trusted**: on kimi-k-3 it saved the volcano as "Backwater
      Swamp" at confidence 1.0 — judges re-confirm `shows_biome`.
    - `judge.py` — the shared per-biome visual item judge (WC003/WC004).
    - `llm.py` — judge model (`CAPTURE_MODEL` → `WC002_MODEL`), images
      downscaled to 896px JPEG. `gemini-3.5-flash-lite` ignores
      `temperature` (fixed sampling), so judges are not bit-repeatable.
  - `evidence.py` — `in_source(quote, normalize(js))`: every probe/judge
    quote must really be in the source (whitespace-insensitive, per line,
    tolerant of a garbled line *tail* — ≥85% prefix — not of invented
    lines). Before this, graders only checked a quote *looked* like code,
    so a plausible invented `scene.add(new THREE.Mesh(palmGeo, …))` scored.
  - `loader.py` — `load_check(module_path, function_name)`: dynamically
    imports a check function from a test's own script by file path (not
    package import, since each test's checks live in that test's own
    folder). Shared by `validate.py` and
    `scripts/dry_run_regex_patterns.py` — the loading logic lives here
    once, dev scripts import it from here, never the reverse.
  - `ingest.py` — `ingest(name)` copies `inputs/<name>/world.html`
    (`name` = `<model>`, or legacy `<model>__<test_dir_name>`) into
    `outputs/<name>/world.html`.
  - `validate.py` — `validate(output_dir, test_dir_name)`: (1)
    `checks.structural.check_input_ready()` — fail fast if the input
    itself is missing or wrong; (2) capture, if any selected test has
    `needs_capture` (a failure is recorded, not fatal); (3) loads + runs
    every listed check via `loader.py` + `audit.py`. Old `validation.json`
    entries for checks no longer in any `test.yaml` are dropped, so totals
    only sum the current ladder. Writes `validation.json`.
  - `score.py` — **real, not a stub.** `score_result(check_result)` turns
    one `CheckResult` into points: a check earns per-item scoring by
    putting `score`/`max_score` in its own `details` (every WC check
    does); any check that doesn't falls back to plain
    1/0 pass-fail (e.g. `checks/structural.py`'s checks). `score_report()`
    aggregates several named results for one test's output into a
    `report.json`-shaped dict. `scripts/dry_run_regex_patterns.py` already
    uses this to print `score/max_score` per world, not just pass/fail.
    `apply_island_gate()` drops the delta biome's points on **WC004 only**
    when any WC000 check's `missing` has `water_bed`, `water_physics` or
    `ocean_void`. WC003 is not gated: it judges the seabed from its own
    frames and zeroes delta itself — gating both would charge it twice.
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
    - **One 504 is not retried: an idle timeout on a tool-bound turn that
      streamed no content** (`_is_silent_tool_call_stall` →
      `SilentToolCallTimeout`). That's the provider buffering a large
      tool-call argument; a retry replays the same reasoning to the same
      decision and the same silence (3 × ~170s in a real run).
- `inputs/` — gitignored drop zone. **Real harness/eval input only** —
  never dry-run data (see `dry_runs/` below). Written by `harness/`
  (`generate.py`) or by hand; read by `eval/` (`ingest.py`) — the seam
  between the two halves.
  - `inputs/<name>/logs/<UTC-timestamp>.log` + `.json` — **written by
    `generate.py`'s `run()`, one pair per invocation.** The `.log` is the
    complete stderr transcript (reasoning streams, every generated/fixed
    file, every debug error). Reasoning is styled on the terminal outside
    `log()`, so `_ReasoningPrinter` also writes it raw via `status.tee()`
    between `[reasoning]`/`[/reasoning]` markers — before that, the
    transcript recorded how long a model reasoned and never what it
    reasoned. The `.json` is the trajectory: per-round
    `debug_rounds` errors, `fix_history` notes, status, rounds used,
    timings. Timestamped rather than overwritten so reruns accumulate
    instead of destroying the previous attempt's evidence. This exists
    because diagnosing a real give-up was guesswork without it
    — the run was over, nothing on disk said what the three fix rounds had
    tried, and `outputs/<name>/` didn't exist either. LangSmith had it, but
    a trace you can't open offline (or after the project's retention
    window) isn't a record. Alongside `world.html` deliberately: the
    artifact and the account of how it got there stay together.
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
  a new scoring/grading-side script goes in `eval/`. Two leaf modules are
  the exceptions both sides import: `harness/status.py` (logging) and
  `harness/code_tools.py` (the read-only tool boundary — one copy of a
  security boundary, not two that drift). Neither is generation or
  evaluation logic itself.
- **Every generation node (generate/debug/fix) prints what it did to
  stderr *and* is a named LangSmith `@traceable` run** — chain-of-thought
  reasoning, the full generated/fixed HTML, and every debug error, all in
  both places, never only in one. If you add a new node or extend an
  existing one, keep both: a silent node (nothing printed) or an untraced
  one (no `@traceable`) reintroduces exactly the black-box behavior this
  was built to avoid.
- Python via **uv** (`pyproject.toml` / `uv.lock`) — run scripts with
  `uv run python <path>`, not a bare venv/pip.
