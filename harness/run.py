"""CLI: ingest a world, validate it, print the score.

LangSmith is on this path only (see harness/audit.py). Direct
`uv run python tests/WC00N/...` does not trace.

Usage:
    uv run python -m harness.run <model>
        Full ladder: WC000 → WC005 against inputs/<model>/world.html

    uv run python -m harness.run <model> --test WC000 --test WC001
    uv run python -m harness.run <model> --test WC000,WC001
        A subset, still through the harness. Existing scores for other tests are kept.

    uv run python -m harness.run <model>__WC001_trying_all_the_biomes
        Legacy: inputs/<model>__<test_dir>/world.html, that test only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
load_dotenv(REPO_ROOT / ".env")

from harness.ingest import ingest  # noqa: E402
from harness.loader import resolve_test  # noqa: E402
from harness.status import log  # noqa: E402
from harness.validate import validate  # noqa: E402


def parse_name(name: str) -> tuple[str, str | None]:
    if "__" in name:
        model, test_dir = name.split("__", 1)
        return model, test_dir
    return name, None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="WorldBench harness: score a world.html")
    parser.add_argument(
        "name",
        help='model folder under inputs/ (e.g. "fable"), or "model__test_dir" for a single test',
    )
    parser.add_argument(
        "--test",
        action="append",
        metavar="WC",
        help="run one test (WC000 or WC000_voxel_world). Repeat or comma-separate. Omit to run the full ladder.",
    )
    args = parser.parse_args(argv)

    model, legacy_test = parse_name(args.name)
    test_names: list[str] = []
    if legacy_test:
        test_names.append(legacy_test)
    for raw in args.test or []:
        test_names.extend(part.strip() for part in raw.split(",") if part.strip())

    test_dir_name = None
    test_dir_names = None
    if len(test_names) == 1:
        test_dir_name = resolve_test(test_names[0])["dir_name"]
    elif len(test_names) > 1:
        test_dir_names = [resolve_test(name)["dir_name"] for name in test_names]

    try:
        output_dir = ingest(model, test_dir_name or (test_dir_names[0] if test_dir_names else None))
    except FileNotFoundError as e:
        print(e)
        sys.exit(1)

    log(f"worldbench  {model}")
    log(f"work dir   {output_dir}")
    if test_dir_names:
        log(f"tests      {', '.join(test_dir_names)}")
    elif test_dir_name:
        log(f"test       {test_dir_name}")
    log()

    if test_dir_names:
        result = validate(output_dir, test_dir_names=test_dir_names)
    elif test_dir_name:
        result = validate(output_dir, test_dir_name)
    else:
        result = validate(output_dir)

    print(f"model:  {result['model']}", flush=True)
    print(f"tests:  {', '.join(result['tests'])}", flush=True)
    print(f"passed: {result['passed']}", flush=True)

    if not result["checks"]:
        print(f"structural: FAIL — {result['structural']['reason']}", flush=True)
        sys.exit(1)

    for name, record in result["checks"].items():
        status = "PASS" if record.get("passed") else "FAIL"
        score = record.get("score", 0)
        max_score = record.get("max_score", 0)
        reason = record.get("reason", "")
        print(f"  [{status}] {name}: {score}/{max_score} — {reason}", flush=True)

    print(
        f"score: {result['total_score']}/{result['total_max_score']} "
        f"({result['pct']:.0%})",
        flush=True,
    )
    print(f"\nWrote {output_dir / 'validation.json'}", flush=True)


if __name__ == "__main__":
    main()
