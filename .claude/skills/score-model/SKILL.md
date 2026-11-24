---
name: score-model
description: Score a new model's world.html in this repo on its own bench/<slug> branch, then export results to worldbench-web. Use after worldbench-web has public/tests/<slug>/world.html.
---

1. `git fetch origin && git checkout -b bench/<slug> origin/main`.
2. `mkdir -p inputs/<slug>` and copy `../worldbench-web/public/tests/<slug>/world.html` into it (inputs/ is gitignored).
3. `uv run python -m eval.run <slug>` (long: run in background), then `uv run python -m eval.gaps find <slug>`; repair until clean.
4. Genuine run only: no failed checks, crashed capture, judge outages or unfinished rechecks. Otherwise stop and report. Never hand-edit scores.
5. Commit `outputs/<slug>/` alone as `add: <slug> scored outputs (<score>/280)`; push `-u`.
6. Export: `uv run python scripts/export_to_web.py <slug>`, then continue in worldbench-web (its `score-model` skill).
