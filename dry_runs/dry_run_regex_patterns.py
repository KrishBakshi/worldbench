"""Dev/testing script — not part of the harness pipeline (harness/, tests/).
This is a script we use while building the project, to sanity-check a
test's check function against real data before trusting it. Its own logic
should not be depended on by anything else — the shared piece it needs
(dynamic check loading) lives in harness/loader.py and is imported from
there, not defined here.

Everything dry-run related — this script and the world.html copies it
imports — lives in this dry_runs/ directory and nowhere else: not
scripts/, not the top-level inputs/ (which is reserved for real
harness/ingest.py input).

Currently hardcoded to WC001 (tests/WC001_trying_all_the_biomes/biome_check.py)
since that's the only real check that exists. Extend the CHECKS dict below
as more tests get real check scripts.

Imports (copies) each world.html into dry_runs/inputs/<slug>/world.html,
preserving which folder it came from as the slug, then runs the check
against every copy and prints a report. Answers one question per check:
is this regex/keyword pattern trustworthy enough to keep, or does it need
an LLM fallback?

Usage: uv run python dry_runs/dry_run_regex_patterns.py [path-to-worldbench-web]
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from harness.audit import run_audited_check  # noqa: E402
from harness.loader import load_check  # noqa: E402

DRY_RUN_DIR = Path(__file__).resolve().parent / "inputs"


# test folder -> (check script, function name)
CHECKS = {
    "WC001_trying_all_the_biomes": ("biome_check.py", "has_all_biomes"),
}


def find_world_htmls(web_repo: Path) -> list[tuple[str, Path]]:
    """Return (slug, path) for every world.html under web_repo, skipping
    node_modules/.next and the old/ archive. old/ is a gitignored,
    prior-pipeline archive (per worldbench-web/CLAUDE.md) — not real model
    outputs from the current prompt, so it doesn't belong in this corpus."""
    results = []
    for path in sorted(web_repo.rglob("world.html")):
        if "node_modules" in path.parts or ".next" in path.parts or "old" in path.parts:
            continue
        rel = path.relative_to(web_repo)
        slug = rel.parts[-2]  # public/tests/<slug>/world.html
        results.append((slug, path))
    return results


def import_worlds(web_repo: Path) -> list[tuple[str, Path]]:
    if DRY_RUN_DIR.exists():
        shutil.rmtree(DRY_RUN_DIR)
    DRY_RUN_DIR.mkdir(parents=True)

    imported = []
    for slug, src in find_world_htmls(web_repo):
        dest_dir = DRY_RUN_DIR / slug
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / "world.html"
        shutil.copy(src, dest)
        imported.append((slug, dest))
    return imported


def main():
    web_repo = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT.parent / "worldbench-web"
    if not web_repo.exists():
        print(f"worldbench-web not found at {web_repo}")
        sys.exit(1)

    imported = import_worlds(web_repo)
    if not imported:
        print(f"No world.html files found under {web_repo}")
        sys.exit(1)

    print(f"Imported {len(imported)} world.html file(s) from {web_repo}\n")

    for test_dir, (script_name, func_name) in CHECKS.items():
        check_fn = load_check(REPO_ROOT / "tests" / test_dir / script_name, func_name)

        print(f"=== {test_dir} :: {func_name} ===")
        rows = []
        for slug, path in imported:
            # Audited: same result as calling check_fn directly, plus this
            # call is a named, metadata-tagged LangSmith run (a no-op if
            # LangSmith isn't configured) — see harness/audit.py.
            record = run_audited_check(check_fn, str(path), test_id=test_dir, model=slug)
            rows.append((slug, record))
            status = "PASS" if record["passed"] else "FAIL"
            print(f"[{status}] {slug}: {record['score']}/{record['max_score']} — {record['reason']}")

        passed = sum(1 for _, r in rows if r["passed"])
        avg_score = sum(r["score"] for _, r in rows) / len(rows)
        print(f"{passed}/{len(rows)} passed | avg score {avg_score:.1f}/{rows[0][1]['max_score']}")

        all_missing = sorted({m for _, r in rows for m in r["details"].get("missing", [])})
        if all_missing:
            print(f"Missed across at least one world: {', '.join(all_missing)}")
        print()


if __name__ == "__main__":
    main()
