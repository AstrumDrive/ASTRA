#!/usr/bin/env python3
"""Discard benchmark cycles that measured the harness instead of the system.

A cycle whose failure was caused by HOW it was run - not by the architecture
under test - must be removed before resuming, or it stays on the record as an
operational failure of that architecture and silently biases every rate
computed from the run.

Written for the incident of 2026-08-15
(`docs/evidence/ASTRA2_ABLATION_RUN2_20260815.md`): ten cycles resumed under
Windows Task Scheduler failed at `[WinError 5] Access is denied` while creating
the codex process, before any model was reached, whereas the nine run
interactively did not fail that way at all.

Removal is a TAIL truncation: cycles are appended in order, so the surviving
prefix keeps its numbering and the runner simply continues from there.
Contaminated cycles that are not at the tail are reported and refused, because
renumbering deposited evidence is not something a script should decide.

Usage:
    python scripts/drop_contaminated_cycles.py \\
        --run workspace/research_trajectory_runs/<run>/checkpoint.json \\
        --error-contains "WinError 5" [--apply]
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


def is_contaminated(cycle: dict[str, Any], needle: str) -> bool:
    error = str((cycle.get("result") or {}).get("error") or "")
    return needle.lower() in error.lower()


def plan_record(record: dict[str, Any], needle: str) -> tuple[int, list[int]]:
    """Return (kept_count, refused_indices) for one cell."""
    cycles = record.get("cycles") or []
    flags = [is_contaminated(cycle, needle) for cycle in cycles]
    keep = len(flags)
    while keep > 0 and flags[keep - 1]:
        keep -= 1
    # Anything still flagged below the truncation point is interleaved, not tail.
    refused = [i + 1 for i, bad in enumerate(flags[:keep]) if bad]
    return keep, refused


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--error-contains", required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Without this the script only reports what it would remove.",
    )
    args = parser.parse_args(argv)

    checkpoint = args.run.resolve()
    report = json.loads(checkpoint.read_text(encoding="utf-8"))
    run_dir = checkpoint.parent

    total_dropped = 0
    refused_any = False
    for record in report.get("records") or []:
        cycles = record.get("cycles") or []
        if not cycles:
            continue
        keep, refused = plan_record(record, args.error_contains)
        if refused:
            refused_any = True
            print(
                f"REFUSED {record['case_id']:30} {record['configuration']:12} "
                f"seed={record['seed']:<3} contaminated cycles not at the tail: "
                f"{refused}"
            )
            continue
        dropped = len(cycles) - keep
        if not dropped:
            continue
        total_dropped += dropped
        print(
            f"drop {dropped} of {len(cycles):<2} {record['case_id']:30} "
            f"{record['configuration']:12} seed={record['seed']:<3} "
            f"-> keeps {keep}"
        )
        if not args.apply:
            continue
        record["cycles"] = cycles[:keep]
        # The cell has to become resumable again: `complete` is skipped outright
        # and a stale stop_reason would end it after one look.
        record["state"] = "running" if keep else "pending"
        record.pop("stop_reason", None)
        record.pop("finished", None)
        cell_dir = run_dir / "cells" / record["case_id"] / record["blind_id"]
        for index in range(keep + 1, len(cycles) + 1):
            victim = cell_dir / f"cycle_{index:03d}"
            if victim.exists():
                shutil.rmtree(victim)

    if args.apply and total_dropped:
        report["state"] = "running"
        report["summary"] = {}
        checkpoint.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\napplied: {total_dropped} cycle(s) removed; resume the run.")
    elif total_dropped:
        print(f"\nwould remove {total_dropped} cycle(s); rerun with --apply.")
    else:
        print("nothing to remove.")
    return 1 if refused_any else 0


if __name__ == "__main__":
    raise SystemExit(main())
