"""The trajectory benchmark must not count a reviewer decline as breakage.

Found 2026-08-28 while verifying protocol amendment A2: of the 8 cycles the
post-A2 growth_model_discrimination run counted as operational failures, 6
were reviewer declines -- `code_review.status=REVISE`, "Independent reviewer
did not approve the validation strategy after 2 model revision(s)". The
reviewer ran and refused to certify; nothing broke.

This is the third appearance of the same defect class, and the reason
`core/review_outcome.py` now exists: the correct predicate had been written
in 2026-08-16 for the campaign layer and defended by
`tests/test_reviewer_rejection_is_not_breakage.py`, but each new layer
reimplemented the check as a bare status-membership test instead of reusing
it.

It mattered because `operational_failure_rate` is the exact number G4's
three remaining bullets are blocked on. Measured over the two runs that
carry that weight: RUN3's H3 pilot reported 0.833 where only 0.556 was
genuine, and the post-A2 run reported 0.889 where only 0.222 was. That is
the difference between "the infrastructure is too broken to compare
architectures" and "the reviewer declines a lot" -- opposite diagnoses with
opposite remedies.
"""
import unittest

from core.research_trajectory_metrics import compute_trajectory_metrics

DECLINE = {
    "status": "TOOL_ERROR",
    "phase": "reviewer",
    "error": (
        "Independent reviewer did not approve the validation strategy after 2 "
        "model revision(s): the two legs solve the same condition."
    ),
    "code_review": {"status": "REVISE", "source": "model_reviewer"},
}
REVIEWER_DIED = {
    "status": "TOOL_ERROR",
    "phase": "reviewer",
    "error": "API_ERROR: 'gpt-5.6-sol': timeout tras 240s (arbol de procesos matado)",
    "code_review": {"status": "REVISE", "source": "model_reviewer"},
}
BUDGET_EXHAUSTED = {
    "status": "TOOL_ERROR",
    "phase": "reviewer",
    "error": (
        "Cycle budget exhausted before validator repair regeneration: the "
        "phase would get 1s, below the 45s a call needs to be worth making"
    ),
    "code_review": {"status": "REVISE", "source": "model_reviewer"},
}
VALIDATED = {"status": "VALIDATED", "code_review": {"status": "APPROVED"}}


def metrics(*results):
    return compute_trajectory_metrics(
        {"cycles": [{"result": r} for r in results], "human_interventions": 1}
    )


class DeclineIsNotOperationalFailureTests(unittest.TestCase):
    def test_a_decline_does_not_count_as_operational_failure(self):
        m = metrics(DECLINE, VALIDATED)
        self.assertEqual(m["operational_failure_rate"], 0.0)

    def test_a_decline_is_still_reported_not_hidden(self):
        """Correcting the rate must not make the signal invisible: a reviewer
        that declines a lot is a real finding, just not an operational one."""
        m = metrics(DECLINE, VALIDATED)
        self.assertEqual(m["reviewer_decline_rate"], 0.5)

    def test_a_dead_reviewer_is_still_an_operational_failure(self):
        """Same phase, same code_review status, opposite meaning."""
        m = metrics(REVIEWER_DIED, VALIDATED)
        self.assertEqual(m["operational_failure_rate"], 0.5)
        self.assertEqual(m["reviewer_decline_rate"], 0.0)

    def test_a_budget_guard_refusal_is_still_an_operational_failure(self):
        """The guard refusing a doomed call is correct behavior, but the cycle
        still produced no verdict for an operational reason."""
        m = metrics(BUDGET_EXHAUSTED, VALIDATED)
        self.assertEqual(m["operational_failure_rate"], 0.5)
        self.assertEqual(m["reviewer_decline_rate"], 0.0)

    def test_the_old_definition_is_retained_for_comparability(self):
        """Runs measured before 2026-08-28 must stay interpretable."""
        m = metrics(DECLINE, REVIEWER_DIED, VALIDATED)
        self.assertEqual(m["operational_failure_rate"], round(1 / 3, 4))
        self.assertEqual(m["operational_failure_rate_with_declines"], round(2 / 3, 4))

    def test_a_clean_run_is_unaffected(self):
        m = metrics(VALIDATED, VALIDATED)
        self.assertEqual(m["operational_failure_rate"], 0.0)
        self.assertEqual(m["reviewer_decline_rate"], 0.0)


class MeasuredRunsReplayTests(unittest.TestCase):
    """Replay the two runs whose numbers G4 is blocked on."""

    def test_the_post_a2_run_shape(self):
        """The real composition, categorised by error text rather than by
        status: 2 genuine reviewer declines, 4 budget-guard refusals, 1
        provider failure, 1 lock contention, 1 refuted -- 9 cycles.

        The first reading of this run called all 6 non-provider failures
        declines, because the predicate did not yet exclude budget
        exhaustion. That put genuine operational failure at 0.222 when it is
        0.667, an error as large as the one being corrected.
        """
        m = metrics(
            DECLINE, DECLINE,
            BUDGET_EXHAUSTED, BUDGET_EXHAUSTED, BUDGET_EXHAUSTED, BUDGET_EXHAUSTED,
            REVIEWER_DIED,
            {"status": "BUSY", "phase": None,
             "error": "Another full ASTRA deliberative cycle is already using "
                      "the shared model-account set."},
            {"status": "REFUTED", "code_review": {"status": "APPROVED"}},
        )
        self.assertEqual(m["operational_failure_rate"], round(6 / 9, 4))
        self.assertEqual(m["operational_failure_rate_with_declines"], round(8 / 9, 4))
        self.assertEqual(m["reviewer_decline_rate"], round(2 / 9, 4))


if __name__ == "__main__":
    unittest.main()
