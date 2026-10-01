"""Runner labels and cycle budget introduced by the 2026-10-01 research-claims run."""
from __future__ import annotations

import unittest

from core.quality_benchmarks import QualityCase
from core.quality_metrics import OPERATIONAL_STATUSES
from scripts.run_quality_benchmarks import _error_status


class ErrorLabelTests(unittest.TestCase):
    def test_reviewer_rejection_is_named(self):
        err = {"error": "Independent reviewer did not approve the validation strategy after 2 model revision(s): ..."}
        self.assertEqual(_error_status(err), "REVIEW_REJECTED")

    def test_budget_exhaustion_is_named(self):
        err = {"error": "Cycle budget exhausted before independent review: the phase would get 1s ..."}
        self.assertEqual(_error_status(err), "BUDGET_EXHAUSTED")

    def test_model_failures_keep_api_error(self):
        self.assertEqual(_error_status({"error": "API_ERROR: 'gpt-6-luna': timeout tras 240s"}), "TIMEOUT")
        self.assertEqual(_error_status({"error": "API_ERROR: OAuth session expired", "phase": "conjecture"}), "API_ERROR")
        self.assertEqual(_error_status({"error": "something else"}), "TOOL_ERROR")

    def test_new_labels_count_as_operational_failures(self):
        self.assertIn("REVIEW_REJECTED", OPERATIONAL_STATUSES)
        self.assertIn("BUDGET_EXHAUSTED", OPERATIONAL_STATUSES)


class CycleBudgetTests(unittest.TestCase):
    def _case(self, timeout):
        return QualityCase(id="c", track="cycle", domain="d", difficulty="research", expected="VALIDATED",
                           objective="o", intuition="i", timeout=timeout)

    def test_default_case_keeps_the_default_budget(self):
        self.assertEqual(self._case(180).cycle_request("local")["cycle_timeout_seconds"], 1500)

    def test_heavy_case_gets_room_after_its_oracle_run(self):
        req = self._case(900).cycle_request("local")
        self.assertEqual(req["exec_timeout"], 900)
        self.assertEqual(req["cycle_timeout_seconds"], 1800)


if __name__ == "__main__":
    unittest.main()
