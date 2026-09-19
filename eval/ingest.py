"""Copy a manually placed world.html into outputs/.

    inputs/<model>/world.html
        full ladder (every WC* test against that one world)

    inputs/<model>__<test_dir>/world.html
        legacy single-test folder; still valid for `eval.run model__WC00N_...`

No generate step — see CLAUDE.md's deferred note.
"""

from __future__ import annotations

import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INPUTS_DIR = REPO_ROOT / "inputs"
OUTPUTS_DIR = REPO_ROOT / "outputs"


def ingest(model: str, test_dir_name: str | None = None) -> Path:
    """Copy world.html into outputs/<run_id>/ and return that directory.

    Prefers inputs/<model>/ (one world, any subset of tests). Falls back
    to inputs/<model>__<test_dir>/ when that is how the input was filed.
    """
    candidates: list[Path] = [INPUTS_DIR / model]
    if test_dir_name:
        candidates.insert(0, INPUTS_DIR / f"{model}__{test_dir_name}")

    src_dir = next((p for p in candidates if (p / "world.html").is_file()), None)
    if src_dir is None:
        wanted = " or ".join(str(p / "world.html") for p in candidates)
        raise FileNotFoundError(f"No world.html at {wanted}")

    dest_dir = OUTPUTS_DIR / src_dir.name
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(src_dir / "world.html", dest_dir / "world.html")
    return dest_dir
