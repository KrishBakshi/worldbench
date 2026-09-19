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
import types
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


def _evict_loaded_tests() -> None:
    """Drop modules imported from a previous WC* folder.

    WC002–WC005 each ship main.py / llm.py / grade.py and do `from llm import`.
    Loading them by filename leaves those names in sys.modules, so WC003+
    bind WC002's copies and never reach run_audited_check (no LangSmith span).
    """
    tests_root = TESTS_DIR.resolve()
    to_drop = [
        name
        for name, mod in sys.modules.items()
        if name == "worldbench_checks" or name.startswith("worldbench_checks.")
    ]
    for name, mod in sys.modules.items():
        file = getattr(mod, "__file__", None)
        if not file:
            continue
        try:
            resolved = Path(file).resolve()
        except OSError:
            continue
        if resolved.is_relative_to(tests_root):
            to_drop.append(name)
    for name in to_drop:
        sys.modules.pop(name, None)


def _ensure_namespace(name: str) -> None:
    if name in sys.modules:
        return
    pkg = types.ModuleType(name)
    pkg.__path__ = []
    pkg.__package__ = name
    sys.modules[name] = pkg


def load_check(module_path: str | Path, function_name: str):
    """Load `function_name` from the Python file at `module_path`.

    Registers the module in sys.modules before exec'ing it — required
    for @dataclass-decorated classes in the loaded module to work; without
    it, dataclasses' own introspection can't find the module and raises.

    Each WC* folder is loaded under a unique name (not just `main`) and
    previous test modules are evicted so llm/grade/probe do not leak.
    """
    module_path = Path(module_path)
    _evict_loaded_tests()
    parent = f"worldbench_checks.{module_path.parent.name}"
    qualname = f"{parent}.{module_path.stem}"
    _ensure_namespace("worldbench_checks")
    _ensure_namespace(parent)
    spec = importlib.util.spec_from_file_location(qualname, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualname] = module
    spec.loader.exec_module(module)
    return getattr(module, function_name)
