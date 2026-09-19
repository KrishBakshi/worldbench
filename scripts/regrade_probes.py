"""Re-score WC003/WC004 from saved probe JSON (no new LLM calls) and patch validation.json.

Usage:
    uv run python scripts/regrade_probes.py fable
    uv run python scripts/regrade_probes.py --all
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from eval.score import score_records  # noqa: E402
from harness.status import log  # noqa: E402

OUTPUTS_DIR = REPO_ROOT / "outputs"
WC003 = REPO_ROOT / "tests" / "WC003_biome_micro_contents" / "main.py"
WC004 = REPO_ROOT / "tests" / "WC004_biome_rendering" / "main.py"


def _patch_check(validation: dict, dir_name: str, function: str, scorecard: dict, extra: dict) -> None:
    key = f"{dir_name}::{function}"
    details = {
        "score": scorecard["score"],
        "max_score": scorecard["max_score"],
        "scorecard": scorecard,
        **extra,
    }
    validation.setdefault("checks", {})[key] = {
        "passed": scorecard["passed"],
        "reason": scorecard["reason"],
        "details": details,
        "score": scorecard["score"],
        "max_score": scorecard["max_score"],
    }


def _regrade_cli(script: Path, json_path: Path) -> dict:
    subprocess.run(
        [sys.executable, str(script), "--regrade", str(json_path)],
        check=True,
        cwd=str(REPO_ROOT),
    )
    return json.loads((json_path.parent / "score.json").read_text(encoding="utf-8"))


def regrade_slug(slug: str) -> Path:
    out = OUTPUTS_DIR / slug
    val_path = out / "validation.json"
    if not val_path.is_file():
        raise FileNotFoundError(f"No validation.json at {val_path}")
    validation = json.loads(val_path.read_text(encoding="utf-8"))

    micro = out / "WC003_biome_micro_contents" / "micro_contents.json"
    if micro.is_file():
        log(f"regrade WC003  {slug}")
        card = _regrade_cli(WC003, micro)
        _patch_check(
            validation,
            "WC003_biome_micro_contents",
            "check_biome_micro_contents",
            card,
            extra={
                "found": card.get("found", {}),
                "missing": card.get("missing", {}),
            },
        )

    rendering = out / "WC004_biome_rendering" / "rendering.json"
    if rendering.is_file():
        log(f"regrade WC004  {slug}")
        card = _regrade_cli(WC004, rendering)
        _patch_check(
            validation,
            "WC004_biome_rendering",
            "check_biome_rendering",
            card,
            extra={
                "found": card.get("found", {}),
                "missing": card.get("missing", {}),
            },
        )

    checks = validation.get("checks") or {}
    validation["passed"] = all(bool(row.get("passed")) for row in checks.values())
    validation.update(score_records(checks))
    val_path.write_text(json.dumps(validation, indent=2, default=str) + "\n", encoding="utf-8")
    return val_path


def discover_slugs() -> list[str]:
    if not OUTPUTS_DIR.is_dir():
        return []
    slugs = []
    for path in sorted(OUTPUTS_DIR.iterdir()):
        if path.is_dir() and (path / "validation.json").is_file() and "__" not in path.name:
            slugs.append(path.name)
    return slugs


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Re-score WC003/WC004 probe JSON into validation.json")
    parser.add_argument("slug", nargs="?", help='model folder under outputs/ (e.g. "fable")')
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)
    slugs = discover_slugs() if args.all else ([args.slug] if args.slug else [])
    if not slugs:
        parser.error("pass a slug or --all")
    for slug in slugs:
        dest = regrade_slug(slug)
        log(f"wrote   {dest}")
        print(dest, flush=True)


if __name__ == "__main__":
    main()
