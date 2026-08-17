"""A replayed cycle is not an observation.

Observed live 2026-08-16 in campaign cmp_5e3c37c77e7b4841: two consecutive
episodes on the same branch recorded byte-identical timings (total 2023.55 s)
and two separate Evidence records, because the second step re-sent the same
direction, hit the cycle cache and returned in seconds. The ledger then showed
a claim supported by two episodes where only one experiment had happened.

The cache itself is correct and useful - a research loop revisiting a similar
direction should not re-burn the whole pipeline. What is wrong is minting
evidence from the replay.
"""
import asyncio
import tempfile
import unittest
from pathlib import Path

from core.campaign_executor import CampaignExecutorError, run_episode


class _Store:
    """Minimal stand-in: run_episode fails before touching the store."""

    def replay(self):
        raise AssertionError("should not be reached in these tests")


class CachedReplayTests(unittest.IsolatedAsyncioTestCase):
    async def test_a_cached_result_is_refused_before_it_becomes_evidence(self):
        from unittest.mock import patch

        cached = {"status": "VALIDATED", "cached": True, "timings": {"total": 2023.55}}

        with patch("core.campaign_executor.record_episode_result") as recorder, \
                patch("core.campaign_executor.build_episode_request", return_value={}), \
                patch("core.campaign_executor._preflight_for_test", create=True):
            with self.assertRaises(CampaignExecutorError) as caught:
                await _run_with(cached)
            recorder.assert_not_called()
        message = str(caught.exception)
        self.assertIn("cached replay", message)
        # The message must tell the operator how to proceed, not just refuse.
        self.assertIn("ASTRA_CYCLE_CACHE=0", message)

    async def test_a_fresh_result_is_recorded_normally(self):
        from unittest.mock import patch

        fresh = {"status": "VALIDATED", "timings": {"total": 2023.55}}
        with patch("core.campaign_executor.record_episode_result",
                   return_value="recorded") as recorder, \
                patch("core.campaign_executor.build_episode_request", return_value={}):
            out = await _run_with(fresh)
        self.assertEqual(out, "recorded")
        recorder.assert_called_once()

    async def test_the_marker_is_the_one_the_cycle_actually_sets(self):
        """astra_tool sets exactly this key on a cache hit."""
        source = (Path(__file__).resolve().parents[1] / "astra_tool.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('cached["cached"] = True', source)


async def _run_with(result):
    """Drive run_episode past its pre-gates with a stubbed state."""
    from unittest.mock import MagicMock, patch

    from core.campaign_models import BranchStatus, CampaignStatus

    branch = MagicMock()
    branch.status = BranchStatus.ACTIVE
    branch.evidence_plan.estimated_cost = MagicMock()
    state = MagicMock()
    state.require_campaign.return_value.status = CampaignStatus.ACTIVE
    state.branches = {"brn_x": branch}
    state.remaining_budget.return_value.covers.return_value = True
    store = MagicMock()
    store.replay.return_value.state = state

    async def runner(_request):
        return result

    with tempfile.TemporaryDirectory():
        return await run_episode(store, "brn_x", cycle_runner=runner)


if __name__ == "__main__":
    unittest.main()
