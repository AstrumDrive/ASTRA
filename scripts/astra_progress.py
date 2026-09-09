#!/usr/bin/env python3
"""Watch ASTRA cycles from a terminal, and summarise cycle telemetry.

  python scripts/astra_progress.py              one-shot: in-flight + recent
  python scripts/astra_progress.py --watch 30   refresh every 30 s (Ctrl+C to stop)
  python scripts/astra_progress.py --summary    per-cycle table + per-goal aggregates

Read-only; uses the same heartbeat/checkpoint files ASTRA already writes
(core/cycle_telemetry.py). ASCII-only output on purpose so a Windows console
with a cp1252 locale never chokes on it. Reads are brief: astra_tool finalises
checkpoints with os.replace(), which a held-open target can make fail on Windows.
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core import cycle_telemetry as ct  # noqa: E402

PROGRESS_DIR = os.path.join(ROOT, "workspace", "progress")
CKPT_DIR = os.path.join(ROOT, "workspace", "cycle_checkpoints")


def _pid_alive(pid) -> bool:
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not h:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return code.value == 259
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _fmt_s(v) -> str:
    return "-" if v is None else f"{float(v):.0f}s"


def live_view(recent_n: int = 5) -> str:
    files = sorted(glob.glob(os.path.join(PROGRESS_DIR, "cycle_*.json")),
                   key=os.path.getmtime, reverse=True)[:12]
    in_flight, recent = [], []
    for f in files:
        d = ct.load_json(f)
        if not d:
            continue
        e = ct.enrich_progress(d, _pid_alive(d.get("pid")))
        (in_flight if e["state"] == "running" else recent).append(e)
    lines = [f"ASTRA cycles @ {time.strftime('%H:%M:%S')}"]
    if in_flight:
        for e in in_flight:
            ph = e.get("timings") or {}
            rev = f" revision={e['revision']}" if e.get("revision") is not None else ""
            strict = " strict" if e.get("strict_contract") else ""
            lines.append(
                f"  RUNNING pid={e.get('pid')} phase={e.get('stage')} heartbeat={e['age_s']}s ago "
                f"round={e.get('review_rounds', 0)}{rev} budget_left={_fmt_s(e.get('budget_remaining_s'))}"
                f"{strict} phases={{{', '.join(f'{k}:{_fmt_s(v)}' for k, v in ph.items() if k != 'total')}}}"
            )
    else:
        lines.append("  (no cycle in flight)")
    if recent:
        lines.append("  recent:")
        for e in recent[:recent_n]:
            tag = {"finished": "FINISHED", "exited": "EXITED", "killed": "KILLED"}.get(e["state"], e["state"])
            strict = " strict" if e.get("strict_contract") else ""
            lines.append(
                f"    {tag} pid={e.get('pid')} outcome={e.get('outcome', e.get('stage'))}"
                f" rounds={e.get('review_rounds', 0)} total={_fmt_s((e.get('timings') or {}).get('total'))}"
                f"{strict} cause={e.get('stop_cause', '-')}"
            )
    return "\n".join(lines)


def summary_view(limit: int = 30) -> str:
    rows = ct.list_checkpoints(CKPT_DIR, limit=limit)
    agg = ct.summarize(rows)
    lines = [f"ASTRA cycle telemetry (last {len(rows)} cycles)", ""]
    lines.append(f"{'#':>3} {'state':<10} {'outcome':<26} {'rnd':>3} {'total':>7} {'strict':<6} stop cause")
    for i, r in enumerate(rows, start=1):
        strict = "yes" if r.get("strict_contract") else ("no" if r.get("strict_contract") is False else "-")
        lines.append(
            f"{i:>3} {r['state']:<10} {r['outcome']:<26} {r['review_rounds']:>3} "
            f"{_fmt_s(r['duration_s']):>7} {strict:<6} {r['stop_cause']}"
        )
    lines.append("")
    lines.append(
        f"cycles={agg['cycles']} finished={agg['finished_cycles']} incomplete={agg['incomplete_cycles']} "
        f"decisive={agg['decisive_cycles']} goals={agg['goals']} resolved={agg['goals_resolved']} "
        f"mean={_fmt_s(agg['mean_duration_s'])} median={_fmt_s(agg['median_duration_s'])} "
        f"review_rounds_total={agg['total_review_rounds']}"
    )
    lg = agg.get("latest_goal")
    if lg:
        lines.append(
            f"latest goal: '{lg['goal']}' -> cycles={lg['cycles']} finished={lg['finished']} "
            f"rounds={lg['rounds']} decisive={lg['decisive']} cycles_to_decisive={lg['cycles_to_decisive']}"
        )
    lines.append(f"by_outcome={agg['by_outcome']}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--watch", type=int, metavar="SECONDS", help="refresh interval; omit for one-shot")
    ap.add_argument("--summary", action="store_true", help="per-cycle telemetry table + aggregates")
    ap.add_argument("--limit", type=int, default=30, help="cycles to include in --summary")
    args = ap.parse_args()
    if args.summary:
        print(summary_view(args.limit))
        return 0
    if not args.watch:
        print(live_view())
        return 0
    try:
        while True:
            os.system("cls" if os.name == "nt" else "clear")
            print(live_view())
            print(f"\n(refreshing every {args.watch}s; Ctrl+C to stop)")
            time.sleep(args.watch)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
