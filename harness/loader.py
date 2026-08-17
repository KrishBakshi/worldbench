"""Shared dynamic import for test check scripts.

Each test keeps its own check script(s) in its own folder (e.g.
tests/WC001_trying_all_the_biomes/biome_check.py) rather than a shared
importable package, so loading one means importing by file path, not by
package name. Both harness/validate.py (the real pipeline) and
scripts/dry_run_regex_patterns.py (the dev tool that sanity-checks a
check against real data before it's trusted) need this exact same logic,
so it lives here once — dev scripts import it from here, not the other
way around.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / "tests"


def discover_tests() -> list[dict]:
    """Every WC* folder with a test.yaml, in ladder order (WC000, WC001, …)."""
    tests = []
    for yaml_path in sorted(TESTS_DIR.glob("WC*/test.yaml")):
        data = yaml.safe_load(yaml_path.read_text()) or {}
        tests.append(
            {
                "dir_name": yaml_path.parent.name,
                "id": data.get("id", yaml_path.parent.name),
                "title": data.get("title", ""),
                "checks": list(data.get("checks") or []),
                "path": yaml_path.parent,
            }
        )
    return tests


def resolve_test(name: str, tests: list[dict] | None = None) -> dict:
    """Match WC005, WC005_day_night_seasons, or the yaml id."""
    tests = tests if tests is not None else discover_tests()
    key = name.strip()
    for test in tests:
        if key in {test["dir_name"], test["id"]}:
            return test
    matches = [t for t in tests if t["dir_name"].startswith(key) or t["id"] == key]
    if len(matches) == 1:
        return matches[0]
    known = ", ".join(t["dir_name"] for t in tests)
    raise ValueError(f"Unknown test {name!r}. Known: {known}")


def load_check(module_path: str | Path, function_name: str):
    """Load `function_name` from the Python file at `module_path`.

    Registers the module in sys.modules before exec'ing it — required
    for @dataclass-decorated classes in the loaded module to work; without
    it, dataclasses' own introspection can't find the module and raises.
    """
    module_path = Path(module_path)
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return getattr(module, function_name)
