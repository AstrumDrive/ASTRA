"""G2 scheduler checks against the shared ASTRUM job manager.

`ASTRA2_ACCEPTANCE.md` G2 asks that scheduler attribution, concurrency limits,
timeouts and cancellation actually work, not merely that the code paths exist.
This submits small real jobs to the shared cluster manager and observes them.

Deliberately cheap and polite to a shared resource: every job is a few seconds
of sleep or arithmetic, nothing is left running, and cancellation is exercised
on a job this script itself created. No model quota is involved.

  python scripts/check_cluster_scheduler.py
  python scripts/check_cluster_scheduler.py --skip cancellation
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from core.cluster_client import (  # noqa: E402
    client_id,
    cluster_enabled,
    cluster_rpc,
    execute_cluster_code,
)

OUT_DIR = ROOT / "workspace" / "g2_astrum"


async def check_capacity() -> dict:
    """Capacity must report slots and the manager's view of the queue."""
    reply = await cluster_rpc({"action": "capacity"}, timeout=60)
    ok = isinstance(reply, dict) and not reply.get("error")
    return {
        "check": "capacity",
        "ok": bool(ok),
        "detail": reply if ok else str(reply)[:400],
    }


async def check_attribution() -> dict:
    """A submitted job must be attributed to THIS line's client id.

    The 2.0 line runs with a client id distinct from production's, so a job
    landing under the wrong owner would mean the two lines are
    indistinguishable to the shared manager.
    """
    mine = client_id()
    submit = await cluster_rpc(
        {
            "action": "submit",
            "code": "print('VERDICT: PASS')\n",
            "oracle": "astrum",
            "timeout": 60,
        },
        timeout=120,
    )
    job_id = (submit or {}).get("job_id")
    if not job_id:
        return {
            "check": "attribution",
            "ok": False,
            "detail": f"no job_id returned: {str(submit)[:300]}",
        }
    status = await cluster_rpc({"action": "job", "job_id": job_id}, timeout=60)
    owner = str(
        (status or {}).get("client_id")
        or (status or {}).get("client")
        or ""
    )
    blob = json.dumps(status, ensure_ascii=False)
    ok = mine in blob
    return {
        "check": "attribution",
        "ok": ok,
        "detail": {
            "expected_client_id": mine,
            "reported_owner": owner or "(not a top-level field)",
            "job_id": job_id,
            "found_in_record": ok,
        },
    }


async def check_timeout() -> dict:
    """A job past its timeout must be reported as such, not as a bad result.

    Goes through ``execute_cluster_code``, the path ASTRA actually uses, rather
    than a hand-built request. The first version of this check sent a field
    named ``timeout``; the contract is ``timeout_seconds``, so the manager
    silently applied its 3600 s default, the job finished and printed PASS -
    the check failed for the wrong reason and the scheduler was blameless.
    """
    reply = await execute_cluster_code(
        "import time\ntime.sleep(45)\nprint('VERDICT: PASS')\n",
        timeout=10,
    )
    blob = json.dumps(reply, ensure_ascii=False).lower()
    reported = any(
        token in blob for token in ("timeout", "timed out", "cancel", "125")
    )
    # The decisive part: an expired job must NOT surface as a scientific
    # verdict. A PASS here would mean wall-clock exhaustion masquerading as
    # evidence.
    clean = "verdict: pass" not in blob
    return {
        "check": "timeout",
        "ok": bool(reported and clean),
        "detail": {
            "timeout_reported": reported,
            "not_reported_as_pass": clean,
            "exit_code": reply.get("exit_code") if isinstance(reply, dict) else None,
            "reply": str(reply)[:300],
        },
    }


async def check_cancellation() -> dict:
    """A cancelled job must stop and be reported as cancelled."""
    submit = await cluster_rpc(
        {
            "action": "submit",
            "code": "import time\ntime.sleep(120)\nprint('VERDICT: PASS')\n",
            "oracle": "astrum",
            "timeout": 300,
        },
        timeout=120,
    )
    job_id = (submit or {}).get("job_id")
    if not job_id:
        return {
            "check": "cancellation",
            "ok": False,
            "detail": f"no job_id returned: {str(submit)[:300]}",
        }
    await asyncio.sleep(3)
    cancelled = await cluster_rpc(
        {"action": "cancel", "job_id": job_id}, timeout=60
    )
    await asyncio.sleep(3)
    status = await cluster_rpc({"action": "job", "job_id": job_id}, timeout=60)
    blob = json.dumps([cancelled, status], ensure_ascii=False).lower()
    ok = "cancel" in blob
    return {
        "check": "cancellation",
        "ok": ok,
        "detail": {
            "job_id": job_id,
            "cancel_reply": str(cancelled)[:200],
            "final_status": str(status)[:200],
        },
    }


CHECKS = {
    "capacity": check_capacity,
    "attribution": check_attribution,
    "timeout": check_timeout,
    "cancellation": check_cancellation,
}


async def main_async(args) -> int:
    if not cluster_enabled():
        print(
            "The shared cluster scheduler is disabled "
            "(ASTRA_REMOTE_SCHEDULER != 1)."
        )
        return 2
    print(f"client id: {client_id()}")
    skip = {name.strip() for name in args.skip.split(",") if name.strip()}
    results = []
    for name, func in CHECKS.items():
        if name in skip:
            print(f"[skip] {name}")
            continue
        print(f"[running] {name} ...", flush=True)
        started = time.monotonic()
        try:
            outcome = await func()
        except Exception as exc:  # a failed check must not hide the others
            outcome = {
                "check": name,
                "ok": False,
                "detail": f"{type(exc).__name__}: {exc}",
            }
        outcome["seconds"] = round(time.monotonic() - started, 1)
        results.append(outcome)
        print(f"[{'PASS' if outcome['ok'] else 'FAIL'}] {name:14s} "
              f"{outcome['seconds']:6.1f}s")
        if not outcome["ok"]:
            print(f"        {str(outcome['detail'])[:300]}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": "astra-scheduler-check/0.1",
        "client_id": client_id(),
        "results": results,
        "passed": sum(1 for r in results if r["ok"]),
        "total": len(results),
    }
    path = OUT_DIR / f"scheduler_check_{time.strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print()
    print(f"{report['passed']}/{report['total']} scheduler checks passed")
    print(f"report: {path}")
    return 0 if report["passed"] == report["total"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip", default="", help="comma-separated check names")
    args = parser.parse_args(argv)
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
