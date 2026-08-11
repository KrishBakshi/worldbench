"""Only path for producing an output right now — no automated generation
exists (see CLAUDE.md's "Future / deferred" note). Copies a manually
placed input into outputs/, so validate.py always reads from the same
place regardless of how an output was produced.

Naming convention: inputs/<model>__<test_dir_name>/world.html, where
<test_dir_name> matches a folder under tests/ exactly (e.g.
"opus-5__WC001_trying_all_the_biomes"). That's how run.py knows which
test's checks to run against a given input.
"""

from __future__ import annotations

import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INPUTS_DIR = REPO_ROOT / "inputs"
OUTPUTS_DIR = REPO_ROOT / "outputs"


def ingest(name: str) -> Path:
    """name is a folder under inputs/, e.g. "opus-5__WC001_trying_all_the_biomes".
    Returns the outputs/<name>/ dir containing the copied world.html."""
    src = INPUTS_DIR / name / "world.html"
    if not src.is_file():
        raise FileNotFoundError(f"No world.html at {src}")

    dest_dir = OUTPUTS_DIR / name
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dest_dir / "world.html")
    return dest_dir
