# Contributing

WorldBench welcomes contributions. The full guide — workflow, standards, and the
PR checklist — lives at **[docs/contributing.md](docs/contributing.md)**.

Quick version:

```bash
pip install -e '.[dev]'
pytest && ruff check benchmark tests && mypy benchmark
```

- One focused change per PR, with tests.
- Regenerate the schema (`python -m benchmark.schemas.export_schema`) if you
  touch the models.
- Stay in scope: **natural environments only** — no humans or civilization.
