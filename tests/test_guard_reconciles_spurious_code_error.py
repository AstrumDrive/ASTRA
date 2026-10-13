"""The deterministic auditor overrules the analyst in BOTH directions.

_apply_guard already downgraded a VALIDATED whose script could not fail to
WEAK_PASS. The symmetric hole cost a finished result: on 2026-08-18, campaign
cmp_6804eb1d1eb8422e episode 4, the analyst returned status CODE_ERROR while its
own reasoning affirmed the proof and offered no corrected_code - it read a Sage
DeprecationWarning on stderr as a code error. The execution had printed
VERDICT: PASS and the deterministic auditor was clean. That spurious CODE_ERROR
triggered a repair patch, the patch response was malformed JSON, and the cycle
destroyed an approved, passing validator that had certified the NEC over the full
null cone at p (q_* = 40864160968/722297701575 > 0 in QQbar).
"""
import unittest

from astra_tool import _apply_guard


def _guard(suspect=False, reasons=None):
    return {"verdict_suspect": suspect, "reasons": reasons or []}


class ExistingDowngradeStillHolds(unittest.TestCase):
    def test_validated_over_a_suspect_guard_becomes_weak_pass(self):
        analysis = {"status": "VALIDATED", "reasoning": "looks fine"}
        exec_result = {"verdict": "PASS", "guard": _guard(suspect=True, reasons=["no reachable FAIL branch"])}
        out = _apply_guard(analysis, exec_result)
        self.assertEqual(out["status"], "WEAK_PASS")
        self.assertIn("AUDITOR determinista", out["reasoning"])

    def test_validated_over_a_clean_guard_is_left_alone(self):
        analysis = {"status": "VALIDATED", "reasoning": "ok"}
        out = _apply_guard(analysis, {"verdict": "PASS", "guard": _guard()})
        self.assertEqual(out["status"], "VALIDATED")


class SpuriousCodeErrorIsReconciled(unittest.TestCase):
    def test_the_episode_4_case_reconciles_to_validated(self):
        # The real values: 8/8 checks OK, clean guard, PASS, no fix offered.
        analysis = {
            "status": "CODE_ERROR",
            "corrected_code": None,
            "reasoning": (
                "proves that the NEC is strictly satisfied for every null "
                "direction at p; the stderr deprecation warning is irrelevant"
            ),
        }
        exec_result = {
            "verdict": "PASS",
            "guard": {"verdict_suspect": False, "reasons": [], "checks_ok": 8, "checks_fail": 0},
        }
        out = _apply_guard(analysis, exec_result)
        self.assertEqual(out["status"], "VALIDATED")
        self.assertEqual(out["reconciled_from"], "CODE_ERROR")
        self.assertIn("no es accionable", out["reasoning"])

    def test_a_code_error_with_a_real_fix_is_respected(self):
        # If the analyst can point to a correction, its CODE_ERROR stands - it
        # is not a mislabelled warning.
        analysis = {
            "status": "CODE_ERROR",
            "corrected_code": "# ASTRA_ENGINE: sage\nprint('VERDICT: PASS')",
            "reasoning": "off-by-one in the tetrad",
        }
        out = _apply_guard(analysis, {"verdict": "PASS", "guard": _guard()})
        self.assertEqual(out["status"], "CODE_ERROR")

    def test_a_code_error_over_a_suspect_guard_stands(self):
        # The deterministic auditor agrees something is wrong; do not promote.
        analysis = {"status": "CODE_ERROR", "corrected_code": None, "reasoning": "x"}
        exec_result = {"verdict": "PASS", "guard": _guard(suspect=True, reasons=["hardcoded PASS"])}
        out = _apply_guard(analysis, exec_result)
        self.assertEqual(out["status"], "CODE_ERROR")

    def test_a_code_error_without_a_pass_verdict_stands(self):
        # Execution did not pass; the CODE_ERROR is about a real failure.
        analysis = {"status": "CODE_ERROR", "corrected_code": None, "reasoning": "x"}
        out = _apply_guard(analysis, {"verdict": "FAIL", "guard": _guard()})
        self.assertEqual(out["status"], "CODE_ERROR")

    def test_a_missing_verdict_is_not_a_pass(self):
        analysis = {"status": "CODE_ERROR", "corrected_code": None, "reasoning": "x"}
        out = _apply_guard(analysis, {"guard": _guard()})
        self.assertEqual(out["status"], "CODE_ERROR")

    def test_the_input_dict_is_not_mutated(self):
        analysis = {"status": "CODE_ERROR", "corrected_code": None, "reasoning": "x"}
        _apply_guard(analysis, {"verdict": "PASS", "guard": _guard()})
        self.assertEqual(analysis["status"], "CODE_ERROR")


if __name__ == "__main__":
    unittest.main()
