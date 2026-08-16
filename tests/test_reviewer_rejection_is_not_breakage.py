"""A gate that declines is not a tool that broke.

Found on the first real campaign episode, 2026-08-16. The independent reviewer
refused a validator with three correct objections - two "independent" legs
solving the same semialgebraic condition, a universal R-scaling claim resting on
two radii, and exact failures mislabelled as operational exceptions. The campaign
recorded that as `operation_status: FAILED`, and two such episodes then promoted
a second branch by progressive widening: a scientific decision taken on an
operational signal, which is the exact collapse the five axes exist to prevent.
"""
import unittest

from core.campaign_decision import uninformative_streak
from core.campaign_executor import map_cycle_outcome, reviewer_withheld_approval
from core.campaign_models import (
    ClaimStatus,
    EvidenceOutcome,
    OperationStatus,
)

# The real reviewer verdict, abridged.
DECLINED = {
    "status": "TOOL_ERROR",
    "phase": "reviewer",
    "error": (
        "Independent reviewer did not approve the validation strategy after 1 "
        "model revision(s): claim 2 quantifies all R>0 while the script "
        "establishes scaling only at R=1 and R=2."
    ),
    "code_review": {"status": "REVISE", "source": "model_reviewer"},
}
REVIEWER_DIED = {
    "status": "TOOL_ERROR",
    "phase": "reviewer",
    "error": "API_ERROR: 'gpt-5.6-sol': timeout tras 240s (arbol de procesos matado)",
    "code_review": {"status": "REVISE", "source": "model_reviewer"},
}
TRANSLATOR_DIED = {
    "status": "TOOL_ERROR",
    "phase": "translator_repair",
    "error": "API_ERROR: 'claude-opus-4-8': timeout tras 480s",
}
VALIDATED = {"status": "VALIDATED", "code_review": {"status": "APPROVED"}}


class ClassificationTests(unittest.TestCase):
    def test_a_declining_reviewer_is_recognised(self):
        self.assertTrue(reviewer_withheld_approval(DECLINED))

    def test_a_dead_reviewer_is_not(self):
        """The distinction is the whole point: same phase, opposite meaning."""
        self.assertFalse(reviewer_withheld_approval(REVIEWER_DIED))

    def test_a_failure_in_another_phase_is_not(self):
        self.assertFalse(reviewer_withheld_approval(TRANSLATOR_DIED))


class MappingTests(unittest.TestCase):
    def test_a_declined_validator_completed_the_pipeline(self):
        axes = map_cycle_outcome(DECLINED)
        self.assertIs(axes.operation_status, OperationStatus.COMPLETED)
        self.assertIs(axes.claim_status, ClaimStatus.NOT_TESTED)
        self.assertIs(axes.evidence_outcome, EvidenceOutcome.INCONCLUSIVE)

    def test_a_dead_reviewer_is_still_an_operational_failure(self):
        axes = map_cycle_outcome(REVIEWER_DIED)
        self.assertIs(axes.operation_status, OperationStatus.FAILED)

    def test_a_refusal_never_becomes_a_refutation(self):
        """Declining to certify a validator says nothing about the physics."""
        axes = map_cycle_outcome(DECLINED)
        self.assertIsNot(axes.claim_status, ClaimStatus.REFUTED)
        self.assertIsNot(axes.evidence_outcome, EvidenceOutcome.SCIENTIFIC_REFUTATION)


class _Episode:
    def __init__(self, branch_id, operation_status, claim_status, timings=None):
        self.branch_id = branch_id
        self.operation_status = operation_status
        self.claim_status = claim_status
        self.timings = timings or {}


class _State:
    def __init__(self, episodes):
        self.episodes = {str(i): ep for i, ep in enumerate(episodes)}


def streak(*episodes):
    return uninformative_streak(_State(episodes), "brn_x")


class WideningTests(unittest.TestCase):
    def test_an_episode_that_never_ran_does_not_widen_a_campaign(self):
        never_ran = _Episode("brn_x", OperationStatus.FAILED, ClaimStatus.NOT_TESTED)
        self.assertEqual(streak(never_ran, never_ran), 0)

    def test_a_validator_that_ran_and_crashed_still_counts(self):
        """It informs the campaign: this direction is hard to test."""
        crashed = _Episode(
            "brn_x", OperationStatus.FAILED, ClaimStatus.NOT_TESTED,
            timings={"conjecture": 200.0, "translate": 400.0, "execute": 3.0},
        )
        self.assertEqual(streak(crashed, crashed), 2)

    def test_a_declined_validator_does_count(self):
        """Two cycles the reviewer would not certify IS a signal about the branch."""
        declined = _Episode("brn_x", OperationStatus.COMPLETED, ClaimStatus.NOT_TESTED)
        self.assertEqual(streak(declined, declined), 2)

    def test_breakage_neither_extends_nor_resets_the_run(self):
        declined = _Episode("brn_x", OperationStatus.COMPLETED, ClaimStatus.NOT_TESTED)
        never_ran = _Episode("brn_x", OperationStatus.FAILED, ClaimStatus.NOT_TESTED)
        self.assertEqual(streak(declined, never_ran, declined), 2)

    def test_real_evidence_still_resets_the_run(self):
        declined = _Episode("brn_x", OperationStatus.COMPLETED, ClaimStatus.NOT_TESTED)
        supported = _Episode("brn_x", OperationStatus.COMPLETED, ClaimStatus.SUPPORTED)
        self.assertEqual(streak(declined, supported, declined), 1)

    def test_the_live_case_would_no_longer_promote(self):
        """Replay 2026-08-16: a lock casualty plus a reviewer refusal."""
        lock_casualty = _Episode(
            "brn_x", OperationStatus.FAILED, ClaimStatus.NOT_TESTED
        )
        refusal = _Episode("brn_x", OperationStatus.COMPLETED, ClaimStatus.NOT_TESTED)
        self.assertEqual(streak(lock_casualty, refusal), 1)


if __name__ == "__main__":
    unittest.main()
