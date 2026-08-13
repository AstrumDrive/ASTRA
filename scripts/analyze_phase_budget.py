"""Phase-time distribution from deposited quality-benchmark reports.

Reads every ``workspace/quality_benchmark_runs/quality_*.json`` and reports
how long each cycle phase actually takes, so the whole-cycle budget can be
allocated from data instead of intuition.  Consumes no model quota: it only
re-reads logs that were already paid for.

Censoring is handled explicitly.  A phase that stopped at its ceiling did not
"take" that long, it needed *at least* that long, so those observations are
counted separately and excluded from the percentiles.  Completed cycles - the
ones that reached the analysis phase - are the only uncensored evidence of
what a phase really costs.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNS = ROOT / "workspace" / "quality_benchmark_runs"

# Per-call ceilings in force when each report was produced. The reports do not
# record the environment, so the mapping is declared here from the session log
# and must be extended when new runs are added.
TRANSLATOR_CEILING = {
    "quality_20260813_043803": 480,
    "quality_20260813_153418": 480,
}
DEFAULT_CEILING = 240
LADDER_DEPTH = 2  # claude-opus-4-8,sonnet: a phase may retry once


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    low, high = int(pos), min(int(pos) + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def load_records(runs_dir: Path) -> list[dict]:
    records = []
    for path in sorted(runs_dir.glob("quality_*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        stem = path.stem
        ceiling = TRANSLATOR_CEILING.get(stem, DEFAULT_CEILING)
        for row in data.get("records", []):
            if row.get("track") != "cycle":
                continue
            detail = str(row.get("detail") or "")
            match = re.search(r"'timings': \{([^}]{0,600})\}", detail)
            if not match:
                continue
            timings = {
                phase: float(value)
                for phase, value in re.findall(
                    r"'(\w+)': ([\d.]+)", match.group(1)
                )
            }
            records.append(
                {
                    "run": stem,
                    "case": row.get("id"),
                    "observed": row.get("observed"),
                    "timings": timings,
                    "translator_ceiling": ceiling,
                    "completed": "analyze" in timings,
                }
            )
    return records


def phase_ceiling(phase: str, record: dict) -> int:
    base = (
        record["translator_ceiling"]
        if phase in {"translate", "translate_patch"}
        else DEFAULT_CEILING
    )
    return base


def is_censored(phase: str, seconds: float, record: dict) -> bool:
    """True when the phase plausibly stopped because it ran out of budget."""
    ceiling = phase_ceiling(phase, record)
    for depth in range(1, LADDER_DEPTH + 1):
        if abs(seconds - ceiling * depth) <= 0.06 * ceiling:
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    args = parser.parse_args(argv)

    records = load_records(args.runs)
    if not records:
        print(f"No cycle records with timings under {args.runs}")
        return 1

    completed = [r for r in records if r["completed"]]
    failed = [r for r in records if not r["completed"]]
    print(f"cycle records: {len(records)}  "
          f"completed: {len(completed)}  incomplete: {len(failed)}")
    print(f"runs: {len(set(r['run'] for r in records))}   "
          f"cases: {len(set(r['case'] for r in records))}")

    uncensored: dict[str, list[float]] = defaultdict(list)
    censored: dict[str, int] = defaultdict(int)
    for record in records:
        for phase, seconds in record["timings"].items():
            if phase == "total":
                continue
            if is_censored(phase, seconds, record):
                censored[phase] += 1
            else:
                uncensored[phase].append(seconds)

    print()
    print("PER-PHASE COST (uncensored observations only)")
    print(f"{'phase':18s}{'n':>4s}{'p50':>8s}{'p90':>8s}{'max':>8s}"
          f"{'censored':>10s}")
    order = sorted(uncensored, key=lambda p: -(percentile(uncensored[p], 0.9) or 0))
    p50_sum = p90_sum = 0.0
    for phase in order:
        values = uncensored[phase]
        p50 = percentile(values, 0.5) or 0.0
        p90 = percentile(values, 0.9) or 0.0
        p50_sum += p50
        p90_sum += p90
        print(f"{phase:18s}{len(values):4d}{p50:8.0f}{p90:8.0f}"
              f"{max(values):8.0f}{censored[phase]:10d}")

    print()
    print("COMPLETED-CYCLE TOTALS (what a full pipeline actually costs)")
    totals = [r["timings"].get("total", 0.0) for r in completed]
    for label, q in (("p50", 0.5), ("p90", 0.9), ("p95", 0.95)):
        print(f"  {label}: {percentile(totals, q):.0f}s")
    print(f"  max: {max(totals):.0f}s   n={len(totals)}")

    print()
    print("BUDGET IMPLICATION")
    print(f"  sum of per-phase p50: {p50_sum:.0f}s")
    print(f"  sum of per-phase p90: {p90_sum:.0f}s  (a cycle rarely hits p90 "
          "in every phase at once)")
    observed_p90 = percentile(totals, 0.9) or 0.0
    print(f"  observed p90 of completed cycles: {observed_p90:.0f}s")
    print(f"  current usable budget: 1440s (1500 default - 60s return buffer)")
    headroom = 1440 - observed_p90
    print(f"  headroom over observed p90: {headroom:+.0f}s")

    print()
    print("INCOMPLETE CYCLES: where they stopped")
    stops: dict[str, int] = defaultdict(int)
    for record in failed:
        phases = {k: v for k, v in record["timings"].items() if k != "total"}
        if not phases:
            continue
        stops[max(phases, key=lambda k: phases[k])] += 1
    for phase, count in sorted(stops.items(), key=lambda kv: -kv[1]):
        print(f"  {phase:18s}{count:4d}  (largest phase when the cycle died)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
