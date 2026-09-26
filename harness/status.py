"""Flushed stderr progress so a long run does not look hung.

LLM probes (WC002–WC005) can sit on one call for a minute. Print a line
before each step, always to stderr, so stdout stays the score summary.

log() can also tee to files opened with log_to_file(). Teeing lives here
rather than in generate.py because this is already the single choke point
every node prints through: capturing at the sink means a transcript is
complete by construction, including anything added later, instead of being
a second thing each new node has to remember to write to.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO

_sinks: list[TextIO] = []


def log(message: str = "") -> None:
    print(message, file=sys.stderr, flush=True)
    for sink in _sinks:
        try:
            sink.write(message + "\n")
            sink.flush()  # flushed per line: a run killed mid-way still leaves a usable transcript
        except (ValueError, OSError):
            # A closed or broken sink must never take down the run whose
            # progress it was only meant to record.
            pass


@contextmanager
def log_to_file(path: Path) -> Iterator[Path]:
    """Tee everything log() prints into `path` for the duration of the block.

    Nested/concurrent sinks are fine — every open sink gets every line. The
    sink is always removed on exit, including on an exception, so a failed
    run doesn't leave a dangling handle teeing into later work.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("w", encoding="utf-8")
    _sinks.append(handle)
    try:
        yield path
    finally:
        if handle in _sinks:
            _sinks.remove(handle)
        handle.close()


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
