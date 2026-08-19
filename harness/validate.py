"""Validate one world.html against one test, several tests, or the full WC* ladder.

1. checks.structural.check_input_ready — fail fast if the file is missing/wrong.
2. For each selected test.yaml check: load + run_audited_check (LangSmith).

Direct test scripts do not call this. Harness does — that is what makes a
run auditable.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from langsmith import traceable

from checks.structural import check_input_ready
from harness.audit import run_audited_check
from harness.loader import discover_tests, load_check, resolve_test
from harness.score import score_records
from harness.status import log, timed

# WC003 is 10 Gemini probes; WC004 is 10 more. Free-tier RPM needs a gap.
_GEMINI_PAUSE_AFTER_WC003_S = 20


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


def _is_full_ladder(selected: list[dict]) -> bool:
    return [t["dir_name"] for t in selected] == [t["dir_name"] for t in discover_tests()]


def _validate(output_dir: Path, model: str, selected: list[dict]) -> dict:
    structural = check_input_ready(output_dir)
    existing_checks: dict = {}
    prev_path = output_dir / "validation.json"
    if prev_path.is_file() and not _is_full_ladder(selected):
        try:
            existing_checks = dict(json.loads(prev_path.read_text(encoding="utf-8")).get("checks") or {})
        except (OSError, json.JSONDecodeError):
            existing_checks = {}

    result = {
        "model": model,
        "tests": [t["dir_name"] for t in selected],
        "structural": {
            "passed": structural.passed,
            "reason": structural.reason,
            "details": structural.details,
        },
        "checks": existing_checks,
    }

    if not structural.passed:
        log(f"structural  fail  {structural.reason}")
        result["passed"] = False
        result.update(score_records({}))
        _write(output_dir, result)
        return result

    world_html = str(output_dir / "world.html")
    n = len(selected)
    for i, test in enumerate(selected, 1):
        test_out = output_dir / test["dir_name"]
        test_out.mkdir(parents=True, exist_ok=True)
        title = test.get("title") or test["dir_name"]
        label = f"[{i}/{n}] {test['id']}  {title}"
        for check in test["checks"]:
            key = f"{test['dir_name']}::{check['function']}"
            with timed(label) as info:
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
                status = "pass" if record.get("passed") else "fail"
                info["detail"] = f"{record.get('score', 0)}/{record.get('max_score', 0)}  {status}"
            result["checks"][key] = record
        if test.get("id") == "WC003" and any(t.get("id") == "WC004" for t in selected[i:]):
            log(f"waiting  {_GEMINI_PAUSE_AFTER_WC003_S}s  Gemini free-tier rate limit")
            time.sleep(_GEMINI_PAUSE_AFTER_WC003_S)

    present = []
    for test in discover_tests():
        prefix = f"{test['dir_name']}::"
        if any(key.startswith(prefix) for key in result["checks"]):
            present.append(test["dir_name"])
    result["tests"] = present or [t["dir_name"] for t in selected]
    result["passed"] = all(bool(record.get("passed")) for record in result["checks"].values())
    result.update(score_records(result["checks"]))
    _write(output_dir, result)
    return result


def _write(output_dir: Path, result: dict) -> None:
    (output_dir / "validation.json").write_text(json.dumps(result, indent=2, default=str))
