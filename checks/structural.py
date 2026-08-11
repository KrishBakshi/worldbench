"""Generic structural pre-checks, shared by every test.

Unlike a test's own content check (e.g. tests/WC001_.../biome_check.py,
which is specific to what that test looks for), these checks are the same
for every test: does the expected input exist, and does it look like a
real world.html, before any content check ever reads it. That's why this
lives in a shared top-level checks/ rather than inside a test folder.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Light signature a real Three.js world.html should contain somewhere in
# its source — enough to reject an empty file or an unrelated decoy
# without being a real parser.
WORLD_MARKERS = ("three", "canvas", "webgl")


@dataclass
class CheckResult:
    passed: bool
    reason: str
    details: dict = field(default_factory=dict)


def check_dir_exists(path: str | Path) -> CheckResult:
    path = Path(path)
    if path.is_dir():
        return CheckResult(passed=True, reason=f"{path} exists")
    return CheckResult(passed=False, reason=f"Input directory not found: {path}")


def check_world_html_present(dir_path: str | Path) -> CheckResult:
    world_html = Path(dir_path) / "world.html"
    if world_html.is_file():
        return CheckResult(passed=True, reason="world.html present", details={"path": str(world_html)})
    return CheckResult(passed=False, reason=f"world.html not found in {dir_path}")


def check_looks_like_world(html_path: str | Path) -> CheckResult:
    path = Path(html_path)
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not text.strip():
        return CheckResult(passed=False, reason=f"{path} is empty")

    lowered = text.lower()
    hits = [m for m in WORLD_MARKERS if m in lowered]
    if not hits:
        return CheckResult(
            passed=False,
            reason=f"{path} doesn't look like a Three.js world (no {'/'.join(WORLD_MARKERS)} marker found)",
        )
    return CheckResult(passed=True, reason="Looks like a world.html", details={"markers": hits})


def check_input_ready(dir_path: str | Path) -> CheckResult:
    """Composes the three checks above in order, stopping at the first
    failure. This is the one harness/validate.py actually calls before
    handing off to a test's content check."""
    dir_result = check_dir_exists(dir_path)
    if not dir_result.passed:
        return dir_result

    presence_result = check_world_html_present(dir_path)
    if not presence_result.passed:
        return presence_result

    world_html = Path(dir_path) / "world.html"
    sanity_result = check_looks_like_world(world_html)
    if not sanity_result.passed:
        return sanity_result

    return CheckResult(passed=True, reason="Input ready", details={"world_html": str(world_html)})
