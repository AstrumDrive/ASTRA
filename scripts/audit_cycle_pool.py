"""Efficiency audit of the deliberative-cycle pool (workspace/cycle_checkpoints).

Read-only. Prints the figures cited by docs/evidence/ASTRA_EFFICIENCY_AUDIT_*.md
so that every number in that document can be regenerated from the checkpoints
on disk. Test-suite artifacts (intuition starting with "Test " or sub-5-second
cycles) are excluded; the 2026-08-17 standard-tier benchmark batch is reported
separately from research cycles.

Usage: venv/Scripts/python.exe scripts/audit_cycle_pool.py [--csv out.csv]
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import json
import os
import re
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FINISHED = ("done", "failed", "partial", "tool_error", "code_error")
DECISIVE = ("VALIDATED", "REFUTED")


def load_pool() -> list[dict]:
    rows = []
    for path in sorted(glob.glob(str(ROOT / "workspace" / "cycle_checkpoints" / "*.json"))):
        try:
            d = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        r = d.get("result") or {}
        created, updated = d.get("created_ts") or 0, d.get("updated_ts") or 0
        wall = (updated - created) if created and updated else None
        intuition = d.get("intuition") or ""
        if intuition.startswith("Test ") or (wall is not None and wall < 5):
            continue
        day = dt.datetime.fromtimestamp(created) if created else None
        benchmark = bool(re.match(r"^(Test the claim|Claim:|Decide whether|Determine whether)", intuition)) or (
            day is not None and day.strftime("%Y-%m-%d") == "2026-08-17" and 2 <= day.hour <= 6
        )
        timings = {k: v for k, v in (d.get("timings") or r.get("timings") or {}).items() if isinstance(v, (int, float))}
        cost = r.get("cli_cost_usd")
        if isinstance(cost, dict):
            cost = sum(v for v in cost.values() if isinstance(v, (int, float)))
        error = str(d.get("error") or r.get("error") or "")
        hist = d.get("code_review_history") or []
        labels = []
        for h in hist:
            rv = h.get("review") or h
            labels.extend(rv.get("defect_labels") or rv.get("labels") or [])
        rows.append({
            "file": os.path.basename(path),
            "month": day.strftime("%Y-%m") if day else "",
            "benchmark": benchmark,
            "finished": d.get("stage") in FINISHED,
            "stage": d.get("stage"),
            "status": r.get("status") or "",
            "decisive": (r.get("status") or "") in DECISIVE,
            "oracle_ran": bool((r.get("execution") or {}).get("exit_code") is not None or r.get("oracle_verdict")),
            "wall_s": wall,
            "rounds": len(hist),
            "retries": r.get("retries") or 0,
            "cost_usd": cost if isinstance(cost, (int, float)) else None,
            "ocv": (r.get("original_claim_verdict") or "").upper() if "original_claim_verdict" in r else None,
            "error_class": classify_error(error),
            "labels": labels,
            "timings": timings,
            "goal": (d.get("shared_goal") or {}).get("objective") if isinstance(d.get("shared_goal"), dict) else (d.get("request") or {}).get("objective") if isinstance(d.get("request"), dict) else "",
            "intuition": intuition[:80].replace("\n", " "),
        })
    return rows


def classify_error(error: str) -> str:
    if not error:
        return ""
    if "did not approve" in error:
        return "reviewer_never_approved"
    if "Review stuck" in error:
        return "review_stuck_same_class"
    if "CUOTA AGOTADA" in error or "usage limit" in error:
        return "quota_exhausted"
    if "timeout tras" in error:
        return "cli_timeout"
    if error.startswith("API_ERROR"):
        return "api_error_other"
    return "other"


def pct(n: int, d: int) -> str:
    return f"{n}/{d} = {100 * n / d:.0f}%" if d else "n/a"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", help="write one row per cycle to this path")
    args = ap.parse_args()
    rows = load_pool()
    fin = [x for x in rows if x["finished"]]
    research = [x for x in fin if not x["benchmark"]]
    bench = [x for x in fin if x["benchmark"]]
    print(f"cycles (non-test): {len(rows)}  finished: {len(fin)}  incomplete/killed: {len(rows) - len(fin)}")
    print(f"benchmark batch (2026-08-17): {len(bench)}  decisive {pct(sum(x['decisive'] for x in bench), len(bench))}")
    print(f"research cycles: {len(research)}  decisive {pct(sum(x['decisive'] for x in research), len(research))}"
          f"  statuses={Counter(x['status'] or '(none)' for x in research).most_common()}")
    print(f"oracle actually ran (research): {pct(sum(x['oracle_ran'] for x in research), len(research))}")
    print("\nper month (research): finished / decisive / oracle ran / median wall")
    for m in sorted({x["month"] for x in research}):
        g = [x for x in research if x["month"] == m]
        walls = [x["wall_s"] for x in g if x["wall_s"]]
        print(f"  {m}: {len(g):3}  decisive {pct(sum(x['decisive'] for x in g), len(g)):>14}"
              f"  oracle {pct(sum(x['oracle_ran'] for x in g), len(g)):>14}  median wall {st.median(walls):.0f}s")
    print("\nwhy research cycles end without a verdict:")
    for k, n in Counter(x["error_class"] for x in research if not x["decisive"] and x["status"] != "NON_DECIDABLE").most_common():
        print(f"  {n:4}  {k or '(no error recorded)'}")
    walls = [x["wall_s"] for x in research if x["wall_s"]]
    dec_walls = [x["wall_s"] for x in research if x["decisive"] and x["wall_s"]]
    print(f"\nwall time (research): median {st.median(walls):.0f}s, p75 {sorted(walls)[3 * len(walls) // 4]:.0f}s,"
          f" total {sum(walls) / 3600:.1f} h; decisive median {st.median(dec_walls):.0f}s;"
          f" hours per decisive verdict {sum(walls) / 3600 / max(1, len(dec_walls)):.2f}")
    costs = [x["cost_usd"] for x in research if x["cost_usd"]]
    if costs:
        dec_cost = [x["cost_usd"] for x in research if x["cost_usd"] and x["decisive"]]
        print(f"cli_cost_usd (research cycles carrying telemetry, n={len(costs)}): total {sum(costs):.2f},"
              f" median {st.median(costs):.2f}, per decisive verdict {sum(costs) / max(1, len(dec_cost)):.2f}")
    agg = defaultdict(float)
    for x in research:
        for k, v in x["timings"].items():
            if k != "total":
                agg[k] += v
    total = sum(agg.values()) or 1
    print("\nphase share of model/oracle time (research):")
    for k, v in sorted(agg.items(), key=lambda kv: -kv[1]):
        print(f"  {k:18} {100 * v / total:5.1f}%")
    print("\nreview rounds (research):", Counter(x["rounds"] for x in research).most_common())
    print("retries (research):", Counter(x["retries"] for x in research).most_common())
    print("reviewer defect labels, all rounds:", Counter(l for x in research for l in x["labels"]).most_common(8))
    # In-use monitoring of the re-anchored axis (production since 2026-09-30).
    # A VALIDATED whose original_claim_verdict is not SUPPORTED is exactly the
    # case the old production reported as a plain VALIDATED: the cycle proved a
    # corrected or contrary statement, not the claim that was asked.
    anchored = [x for x in research if x["ocv"] is not None]
    if anchored:
        decisive_anchored = [x for x in anchored if x["decisive"]]
        discordant = [x for x in decisive_anchored if x["status"] == "VALIDATED" and x["ocv"] != "SUPPORTED"]
        print(f"\nre-anchored axis: cycles carrying it {len(anchored)}; decisive {len(decisive_anchored)};"
              f" original_claim_verdict={Counter(x['ocv'] for x in decisive_anchored).most_common()}")
        print(f"  VALIDATED that do NOT support the asked claim (would have misled before the port):"
              f" {pct(len(discordant), len([x for x in decisive_anchored if x['status'] == 'VALIDATED']))}")
        for x in discordant[:5]:
            print(f"    {x['month']} {x['ocv']:12} {x['intuition'][:70]}")
    goals = defaultdict(list)
    for x in research:
        goals[x["goal"] or x["intuition"]].append(x)
    reached = {g: v for g, v in goals.items() if any(x["decisive"] for x in v)}
    first = Counter(next(i for i, x in enumerate(sorted(v, key=lambda x: x["file"])) if x["decisive"]) + 1 for v in reached.values())
    print(f"\ndistinct research goals: {len(goals)}; reached a verdict: {pct(len(reached), len(goals))};"
          f" cycle on which it was reached: {dict(sorted(first.items()))}")
    multi = sorted(((len(v), g[:70]) for g, v in goals.items() if g not in reached and len(v) > 1), reverse=True)[:5]
    print("goals retried without ever reaching a verdict (cycles, goal):")
    for n, g in multi:
        print(f"  {n}  {g}")
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            fields = [k for k in rows[0] if k not in ("labels", "timings")]
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            for x in rows:
                w.writerow({k: x[k] for k in fields})
        print("csv:", args.csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
