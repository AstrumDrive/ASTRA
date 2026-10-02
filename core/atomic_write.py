"""Atomic JSON writes that survive a reader holding the target open on Windows.

The job runners publish their state as ``<jobdir>/job.json`` every ~5 s by
writing ``job.json.tmp`` and ``os.replace``-ing it over the target.  On
Windows that rename fails with ``PermissionError`` (WinError 5 or 32) while
any other process has the target open without FILE_SHARE_DELETE, which is
how CPython's own ``open()`` and most tools (grep, type, an editor) open it.

On 2026-10-02 a ``grep`` poll over the job files collided with one heartbeat
(workspace/jobs/cycle_20261002_143555_c756/runner.err): the bare
``os.replace`` raised, the cycle runner died, and ``astra_job`` reported the
job as ``killed`` with a frozen heartbeat while the nested astra_tool cycle
went on to finish VALIDATED.  Its result reached stdout.log, never job.json.

A reader holds the file for milliseconds, so the collision is transient:
retry with a short backoff.  A heartbeat must never take the runner down
either; the caller keeps the whole state in memory and the next heartbeat
rewrites it, so a write that still fails is logged and dropped.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Callable, TypeVar

# 10 attempts with delays 50, 100, 200, 200, ... ms: about 1.6 s in the worst
# case, well inside the 5 s heartbeat period.
DEFAULT_ATTEMPTS = 10
# A runner's last write carries the final result; give it about 10 s.
FINAL_ATTEMPTS = 50
BASE_DELAY_S = 0.05
MAX_DELAY_S = 0.2

_T = TypeVar("_T")


def backoff_delay(attempt: int) -> float:
    """Delay before retry number ``attempt + 1`` (0-based): 50 ms doubling to 200 ms."""
    return min(MAX_DELAY_S, BASE_DELAY_S * (2 ** attempt))


def _retry_on_permission_error(
    operation: Callable[[], _T],
    attempts: int,
    sleep: Callable[[float], Any],
) -> _T:
    attempts = max(1, int(attempts))
    for attempt in range(attempts):
        try:
            return operation()
        except PermissionError:
            if attempt == attempts - 1:
                raise
            sleep(backoff_delay(attempt))
    raise AssertionError("unreachable")  # pragma: no cover


def replace_with_retry(
    source,
    target,
    *,
    attempts: int = DEFAULT_ATTEMPTS,
    sleep: Callable[[float], Any] = time.sleep,
) -> None:
    """``os.replace(source, target)``, retried while Windows denies the rename.

    Only ``PermissionError`` is retried; after ``attempts`` tries the last
    one is re-raised.  Any other ``OSError`` propagates at once.
    """
    source, target = os.fspath(source), os.fspath(target)
    _retry_on_permission_error(
        lambda: os.replace(source, target), attempts, sleep
    )


def write_json_atomic(
    path,
    payload: Any,
    *,
    attempts: int = DEFAULT_ATTEMPTS,
    sleep: Callable[[float], Any] = time.sleep,
    **dumps_kwargs: Any,
) -> None:
    """Publish ``payload`` as JSON at ``path`` through ``<path>.tmp``.

    Readers see either the previous file or the new one, never a partial
    write.  Raises when the write still fails after the retries; a failed
    rename leaves the newer state in ``<path>.tmp``.
    """
    path = os.fspath(path)
    temporary = path + ".tmp"
    text = json.dumps(payload, **dumps_kwargs)

    def _write_temporary() -> None:
        with open(temporary, "w", encoding="utf-8") as stream:
            stream.write(text)

    _retry_on_permission_error(_write_temporary, attempts, sleep)
    replace_with_retry(temporary, path, attempts=attempts, sleep=sleep)


def save_json_best_effort(
    path,
    payload: Any,
    *,
    label: str = "heartbeat",
    attempts: int = DEFAULT_ATTEMPTS,
    sleep: Callable[[float], Any] = time.sleep,
    **dumps_kwargs: Any,
) -> bool:
    """``write_json_atomic`` that never raises: on failure log to stderr, return False.

    For heartbeats and other periodic state: the caller keeps the state in
    memory and its next write retries.  A detached runner's stderr is its
    ``runner.err``, so the line lands next to the job it concerns.
    """
    try:
        write_json_atomic(
            path, payload, attempts=attempts, sleep=sleep, **dumps_kwargs
        )
        return True
    except Exception as exc:  # noqa: BLE001 - a lost write must not kill the runner
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        try:
            print(
                f"[{stamp}] {label}: {os.fspath(path)} not written after up "
                f"to {max(1, int(attempts))} attempts ({type(exc).__name__}: "
                f"{exc}); continuing",
                file=sys.stderr,
                flush=True,
            )
        except Exception:  # noqa: BLE001 - stderr may be closed in a detached runner
            pass
        return False
