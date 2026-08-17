"""CLI: ingest a world, validate it, print the score.

LangSmith is on this path only (see harness/audit.py). Direct
`uv run python tests/WC00N/...` does not trace.

Usage:
    uv run python -m harness.run <model>
        Full ladder: WC000 → WC005 against inputs/<model>/world.html

    uv run python -m harness.run <model> --test WC005
    uv run python -m harness.run <model> --test WC005_day_night_seasons
        One test, still through the harness (still traced).

    uv run python -m harness.run <model>__WC001_trying_all_the_biomes
        Legacy: inputs/<model>__<test_dir>/world.html, that test only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from harness.ingest import ingest  # noqa: E402
from harness.loader import resolve_test  # noqa: E402
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
        metavar="WC",
        help="run one test (WC005 or WC005_day_night_seasons). Omit to run the full ladder.",
    )
    args = parser.parse_args(argv)

    model, legacy_test = parse_name(args.name)
    test_dir_name = legacy_test
    if args.test:
        test_dir_name = resolve_test(args.test)["dir_name"]

    try:
        output_dir = ingest(model, test_dir_name)
    except FileNotFoundError as e:
        print(e)
        sys.exit(1)

    if test_dir_name is None and "__" not in args.name:
        result = validate(output_dir)
    else:
        result = validate(output_dir, test_dir_name)

    print(f"model:  {result['model']}")
    print(f"tests:  {', '.join(result['tests'])}")
    print(f"passed: {result['passed']}")

    if not result["checks"]:
        print(f"structural: FAIL — {result['structural']['reason']}")
        sys.exit(1)

    for name, record in result["checks"].items():
        status = "PASS" if record.get("passed") else "FAIL"
        score = record.get("score", 0)
        max_score = record.get("max_score", 0)
        reason = record.get("reason", "")
        print(f"  [{status}] {name}: {score}/{max_score} — {reason}")

    print(
        f"score: {result['total_score']}/{result['total_max_score']} "
        f"({result['pct']:.0%})"
    )
    print(f"\nWrote {output_dir / 'validation.json'}")


if __name__ == "__main__":
    main()
