"""Flushed stderr progress so a long run does not look hung.

LLM probes (WC002–WC005) can sit on one call for a minute. Print a line
before each step, always to stderr, so stdout stays the score summary.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager


def log(message: str = "") -> None:
    print(message, file=sys.stderr, flush=True)


@contextmanager
def timed(label: str) -> Iterator[dict[str, str]]:
    """Print `running` then `done` with elapsed seconds.

    Set info['detail'] (e.g. '8/14 fail') to append it on the done line.
    """
    log(f"running  {label}")
    info: dict[str, str] = {}
    t0 = time.perf_counter()
    try:
        yield info
    except Exception as exc:
        dt = time.perf_counter() - t0
        log(f"error    {label}  {dt:.1f}s  {exc}")
        raise
    else:
        dt = time.perf_counter() - t0
        extra = f"  {info['detail']}" if info.get("detail") else ""
        log(f"done     {label}  {dt:.1f}s{extra}")
