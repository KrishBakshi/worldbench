"""Two-stage validation of one output against one test's checks.

1. checks.structural.check_input_ready(output_dir) — does world.html
   exist and look real. Fails fast with that reason; a test's content
   checks never run against a missing/wrong file.
2. Only if that passes: load and run every check listed in the test's
   test.yaml (script + function, relative to that test's own folder),
   via harness.loader + harness.audit (so every check run is a named,
   metadata-tagged LangSmith run — see harness/audit.py).

Writes validation.json into output_dir and returns the same dict.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from checks.structural import check_input_ready
from harness.audit import run_audited_check
from harness.loader import load_check

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / "tests"


def validate(output_dir: Path, test_dir_name: str) -> dict:
    output_dir = Path(output_dir)
    test_dir = TESTS_DIR / test_dir_name
    model = output_dir.name.split("__", 1)[0]

    structural = check_input_ready(output_dir)
    result = {
        "test": test_dir_name,
        "model": model,
        "structural": {"passed": structural.passed, "reason": structural.reason, "details": structural.details},
        "checks": {},
    }

    if not structural.passed:
        result["passed"] = False
        _write(output_dir, result)
        return result

    world_html = output_dir / "world.html"
    test_yaml = yaml.safe_load((test_dir / "test.yaml").read_text())

    checks_passed = True
    for check in test_yaml["checks"]:
        check_fn = load_check(test_dir / check["script"], check["function"])
        record = run_audited_check(check_fn, str(world_html), test_id=test_dir_name, model=model)
        result["checks"][check["function"]] = record
        checks_passed = checks_passed and record["passed"]

    result["passed"] = checks_passed
    _write(output_dir, result)
    return result


def _write(output_dir: Path, result: dict) -> None:
    (output_dir / "validation.json").write_text(json.dumps(result, indent=2))
