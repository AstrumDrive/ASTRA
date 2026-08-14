"""Block until an ASTRA background job leaves the running state, then report.

`astra_cycle_submit` returns immediately and the job outlives the caller, so an
agent that wants to react when it finishes has to watch it. Polling from the
agent burns a turn per check; this waits in one process instead and prints the
outcome once, which is enough for a background runner to signal completion.

  python scripts/wait_for_job.py cycle_20260814_031010_f2fa
  python scripts/wait_for_job.py <job_id> --interval 120 --max-wait 7800
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "venv" / "Scripts" / "python.exe"
if not PYTHON.is_file():
    PYTHON = ROOT / "venv" / "bin" / "python"
ASTRA_TOOL = ROOT / "astra_tool.py"

TERMINAL = {"done", "failed", "killed", "cancelled"}


def job_status(job_id: str, timeout: int = 120) -> dict:
    proc = subprocess.run(
        [str(PYTHON), str(ASTRA_TOOL)],
        input=json.dumps({"action": "job", "job_id": job_id}),
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(ROOT),
    )
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    # Some builds print the whole payload at once rather than line by line.
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"status": "unknown", "raw": proc.stdout[-400:],
                "stderr": proc.stderr[-400:]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_id")
    parser.add_argument("--interval", type=int, default=90)
    parser.add_argument("--max-wait", type=int, default=8400)
    args = parser.parse_args(argv)

    started = time.monotonic()
    last = None
    while True:
        status = job_status(args.job_id)
        state = str(status.get("status") or "unknown").lower()
        if state != last:
            elapsed = int(status.get("elapsed_s") or 0)
            print(f"[{time.strftime('%H:%M:%S')}] {state}  elapsed={elapsed}s",
                  flush=True)
            last = state
        if state in TERMINAL:
            print()
            print(json.dumps(status, indent=2, ensure_ascii=False)[:4000])
            return 0
        if time.monotonic() - started > args.max_wait:
            print(f"Gave up waiting after {args.max_wait}s; job is still "
                  f"{state}. It keeps running: poll it again later.")
            return 2
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
