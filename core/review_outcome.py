"""Telling a gate that declined apart from a tool that broke.

They look alike in a cycle result and mean opposite things, and conflating
them collapses a scientific signal into an operational one. This module
holds the single definition, because the cost of having it in only one
layer has now been paid three times:

* 2026-08-16, first real campaign episode: a reviewer refused a validator
  whose two "independent" legs solved the same semialgebraic condition.
  That is rigour, and it was being recorded as a broken tool. Fixed then in
  ``core/campaign_executor.py``, with
  ``tests/test_reviewer_rejection_is_not_breakage.py`` written to defend
  the principle.
* 2026-08-24, the audit track of ``core/quality_metrics.py``:
  ``sound_validator_false_alarm_rate`` counted a dead reviewer call as a
  genuine false alarm, because its numerator was a blacklist rather than a
  whitelist.
* 2026-08-28, ``core/research_trajectory_metrics.py``: the trajectory
  benchmark's ``operational_failure_rate`` -- the exact number G4's
  remaining bullets are blocked on -- counted reviewer declines as
  breakage. Measured over the two runs that matter: RUN3's H3 pilot
  reported 0.833 where only 0.556 was genuine, and the post-A2 run
  reported 0.889 where only 0.222 was.

The correct logic already existed each time; what was missing was a shared
place to import it from. That is what this module is.
"""
from __future__ import annotations

from typing import Any, Mapping


def reviewer_withheld_approval(result: Mapping[str, Any]) -> bool:
    """True when review ran and declined, as opposed to review breaking.

    A reviewer that returns REVISE or REJECT has done its job: the pipeline
    completed and the gate refused to certify a validator. A reviewer that
    times out or hits a quota error is an operational failure and must stay
    one.
    """
    phase = str(result.get("phase") or "").lower()
    if not phase.startswith("review"):
        return False
    error = str(result.get("error") or "")
    if error.startswith("API_ERROR:") or "timeout tras" in error:
        return False
    # A starved phase is an operational failure, not a judgement. The budget
    # guard (astra_tool.py `_starved_error`) refuses a call it cannot afford
    # and returns before any reviewing happens, but `code_review` still holds
    # REVISE from the previous round -- so status alone reads like a decline.
    # Found 2026-08-28 by the trajectory test replaying real cycles: 4 of the
    # 6 post-A2 cycles first taken for declines were budget exhaustions, which
    # inflated the correction as badly as the original defect inflated the
    # rate. The remedy for the two is opposite (more budget vs reviewer
    # calibration), so conflating them defeats the point of separating them.
    if "Cycle budget exhausted" in error:
        return False
    review = result.get("code_review") or {}
    return str(review.get("status") or "").upper() in {"REVISE", "REJECT"}
