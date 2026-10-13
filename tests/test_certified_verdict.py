"""The vetted verdict helper (core/certified/verdict_prelude.py): decisive legs
decide, corroborative legs never print FAIL.

Regression for 9 October 2026: three validators the reviewer otherwise
accepted (Kondo's integral asymptotic twice, a synthetic sector bound) were
sent back because one all(checks.values()) let a quadrature or sampling leg
print VERDICT: FAIL on an asymptotic claim.
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from core.certified import decision_from_stdout, expand_certified, prelude_info, prelude_source
from core.verdict_guard import assess_verdict


def fresh():
    namespace = {}
    exec(compile(prelude_source("verdict"), "verdict_prelude", "exec"), namespace)
    return namespace


def run(legs):
    """Record legs [(name, value, role)] in a fresh helper and decide.
    Returns (result or exit code, stdout)."""
    ns, out = fresh(), io.StringIO()
    with redirect_stdout(out):
        for name, value, role in legs:
            ns["leg"](name, value, "detail", role)
        try:
            result = ns["decide"]()
        except SystemExit as stop:
            result = stop.code
    return result, out.getvalue()


class Decide(unittest.TestCase):
    def test_all_hold_is_pass(self):
        result, out = run([("exact", True, "decisive"), ("quad", True, "corroborative")])
        self.assertEqual(result, "PASS")
        self.assertIn("CHECK exact: OK [decisive] -- detail", out)
        self.assertIn("DECISION: PASS", out)
        self.assertTrue(out.rstrip().endswith("VERDICT: PASS"))

    def test_only_a_decisive_false_refutes(self):
        result, out = run([("exact", False, "decisive"), ("quad", True, "corroborative")])
        self.assertEqual(result, "FAIL")
        self.assertIn("refuted by decisive leg(s): exact", out)
        self.assertTrue(out.rstrip().endswith("VERDICT: FAIL"))

    def test_a_corroborative_disagreement_is_never_fail(self):
        for value in (False, None):
            with self.subTest(value=value):
                result, out = run([("exact", True, "decisive"), ("quad", value, "corroborative")])
                self.assertEqual(result, 6)
                self.assertIn("DECISION: CORROBORATION_MISMATCH", out)
                self.assertNotIn("VERDICT:", out)

    def test_an_undecided_decisive_leg_gives_no_verdict(self):
        result, out = run([("exact", True, "decisive"), ("bound", None, "decisive"),
                           ("quad", False, "corroborative")])
        self.assertEqual(result, 5)
        self.assertIn("DECISION: UNDECIDED -- decisive leg(s) not decided: bound", out)
        self.assertNotIn("VERDICT:", out)

    def test_a_refutation_wins_over_an_undecided_leg(self):
        result, out = run([("exact", False, "decisive"), ("bound", None, "decisive")])
        self.assertEqual(result, "FAIL")
        self.assertIn("VERDICT: FAIL", out)

    def test_misuse_is_an_error_not_a_verdict(self):
        ns = fresh()
        with redirect_stdout(io.StringIO()):
            ns["leg"]("quad", True, role="corroborative")
            with self.assertRaises(RuntimeError):
                ns["decide"]()                          # no decisive leg
            with self.assertRaises(RuntimeError):
                ns["decide"]()                          # second call
            with self.assertRaises(RuntimeError):
                ns["leg"]("late", True)                 # after decide()
        ns = fresh()
        for value in (1, 0, "True", 0.0):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    ns["leg"]("x", value)
        with self.assertRaises(ValueError):
            ns["leg"]("x", True, role="crosscheck")

    def test_run_leg_turns_undecided_into_none_and_keeps_real_errors(self):
        ns, out = fresh(), io.StringIO()

        class Undecided(Exception):
            pass

        def undecided():
            raise Undecided("42 boxes at 64 bits")

        with redirect_stdout(out):
            self.assertIsNone(ns["run_leg"]("bound", undecided))
            self.assertTrue(ns["run_leg"]("exact", lambda: (True, "residual 0")))
            with self.assertRaises(ZeroDivisionError):
                ns["run_leg"]("broken", lambda: 1 / 0)
        self.assertIn("CHECK bound: UNDECIDED [decisive] -- undecided: 42 boxes at 64 bits", out.getvalue())
        self.assertIn("CHECK exact: OK [decisive] -- residual 0", out.getvalue())

    def test_decision_line_is_parsed(self):
        self.assertEqual(decision_from_stdout("CHECK a: OK\nDECISION: PASS -- 1 decisive\nVERDICT: PASS\n"), "PASS")
        self.assertEqual(decision_from_stdout("DECISION: CORROBORATION_MISMATCH -- x\n"), "CORROBORATION_MISMATCH")
        self.assertEqual(decision_from_stdout("VERDICT: PASS\n"), "")


LEGS_VALIDATOR = """# ASTRA_CERTIFIED: verdict
from fractions import Fraction
exact = Fraction(1, 3) + Fraction(1, 6) == Fraction(1, 2)
leg("exact_sum", exact, "1/3 + 1/6 = 1/2 in exact rationals")
leg("float_sum", abs(1/3 + 1/6 - 0.5) < 1e-12, "float cross-check", role="corroborative")
decide()
"""


class Wiring(unittest.TestCase):
    def test_verdict_kind_is_pure_python(self):
        expanded, info, error = expand_certified(LEGS_VALIDATOR, "python")
        self.assertIsNone(error)
        self.assertEqual(info, prelude_info("verdict"))
        self.assertEqual(info["version"], "verdict-1")
        self.assertNotIn("import flint", expanded)

    def test_local_run_end_to_end(self):
        from core.executor import execute_python_code

        with patch.dict(os.environ, {"ASTRA_ORACLE_MODE": "local"}):
            result = asyncio.run(execute_python_code(LEGS_VALIDATOR, timeout=120))
        self.assertEqual(result["exit_code"], 0, result["stderr"])
        self.assertIn("DECISION: PASS", result["stdout"])
        self.assertEqual(result["certified_prelude"]["kind"], "verdict")
        guard = assess_verdict(LEGS_VALIDATOR, result)
        self.assertFalse(guard["verdict_suspect"], guard["reasons"])


class Guard(unittest.TestCase):
    PASSED = {"stdout": "CHECK a: OK [decisive]\nDECISION: PASS -- 1 decisive\nVERDICT: PASS\n",
              "certified_prelude": {"kind": "verdict"}}

    def test_helper_pass_needs_no_fail_string_in_the_validator(self):
        code = "# ASTRA_CERTIFIED: verdict\nleg('a', is_certainly_lt(1, 2))\ndecide()\n"
        self.assertFalse(assess_verdict(code, self.PASSED)["verdict_suspect"])

    def test_a_literal_true_decisive_leg_is_suspect(self):
        for code in ("leg('a', True)\ndecide()\n",
                     "leg(name='a', value=True)\ndecide()\n",
                     "run_leg('a', lambda: True)\ndecide()\n"):
            with self.subTest(code=code):
                guard = assess_verdict(code, self.PASSED)
                self.assertTrue(guard["verdict_suspect"])
                self.assertIn("True literal", guard["reasons"][0])
        corroborative = "leg('a', ok)\nleg('b', True, '', 'corroborative')\ndecide()\n"
        self.assertFalse(assess_verdict(corroborative, self.PASSED)["verdict_suspect"])

    def test_without_the_helper_the_old_audit_still_applies(self):
        plain = {"stdout": "DECISION: PASS\nVERDICT: PASS\n"}      # forged, no prelude ran
        self.assertTrue(assess_verdict("print('DECISION: PASS')\nprint('VERDICT: PASS')\n",
                                       plain)["verdict_suspect"])


class AnalystGuard(unittest.IsolatedAsyncioTestCase):
    async def _analyze(self, reply_status, decision, exit_code):
        from core.llm_client import ASTRAIntelligence

        analyst = ASTRAIntelligence(provider="codex_cli")

        async def fake_call(_system, _user):
            return json.dumps({"status": reply_status, "reasoning": "prose",
                               "original_claim_verdict": "REFUTED" if reply_status == "REFUTED" else "SUPPORTED",
                               "original_claim_reasoning": "P decided."})

        analyst._call_api = fake_call
        return await analyst.analyze_results(
            "conjecture",
            {"exit_code": exit_code, "stderr": "",
             "stdout": f"CHECK exact: OK [decisive]\nCHECK quad: FAIL [corroborative]\nDECISION: {decision} -- x\n",
             "validation_code": "# ASTRA_CERTIFIED: verdict\n", "code_review": {"status": "APPROVED"}},
            shared_goal="Determine whether P.", original_claim="P",
        )

    async def test_no_scientific_verdict_without_a_decision(self):
        for status, decision, code in (("REFUTED", "CORROBORATION_MISMATCH", 6),
                                       ("REFUTED", "UNDECIDED", 5),
                                       ("VALIDATED", "CORROBORATION_MISMATCH", 0)):
            with self.subTest(status=status, decision=decision):
                result = await self._analyze(status, decision, code)
                self.assertEqual(result["status"], "CODE_ERROR")
                self.assertEqual(result["original_claim_verdict"], "INCONCLUSIVE")
                self.assertIn(f"DECISION {decision}", result["reasoning"])


if __name__ == "__main__":
    unittest.main()
