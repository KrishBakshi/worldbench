"""Re-score saved probe/judge outputs with the current graders (no model calls) and patch validation.json.

For a grader change: every scored world must be regraded together, or totals
stop being comparable. Uses each test's own regrade_* function and
eval.gaps' validation update (island gate re-applied, `repairs` / `rechecks`
kept, a note appended to `details.repairs`); the files it rewrites are copied
to outputs/<model>/.repair_backups/<UTC time>/ first.

Usage:
    uv run python scripts/regrade_probes.py --tests WC004 WC005 --all --note "frame-loop motion check"
    uv run python scripts/regrade_probes.py --tests WC004 claude-opus-5
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from eval.gaps import OUTPUTS, WC003, WC004, WC005, _backup, _main_module, _update_validation, _worlds  # noqa: E402
from harness.status import log  # noqa: E402

# test -> (saved probe file, regrade function, files the regrade rewrites)
TESTS = {
    "WC003": (WC003, "micro_contents.json", "regrade_micro", ["score.json"]),
    "WC004": (WC004, "rendering.json", "regrade_rendering", ["score.json"]),
    "WC005": (WC005, "cycle.json", "regrade_cycle", ["score.json"]),
}


def regrade(model: str, tests: list[str], note_text: str) -> list[str]:
    O = OUTPUTS / model
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    lines = []
    for t in tests:
        test, probe_file, fn, rewrites = TESTS[t]
        D = O / test
        if not (D / probe_file).is_file():
            lines.append(f"{model} {t}: no {probe_file}, skipped")
            continue
        backup = _backup(model, [D / f for f in rewrites] + [O / "validation.json"])
        result = getattr(_main_module(test), fn)(D / probe_file)
        note = {"at": stamp, "did": [f"regrade: {note_text}"], "backup": str(backup.relative_to(O))}
        b, a, tb, ta = _update_validation(model, test, result, note)
        lines.append(f"{model} {t}: {b} -> {a} | total {tb} -> {ta}")
        log(f"      regrade   {lines[-1]}")
    return lines


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Re-score saved probe outputs into validation.json")
    parser.add_argument("models", nargs="*", help="model folders under outputs/")
    parser.add_argument("--all", action="store_true", help="every world with a validation.json")
    parser.add_argument("--tests", nargs="+", required=True, choices=sorted(TESTS))
    parser.add_argument("--note", default="grader change", help="recorded in details.repairs")
    args = parser.parse_args(argv)
    if not args.all and not args.models:
        parser.error("pass model names or --all")
    for m in _worlds([] if args.all else args.models):
        for line in regrade(m, args.tests, args.note):
            print(line, flush=True)


if __name__ == "__main__":
    main()
