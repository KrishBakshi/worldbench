# Contributing to WorldBench

Thanks for helping. WorldBench compares models on one fixed ladder, so most of
these rules exist to keep scores comparable across every model on the board.

## Setup

Python runs through [uv](https://docs.astral.sh/uv/):

```bash
uv sync
cp .env.example .env    # API keys only
uv run python -m eval.run <model>
```

Capture needs Node (it drives a headless browser). Judge settings (which model
does which job, rate limits, retries) live in `eval/judge.yaml`, never in code.

## Submitting a model's results

1. Put the world at `inputs/<model>/world.html`, or generate it with
   `harness/generate.py`.
2. Run the full ladder: `uv run python -m eval.run <model>`.
3. Run `uv run python -m eval.gaps find <model>`. If it lists gaps (judge
   outages, unfinished rechecks), run `uv run python -m eval.gaps repair <model>`
   and check again. Submit only a world that reports clean.
4. Commit `outputs/<model>/` alone on a branch named `bench/<model>` and open a
   pull request. Screenshots are gitignored and stay local.

Scores change only through the pipeline's own judges. Never edit a score,
verdict or quote by hand.

## Changing a test or the pipeline

- **One ladder for every model.** A change to capture or grading that can move
  a score means every scored world is re-run. Say what it does to existing
  scores in the pull request.
- **Content checks stay in their test's folder** (`tests/WC00N_*/`). Only
  checks that are identical for every test belong in `checks/`.
- **Check a new check against real worlds first**, and look at *why* things
  matched, not only the pass count.
- **No keyword or identifier matching** for a property of the built world:
  renaming a variable must never change a score.
- **Generation and grading stay apart.** `harness/` makes worlds, `eval/` grades
  them, and they meet only through `inputs/<model>/world.html`.
- **Docs say "the judge model"**, never a judge model's name or provider.
  Models under test can be named.

## Commit messages

Start with a lowercase type and a colon, then a short summary, with details in
the body:

- `add:` something new: a file, test, check, feature or result
- `update:` a change to something that already exists
- `fix:` a bug fix
- Anything else uses the same form, e.g. `remove:`

Examples: `add: glm-5-3 scored outputs (160.98/280)`,
`fix: capture reused a manifest with failed episodes`.

## License

By contributing, you agree that code contributions are licensed under the
[MIT License](LICENSE) and contributions to `outputs/` under
[CC BY 4.0](outputs/LICENSE).
