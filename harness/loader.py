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
