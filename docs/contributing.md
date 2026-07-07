# Contributing to WorldBench

Thanks for helping build WorldBench. This guide covers the workflow and the bar
for changes.

## Workflow

1. **Fork & branch.** Create a topic branch off `main`
   (`feature/…`, `fix/…`, `task/…`).
2. **Set up the dev environment** (see the [Developer Guide](developer_guide.md)):
   `pip install -e '.[dev]'`.
3. **Make focused changes.** One logical change per pull request.
4. **Add or update tests.** Every behavioral change needs test coverage.
5. **Run the checks locally** (all must pass):
   ```bash
   pytest
   ruff check benchmark tests
   mypy benchmark
   ```
6. **Regenerate the schema** if you touched the models:
   ```bash
   python -m benchmark.schemas.export_schema
   ```
7. **Open a PR** with a clear description of what and why.

## Where changes go

| Change                          | Location                                            |
|---------------------------------|-----------------------------------------------------|
| Schema field / entity           | `benchmark/models/` (+ regenerate JSON Schema)      |
| Ecological rule                 | `benchmark/knowledge/*.yaml`                        |
| New / updated validator         | `benchmark/validators/` (+ register in `composite`) |
| New / updated metric            | `benchmark/metrics/` (+ `weights.yaml`)             |
| Model provider adapter          | `benchmark/runner/adapters/`                        |
| Benchmark task                  | `prompts/<category>/` (see task authoring guide)    |
| Report format                   | `benchmark/reports/`                                |

## Standards

- Python 3.12+, full type annotations, `from __future__ import annotations`.
- Docstrings on modules and public functions — explain intent.
- Pydantic models forbid extra fields; keep input strict.
- Prefer editing the YAML ontology over hard-coding ecology in Python.
- No `TODO` placeholders in committed code.
- Keep adapters SDK-free — HTTP via `httpx`, credentials from env vars.

## PR checklist

- [ ] Tests added/updated and `pytest` is green
- [ ] `ruff` and `mypy` are clean
- [ ] JSON Schema regenerated if models changed
- [ ] Docs updated if behavior or interfaces changed
- [ ] No secrets, API keys, or large binaries committed
- [ ] Change stays in scope: **natural environments only**, no civilization

## Reporting issues

Open an issue describing the expected vs. actual behavior, a minimal `world.json`
that reproduces it, and the WorldBench version / schema version.
