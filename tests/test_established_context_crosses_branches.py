"""A branch must be able to consume what its ancestor established.

A cycle used to receive only the campaign objective, its branch direction and
its own first claim. So a branch built by widening on an earlier result could
not see that result: the seeded PSD branch of cmp_6804eb1d1eb8422e said "given
the S-procedure data at p" but nothing carried the entries, and its cycle had to
re-derive the assembly it was meant to consume - the operation that failed
campaign 05 five times. gather_established_context closes that transport gap by
surfacing the exact published output of every SUPPORTED episode in a branch's
ancestry, read straight from the stored artifact.
"""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.campaign_executor import (
    ESTABLISHED_ARTIFACT_CHAR_CAP,
    gather_established_context,
)
from core.campaign_models import ClaimStatus


class _Claim:
    def __init__(self, claim_id, statement):
        self.claim_id = claim_id
        self.statement = statement


class _Branch:
    def __init__(self, branch_id, parent_branch_id=None, parent_episode_id=None):
        self.branch_id = branch_id
        self.parent_branch_id = parent_branch_id
        self.parent_episode_id = parent_episode_id


class _Episode:
    def __init__(self, episode_id, branch_id, claim_status, claim_refs=()):
        self.episode_id = episode_id
        self.branch_id = branch_id
        self.claim_status = claim_status
        self.claim_refs = tuple(claim_refs)


class _State:
    def __init__(self, branches, episodes, claims):
        self.branches = {b.branch_id: b for b in branches}
        self.episodes = {e.episode_id: e for e in episodes}
        self.claims = {c.claim_id: c for c in claims}


def _write_stdout(campaign_dir: Path, episode_id: str, text: str) -> None:
    art = campaign_dir / "artifacts" / episode_id
    art.mkdir(parents=True, exist_ok=True)
    (art / "stdout.txt").write_text(text, encoding="utf-8")


class GatherEstablishedContextTests(unittest.TestCase):
    def test_ancestor_supported_output_is_surfaced_verbatim(self):
        with TemporaryDirectory() as tmp:
            campaign_dir = Path(tmp)
            _write_stdout(
                campaign_dir,
                "epi_assembly",
                "A = diag(-3500588/13286025, -823876/1476225, ...)\nVERDICT: PASS",
            )
            claim = _Claim("clm_assembly", "The S-procedure data are exactly computable.")
            parent = _Branch("brn_assembly")
            child = _Branch(
                "brn_psd",
                parent_branch_id="brn_assembly",
                parent_episode_id="epi_assembly",
            )
            episode = _Episode(
                "epi_assembly", "brn_assembly", ClaimStatus.SUPPORTED,
                claim_refs=("clm_assembly",),
            )
            state = _State([parent, child], [episode], [claim])

            context = gather_established_context(state, child, campaign_dir)

            self.assertIn("ESTABLISHED EARLIER IN THIS CAMPAIGN", context)
            self.assertIn("A = diag(-3500588/13286025", context)
            self.assertIn("do NOT rebuild them", context)
            self.assertIn("The S-procedure data are exactly computable.", context)

    def test_no_ancestry_yields_empty_context(self):
        with TemporaryDirectory() as tmp:
            lonely = _Branch("brn_only")
            state = _State([lonely], [], [])
            self.assertEqual(
                gather_established_context(state, lonely, Path(tmp)), ""
            )

    def test_a_missing_artifact_dir_never_raises(self):
        parent = _Branch("brn_p")
        child = _Branch("brn_c", parent_branch_id="brn_p", parent_episode_id="epi_p")
        episode = _Episode("epi_p", "brn_p", ClaimStatus.SUPPORTED)
        state = _State([parent, child], [episode], [])
        # A campaign_dir that does not exist on disk must degrade to "".
        self.assertEqual(
            gather_established_context(state, child, Path("nonexistent_dir_xyz")),
            "",
        )

    def test_none_campaign_dir_keeps_the_request_pure(self):
        parent = _Branch("brn_p")
        child = _Branch("brn_c", parent_branch_id="brn_p", parent_episode_id="epi_p")
        episode = _Episode("epi_p", "brn_p", ClaimStatus.SUPPORTED)
        state = _State([parent, child], [episode], [])
        self.assertEqual(gather_established_context(state, child, None), "")

    def test_an_unsupported_ancestor_episode_is_not_surfaced(self):
        with TemporaryDirectory() as tmp:
            campaign_dir = Path(tmp)
            _write_stdout(campaign_dir, "epi_refused", "VERDICT: FAIL")
            parent = _Branch("brn_p")
            child = _Branch("brn_c", parent_branch_id="brn_p")
            episode = _Episode("epi_refused", "brn_p", ClaimStatus.NOT_TESTED)
            state = _State([parent, child], [episode], [])
            self.assertEqual(
                gather_established_context(state, child, campaign_dir), ""
            )

    def test_a_long_artifact_is_truncated_with_a_marker(self):
        with TemporaryDirectory() as tmp:
            campaign_dir = Path(tmp)
            big = "x" * (ESTABLISHED_ARTIFACT_CHAR_CAP + 500)
            _write_stdout(campaign_dir, "epi_big", big)
            parent = _Branch("brn_p")
            child = _Branch("brn_c", parent_branch_id="brn_p", parent_episode_id="epi_big")
            episode = _Episode("epi_big", "brn_p", ClaimStatus.SUPPORTED)
            state = _State([parent, child], [episode], [])
            context = gather_established_context(state, child, campaign_dir)
            self.assertIn("established output truncated", context)

    def test_a_parent_cycle_does_not_hang(self):
        # Defensive: a malformed ledger with a self-referential ancestry must
        # terminate rather than loop.
        a = _Branch("brn_a", parent_branch_id="brn_b")
        b = _Branch("brn_b", parent_branch_id="brn_a")
        state = _State([a, b], [], [])
        with TemporaryDirectory() as tmp:
            self.assertEqual(gather_established_context(state, a, Path(tmp)), "")


if __name__ == "__main__":
    unittest.main()
