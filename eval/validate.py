"""Validate one world.html against one test, several tests, or the full WC* ladder.

1. checks.structural.check_input_ready — fail fast if the file is missing/wrong.
2. eval.capture.run.capture — once per world, if any selected test.yaml says
   needs_capture: the daytime preview, fixed views and the navigator agent's
   biome frames that every visual judge reads. A capture failure is recorded,
   not fatal; each visual test then reports its own failure.
3. For each selected test.yaml check: load + run_audited_check (LangSmith).

Direct test scripts do not call this. Harness does — that is what makes a
run auditable.
"""

from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from langsmith import traceable

from checks.structural import check_input_ready
from eval.audit import run_audited_check
from eval.capture.run import capture
from eval.loader import discover_tests, load_check, resolve_test
from eval.score import score_records
from eval.capture.llm import JudgeUnavailable  # noqa: E402
from harness.status import log, timed


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
    # Keys of checks that still exist in some test.yaml. Anything else in an
    # old validation.json (a removed test like the retired keyword-coverage test, a removed check like
    # check_voxel_world or check_bedrock) is dropped, so totals only ever sum
    # the current ladder.
    live_keys = {f"{t['dir_name']}::{c['function']}" for t in discover_tests() for c in t["checks"]}
    prev_path = output_dir / "validation.json"
    if prev_path.is_file() and not _is_full_ladder(selected):
        try:
            existing_checks = dict(json.loads(prev_path.read_text(encoding="utf-8")).get("checks") or {})
        except (OSError, json.JSONDecodeError):
            existing_checks = {}
        # Drop stale entries for tests being re-run this pass — otherwise a
        # check removed from a test's own test.yaml (or renamed) lingers in
        # validation.json forever, since nothing in this run ever overwrites
        # it. Only checks for tests NOT selected this run should carry over.
        selected_prefixes = tuple(f"{t['dir_name']}::" for t in selected)
        existing_checks = {
            key: record
            for key, record in existing_checks.items()
            if not key.startswith(selected_prefixes) and key in live_keys
        }

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
    if any(t.get("needs_capture") for t in selected):
        with timed("capture  views for the visual judges") as info:
            try:
                manifest = capture(output_dir)
                framed = sum(1 for b in manifest.get("biomes", {}).values() if b.get("status") == "found")
                info["detail"] = f"{len(manifest.get('views', {}))} views, {framed}/10 biomes framed"
                result["capture"] = {
                    "views": len(manifest.get("views", {})),
                    "biomes": {k: v.get("status") for k, v in manifest.get("biomes", {}).items()},
                    "time": manifest.get("time"),
                    "preview_ok": manifest.get("preview", {}).get("ok"),
                }
            except JudgeUnavailable:
                raise  # every test is judged by this model: nothing left to run
            except Exception as exc:
                info["detail"] = f"failed: {exc}"
                result["capture"] = {"error": str(exc)}
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
                except JudgeUnavailable:
                    raise
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
