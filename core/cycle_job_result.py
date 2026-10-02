"""The final result of a persistent deliberative cycle, as its job records it.

A persistent cycle runs as astra_tool.py under astra_cycle_job_runner.py.
astra_tool prints exactly one line to stdout.log, its result as a JSON
object, as the last thing it does; the runner copies that line to
result.json and summarises it in job.json.  When the runner dies before
that (on 2026-10-02 five runners were terminated together while their
cycles went on to finish), astra_job recovers the same summary from
stdout.log.  Both sides use this module, so the recovered job.json fields
are the ones the runner would have written.
"""

from __future__ import annotations

import json
import os
from typing import Any

NO_RESULT_ERROR = "persistent cycle produced no JSON result"


def last_json_object(path) -> dict | None:
    """The last line of ``path`` that parses as a JSON object, or None.

    A line still being written never parses (an object's closing brace
    comes last), so a reader racing the final print sees no result yet
    rather than a partial one.
    """
    last = None
    try:
        with open(os.fspath(path), "r", encoding="utf-8", errors="replace") as stream:
            for line in stream:
                try:
                    candidate = json.loads(line.strip())
                except (json.JSONDecodeError, TypeError):
                    continue
                if isinstance(candidate, dict):
                    last = candidate
    except OSError:
        return None
    return last


def final_fields(result: dict[str, Any]) -> dict[str, Any]:
    """The job.json fields that summarise a cycle's result."""
    return {
        "scientific_status": result.get("scientific_status") or result.get("status"),
        "atomic_status": result.get("atomic_status") or result.get("status"),
        "goal_coverage": (result.get("goal_coverage") or {}).get("status"),
        "oracle_verdict": result.get("oracle_verdict"),
        "operational_error": bool(result.get("error")),
    }
