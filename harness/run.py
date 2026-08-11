"""CLI entrypoint: ingest a manually-produced input, validate it against
its test's checks, print the score. (No generate step yet — see
CLAUDE.md's "Future / deferred" note.)

Usage:
    uv run python -m harness.run <input-name>

<input-name> is a folder under inputs/, named
"<model>__<test_dir_name>" (test_dir_name matches a folder under tests/
exactly), e.g.:

    uv run python -m harness.run opus-5__WC001_trying_all_the_biomes
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from harness.ingest import ingest  # noqa: E402
from harness.score import score_report  # noqa: E402
from harness.validate import validate  # noqa: E402


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    name = sys.argv[1]
    if "__" not in name:
        print(f'Expected "<model>__<test_dir_name>", got: {name}')
        sys.exit(1)
    test_dir_name = name.split("__", 1)[1]

    try:
        output_dir = ingest(name)
    except FileNotFoundError as e:
        print(e)
        sys.exit(1)

    result = validate(output_dir, test_dir_name)

    print(f"test:   {result['test']}")
    print(f"model:  {result['model']}")
    print(f"passed: {result['passed']}")

    if not result["checks"]:
        print(f"structural: FAIL — {result['structural']['reason']}")
        sys.exit(1)

    for name, record in result["checks"].items():
        status = "PASS" if record["passed"] else "FAIL"
        print(f"  [{status}] {name}: {record['score']}/{record['max_score']} — {record['reason']}")

    report = score_report(
        {name: SimpleNamespace(**r) for name, r in result["checks"].items()}
    )
    print(f"score: {report['total_score']}/{report['total_max_score']} ({report['pct']:.0%})")
    print(f"\nWrote {output_dir / 'validation.json'}")


if __name__ == "__main__":
    main()
