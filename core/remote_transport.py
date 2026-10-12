"""SSH transport failures to ASTRUM: recognise them, retry them, probe early.

Measured 2026-10-07: 27 of the 28 CODE_ERROR cycles in the last 80 never ran
their validator. ssh exited 255 during the banner exchange ("Connection to
UNKNOWN port 65535 timed out", the Tailscale ProxyCommand). Each one had
already paid for conjecture, translation and review. Then the retry loop
treated the outage as a code defect and asked the models to repair a
validator that had nothing wrong with it.

Only failures that happen before an SSH session exists are recognised here.
At that point the remote command has certainly not started, so a retry cannot
duplicate a job. A connection that drops mid-session ("closed by remote
host") is deliberately not matched.
"""

from __future__ import annotations

import asyncio
import os
import re

# ssh's own pre-session diagnostics (OpenSSH on Windows, macOS and Linux).
_PRE_SESSION = re.compile(
    r"banner exchange"
    r"|kex_exchange_identification"
    r"|connection to \S+ port \d+ timed out"
    r"|connect to host \S+ port \d+: (connection (timed out|refused)|no route to host|network is unreachable)"
    r"|could not resolve hostname"
    r"|connection timed out during banner",
    re.IGNORECASE,
)


def is_transport_failure(exit_code, stdout: str, stderr: str) -> bool:
    """True when ssh never opened a session: exit 255, no stdout, and a
    pre-session diagnostic in stderr."""
    try:
        code = int(exit_code)
    except (TypeError, ValueError):
        return False
    return code == 255 and not (stdout or "").strip() and bool(_PRE_SESSION.search(stderr or ""))


def _env_int(name: str, default: int) -> int:
    try:
        return max(0, int(str(os.environ.get(name, default)).strip().strip("'\"")))
    except ValueError:
        return default


def transport_retries() -> int:
    """Extra attempts after a pre-session failure (default 2)."""
    return _env_int("ASTRA_REMOTE_TRANSPORT_RETRIES", 2)


def backoff_seconds(attempt: int) -> int:
    """Wait before retry `attempt` (1-based): 10 s, then 30 s by default."""
    base = _env_int("ASTRA_REMOTE_TRANSPORT_BACKOFF", 10)
    return base * (1 if attempt <= 1 else 3)


async def run_with_transport_retry(run, describe):
    """Run the blocking ssh call `run` in a thread, retrying pre-session
    failures. `describe(result)` returns (exit_code, stdout, stderr).
    Returns (result, attempts, transport_failed)."""
    attempts = 0
    while True:
        attempts += 1
        result = await asyncio.to_thread(run)
        code, out, err = describe(result)
        if not is_transport_failure(code, out, err):
            return result, attempts, False
        if attempts > transport_retries():
            return result, attempts, True
        await asyncio.sleep(backoff_seconds(attempts))


def transport_message(stderr: str, attempts: int) -> str:
    last = (stderr or "").strip().splitlines()
    detail = last[-1] if last else "ssh exited 255"
    return (
        f"ASTRUM unreachable over SSH after {attempts} attempt(s): {detail}. "
        "The validator did not run; this is not evidence about the claim."
    )
