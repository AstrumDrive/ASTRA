"""H3 adapter: trajectory metrics computed from the campaign ledger."""
import tempfile
import unittest
from pathlib import Path

from core.campaign_executor import record_episode_result
from core.campaign_policy import CampaignState
from core.campaign_trajectory_metrics import campaign_trajectory_metrics

from test_campaign_executor import (
    SEED_BRANCH_ID,
    fixed_now,
    make_cycle_result,
    make_id_factory,
    seed_store,
)


def plain_result(**overrides):
    result = make_cycle_result(**overrides)
    result["deliberation"]["portfolio"] = None
    return result


class TrajectoryMetricsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_empty_state_reports_nulls_not_crashes(self):
        metrics = campaign_trajectory_metrics(CampaignState())
        self.assertEqual(metrics["episodes_completed"], 0)
        self.assertIsNone(metrics["autonomous_loop_yield"])
        self.assertIsNone(metrics["recovery_rate"])
        self.assertIsNone(metrics["campaign_status"])

    def test_mixed_trajectory_is_measured_deterministically(self):
        store = seed_store(self.root, self.addCleanup)
        ids = make_id_factory()
        # Episode 1: credible support (review APPROVED -> SCOPED).
        record_episode_result(
            store, SEED_BRANCH_ID, plain_result(),
            id_factory=ids, now_iso=fixed_now,
        )
        # Episode 2: operational failure (CODE_ERROR -> NOT_TESTED).
        record_episode_result(
            store, SEED_BRANCH_ID,
            plain_result(status="CODE_ERROR", scientific_status=""),
            id_factory=ids, now_iso=fixed_now,
        )
        # Episode 3: decisive refutation right after the failure (recovery).
        record_episode_result(
            store, SEED_BRANCH_ID,
            plain_result(status="REFUTED", scientific_status="ATOMIC_REFUTED"),
            id_factory=ids, now_iso=fixed_now,
        )
        metrics = campaign_trajectory_metrics(store.replay().state)
        self.assertEqual(metrics["episodes_completed"], 3)
        self.assertEqual(metrics["credible_evidence_episodes"], 2)
        self.assertAlmostEqual(metrics["autonomous_loop_yield"], 2 / 3)
        self.assertEqual(metrics["operational_failures"], 1)
        self.assertAlmostEqual(metrics["operational_failure_rate"], 1 / 3)
        self.assertEqual(metrics["distinct_claim_fingerprints"], 1)
        self.assertEqual(metrics["recovery_opportunities"], 1)
        self.assertEqual(metrics["recoveries"], 1)
        self.assertAlmostEqual(metrics["recovery_rate"], 1.0)
        self.assertEqual(metrics["scientific_refutations"], 1)
        self.assertEqual(metrics["branches_recorded"], 1)
        self.assertEqual(metrics["branch_preservation"], 0)
        self.assertEqual(metrics["model_calls"], 24)
        self.assertAlmostEqual(
            metrics["evidence_per_model_call"], 2 / 24
        )
        self.assertEqual(metrics["campaign_status"], "ACTIVE")
        self.assertIn("analogue", metrics["instrument"])

    def test_preserved_alternatives_count_as_branch_preservation(self):
        store = seed_store(self.root, self.addCleanup)
        # A portfolio with one alternative promotes a second branch.
        record_episode_result(
            store, SEED_BRANCH_ID, make_cycle_result(),
            id_factory=make_id_factory(), now_iso=fixed_now,
        )
        metrics = campaign_trajectory_metrics(store.replay().state)
        self.assertEqual(metrics["branches_recorded"], 2)
        self.assertEqual(metrics["branch_preservation"], 1)
        self.assertEqual(metrics["branch_statuses"].get("ADMISSIBLE"), 1)
        # Two distinct fingerprints: the seed claim and the synthesis claim
        # from the portfolio (attached to the executing branch).
        self.assertGreaterEqual(metrics["distinct_claim_fingerprints"], 1)


if __name__ == "__main__":
    unittest.main()
