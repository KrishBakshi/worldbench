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
- `harness/` — orchestration, one script per pipeline stage:
  - `loader.py` — `load_check(module_path, function_name)`: dynamically
    imports a check function from a test's own script by file path (not
    package import, since each test's checks live in that test's own
    folder). Shared by `validate.py` and
    `scripts/dry_run_regex_patterns.py` — the loading logic lives here
    once, dev scripts import it from here, never the reverse.
  - `ingest.py` — **the only path right now.** `ingest(name)` copies
    `inputs/<name>/world.html` (`name` = `<model>__<test_dir_name>`,
    `test_dir_name` matching a folder under `tests/` exactly, e.g.
    `opus-5__WC001_trying_all_the_biomes`) into `outputs/<name>/world.html`.
    There is no `generate.py` — see **Future / deferred** below.
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
  - `run.py` — **real CLI entrypoint.** `uv run python -m harness.run
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
- `inputs/` — gitignored drop zone for `ingest.py`. **Real harness input
  only** — never dry-run data (see `dry_runs/` below).
- `outputs/` — gitignored, per-run/per-model/per-test results.
- `scripts/`
  - `export_to_web.py` — copies a passing output + writes `meta.mdx` into
    `worldbench-web/public/tests/<slug>/`. The seam between the two repos.
- `dry_runs/` — **everything dry-run related lives here and nowhere
  else** — not `scripts/`, not the top-level `inputs/`.
  - `dry_run_regex_patterns.py` — **dev tool, not part of the pipeline.**
    Its own code should never be imported by anything else — the one
    piece of shared logic it needs (dynamic check loading) lives in
    `harness/loader.py` and is imported from there. Imports every
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

- **Automated generation (`harness/generate.py`) doesn't exist yet.**
  When there's access/resources to build it: call the model under test
  via **OpenRouter** (one API, many providers), through **LangChain**
  (`ChatOpenAI` pointed at OpenRouter's `base_url`), traced with
  **LangSmith**. Until then, every test is direct ingestion
  (`harness/ingest.py`) of a manually-produced output — don't build
  `generate.py` out until explicitly asked.

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
  — that directory is reserved for real `harness/ingest.py` input.
- Python via **uv** (`pyproject.toml` / `uv.lock`) — run scripts with
  `uv run python <path>`, not a bare venv/pip.
