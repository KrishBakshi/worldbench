"""Validate one world.html against one test, several tests, or the full WC* ladder.

1. checks.structural.check_input_ready — fail fast if the file is missing/wrong.
2. For each selected test.yaml check: load + run_audited_check (LangSmith).

Direct test scripts do not call this. Harness does — that is what makes a
run auditable.
"""

from __future__ import annotations

import json
from pathlib import Path

from langsmith import traceable

from checks.structural import check_input_ready
from harness.audit import run_audited_check
from harness.loader import discover_tests, load_check, resolve_test
from harness.score import score_records


def validate(
    output_dir: Path,
    test_dir_name: str | None = None,
    *,
    test_dir_names: list[str] | None = None,
) -> dict:
    output_dir = Path(output_dir)
    model = output_dir.name.split("__", 1)[0]
    selected = _selected_tests(test_dir_name, test_dir_names)

    @traceable(
        name=f"{model}::pipeline",
        run_type="chain",
        metadata={
            "model": model,
            "tests": [t["dir_name"] for t in selected],
        },
    )
    def _run() -> dict:
        return _validate(output_dir, model, selected)

    return _run()


def _selected_tests(
    test_dir_name: str | None,
    test_dir_names: list[str] | None,
) -> list[dict]:
    all_tests = discover_tests()
    if test_dir_names:
        return [resolve_test(name, all_tests) for name in test_dir_names]
    if test_dir_name:
        return [resolve_test(test_dir_name, all_tests)]
    return all_tests


def _validate(output_dir: Path, model: str, selected: list[dict]) -> dict:
    structural = check_input_ready(output_dir)
    result = {
        "model": model,
        "tests": [t["dir_name"] for t in selected],
        "structural": {
            "passed": structural.passed,
            "reason": structural.reason,
            "details": structural.details,
        },
        "checks": {},
    }

    if not structural.passed:
        result["passed"] = False
        result.update(score_records({}))
        _write(output_dir, result)
        return result

    world_html = str(output_dir / "world.html")
    checks_passed = True
    for test in selected:
        test_out = output_dir / test["dir_name"]
        test_out.mkdir(parents=True, exist_ok=True)
        for check in test["checks"]:
            key = f"{test['dir_name']}::{check['function']}"
            try:
                check_fn = load_check(test["path"] / check["script"], check["function"])
                record = run_audited_check(
                    check_fn,
                    world_html,
                    test_id=test["dir_name"],
                    model=model,
                    out_dir=test_out,
                )
            except Exception as exc:
                record = {
                    "passed": False,
                    "reason": str(exc),
                    "score": 0,
                    "max_score": 0,
                    "details": {"error": str(exc)},
                }
            result["checks"][key] = record
            checks_passed = checks_passed and bool(record.get("passed"))

    result["passed"] = checks_passed
    result.update(score_records(result["checks"]))
    _write(output_dir, result)
    return result


def _write(output_dir: Path, result: dict) -> None:
    (output_dir / "validation.json").write_text(json.dumps(result, indent=2, default=str))
