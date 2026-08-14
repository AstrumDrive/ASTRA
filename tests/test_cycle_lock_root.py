"""The deliberative-cycle slot must exclude across checkouts, not within one.

The slot enforces one deliberation per model-account set.  It used to live
under ``<checkout>/workspace/locks``, so the 2.0 line and production held
different locks while sharing one subscription and could run two
deliberations against the same account: the quota contention then surfaces as
operational errors that contaminate any measurement
(`docs/architecture/ASTRA2_SEPARATION_AND_PREPROD.md`).
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.runtime_resources import acquire_cycle_slot, cycle_lock_root


class LockRootTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_explicit_override_wins(self):
        target = self.tmp / "shared"
        with patch.dict(os.environ, {"ASTRA_LOCK_ROOT": str(target)}):
            self.assertEqual(
                cycle_lock_root(Path("C:/any/checkout")), target
            )

    def test_default_is_machine_wide_not_checkout_relative(self):
        env = {k: v for k, v in os.environ.items() if k != "ASTRA_LOCK_ROOT"}
        with patch.dict(os.environ, env, clear=True):
            root_a = cycle_lock_root(Path("C:/Users/x/Dev/ASTRA"))
            root_b = cycle_lock_root(Path("C:/Users/x/Dev/ASTRA-2.0"))
        self.assertEqual(root_a, root_b)
        self.assertNotIn("ASTRA-2.0", str(root_a))
        self.assertIn("astra", str(root_a).lower())

    def test_two_checkouts_share_one_slot(self):
        """The regression this exists for: production and 2.0 must contend."""
        production = self.tmp / "ASTRA"
        development = self.tmp / "ASTRA-2.0"
        for path in (production, development):
            (path / "workspace").mkdir(parents=True)
        shared = self.tmp / "machine-wide"
        with patch.dict(os.environ, {"ASTRA_LOCK_ROOT": str(shared)}):
            slot, active = acquire_cycle_slot(production, max_slots=1)
            self.addCleanup(slot.release)
            self.assertIsNotNone(slot)
            self.assertEqual(active, [])
            # A second checkout, same account: it must be refused.
            denied, holders = acquire_cycle_slot(development, max_slots=1)
        self.assertIsNone(denied)
        self.assertTrue(holders)
        self.assertEqual(holders[0]["pid"], os.getpid())

    def test_releasing_frees_the_slot_for_the_other_checkout(self):
        production = self.tmp / "ASTRA"
        development = self.tmp / "ASTRA-2.0"
        for path in (production, development):
            (path / "workspace").mkdir(parents=True)
        shared = self.tmp / "machine-wide"
        with patch.dict(os.environ, {"ASTRA_LOCK_ROOT": str(shared)}):
            first, _ = acquire_cycle_slot(production, max_slots=1)
            first.release()
            second, active = acquire_cycle_slot(development, max_slots=1)
            self.addCleanup(second.release)
        self.assertIsNotNone(second)
        self.assertEqual(active, [])

    def test_unwritable_root_falls_back_instead_of_disabling_the_slot(self):
        checkout = self.tmp / "checkout"
        (checkout / "workspace").mkdir(parents=True)
        blocker = self.tmp / "not-a-dir"
        blocker.write_text("", encoding="utf-8")
        with patch.dict(os.environ, {"ASTRA_LOCK_ROOT": str(blocker)}):
            slot, active = acquire_cycle_slot(checkout, max_slots=1)
        self.assertIsNotNone(slot)
        self.addCleanup(slot.release)
        self.assertEqual(active, [])
        # It fell back to the historical per-checkout location.
        self.assertIn("workspace", str(slot.path))

    def test_separate_accounts_can_be_isolated_on_purpose(self):
        checkout = self.tmp / "checkout"
        (checkout / "workspace").mkdir(parents=True)
        with patch.dict(os.environ, {"ASTRA_LOCK_ROOT": str(self.tmp / "acct-a")}):
            first, _ = acquire_cycle_slot(checkout, max_slots=1)
            self.addCleanup(first.release)
        with patch.dict(os.environ, {"ASTRA_LOCK_ROOT": str(self.tmp / "acct-b")}):
            second, active = acquire_cycle_slot(checkout, max_slots=1)
            self.addCleanup(second.release)
        self.assertIsNotNone(second)
        self.assertEqual(active, [])


if __name__ == "__main__":
    unittest.main()
