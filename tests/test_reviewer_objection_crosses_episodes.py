"""A reviewer refusal must reach the next author on the same branch.

The symmetric partner of the established-context fix. Across four episodes of
cmp_6804eb1d1eb8422e the reviewer refused four different shortcuts - re-derive
the data, gate on an exact value, use QQ for a rational sign, reduce to a
representative tensor - and each objection lived only in the cycle checkpoint,
invisible to the next fresh author, who invented the next shortcut. Persisting
the objection into the evidence record and surfacing it in the next request
lets a retry converge instead of cycling.
"""
import unittest

from core.campaign_executor import (
    _extract_reviewer_objection,
    gather_prior_reviewer_objection,
)
from core.campaign_models import ClaimStatus


class ExtractObjectionTests(unittest.TestCase):
    def test_a_revise_reasoning_is_extracted(self):
        result = {
            "code_review": {
                "status": "REVISE",
                "reasoning": "two decisive signs are decided in QQ, not QQbar",
                "revision_instructions": "wrap them as QQbar(...)",
            }
        }
        out = _extract_reviewer_objection(result)
        self.assertIn("QQ, not QQbar", out)
        self.assertIn("wrap them as QQbar", out)

    def test_an_approved_review_yields_nothing(self):
        result = {"code_review": {"status": "APPROVED", "reasoning": "sound"}}
        self.assertEqual(_extract_reviewer_objection(result), "")

    def test_a_missing_review_yields_nothing(self):
        self.assertEqual(_extract_reviewer_objection({}), "")

    def test_a_reject_is_extracted_too(self):
        result = {"code_review": {"status": "REJECT", "reasoning": "not code at all"}}
        self.assertEqual(_extract_reviewer_objection(result), "not code at all")


class _Claim:
    def __init__(self, claim_id):
        self.claim_id = claim_id
        self.statement = "claim"
        self.unresolved_obligations = ()


class _Branch:
    def __init__(self, branch_id):
        self.branch_id = branch_id
        self.direction = "do the thing"
        self.claim_refs = ()
        self.parent_branch_id = None
        self.parent_episode_id = None


class _Episode:
    def __init__(self, episode_id, branch_id, claim_status, evidence_refs=()):
        self.episode_id = episode_id
        self.branch_id = branch_id
        self.claim_status = claim_status
        self.evidence_refs = tuple(evidence_refs)


class _Evidence:
    def __init__(self, evidence_id, metadata):
        self.evidence_id = evidence_id
        self.metadata = metadata


class _State:
    def __init__(self, branches=(), episodes=(), evidence=()):
        self.branches = {b.branch_id: b for b in branches}
        self.episodes = {e.episode_id: e for e in episodes}
        self.evidence = {e.evidence_id: e for e in evidence}


class GatherPriorObjectionTests(unittest.TestCase):
    def test_the_latest_refusal_on_this_branch_is_surfaced(self):
        branch = _Branch("brn_x")
        ev = _Evidence("evd_1", {"reviewer_objection": "load the literal A, b, c"})
        ep = _Episode("epi_1", "brn_x", ClaimStatus.NOT_TESTED, evidence_refs=("evd_1",))
        state = _State(branches=[branch], episodes=[ep], evidence=[ev])
        self.assertEqual(
            gather_prior_reviewer_objection(state, branch), "load the literal A, b, c"
        )

    def test_a_supported_last_episode_surfaces_nothing(self):
        # If the last thing on the branch passed, a stale earlier objection must
        # not resurface.
        branch = _Branch("brn_x")
        ev = _Evidence("evd_1", {"reviewer_objection": "old objection"})
        old = _Episode("epi_1", "brn_x", ClaimStatus.NOT_TESTED, evidence_refs=("evd_1",))
        new = _Episode("epi_2", "brn_x", ClaimStatus.SUPPORTED)
        state = _State(branches=[branch], episodes=[old, new], evidence=[ev])
        self.assertEqual(gather_prior_reviewer_objection(state, branch), "")

    def test_an_objection_on_another_branch_is_not_surfaced(self):
        branch = _Branch("brn_x")
        other = _Branch("brn_y")
        ev = _Evidence("evd_1", {"reviewer_objection": "y-branch objection"})
        ep = _Episode("epi_1", "brn_y", ClaimStatus.NOT_TESTED, evidence_refs=("evd_1",))
        state = _State(branches=[branch, other], episodes=[ep], evidence=[ev])
        self.assertEqual(gather_prior_reviewer_objection(state, branch), "")

    def test_no_episodes_yields_nothing(self):
        branch = _Branch("brn_x")
        self.assertEqual(gather_prior_reviewer_objection(_State(branches=[branch]), branch), "")

    def test_a_refusal_without_stored_objection_yields_nothing(self):
        branch = _Branch("brn_x")
        ev = _Evidence("evd_1", {})
        ep = _Episode("epi_1", "brn_x", ClaimStatus.NOT_TESTED, evidence_refs=("evd_1",))
        state = _State(branches=[branch], episodes=[ep], evidence=[ev])
        self.assertEqual(gather_prior_reviewer_objection(state, branch), "")


if __name__ == "__main__":
    unittest.main()
