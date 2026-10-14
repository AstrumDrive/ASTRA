"""A posed request skips the conjecture cross-critique only when the
proposals agree (1.1.18, gated by agreement in 1.1.20)."""
import os
import unittest
from unittest.mock import patch

from astra_tool import _AGREEMENT_GATE, _ensemble_conjecture, _request_is_posed, _split_agreement
from core.llm_client import ASTRAIntelligence

POSED = ("Definitions. Pauli matrices sigma_1, sigma_2, sigma_3 as usual; gamma matrices "
         "built from them in the Dirac representation; metric diag(+1,-1,-1,-1).\n"
         "Claim: the anticommutator of gamma^mu and gamma^nu equals 2 eta^{mu nu} I_4.\n"
         "Decide with exact 4x4 matrices.")
VAGUE = "Check whether the gamma matrices behave as they should."


class Detection(unittest.TestCase):
    def test_needs_the_switch_a_claim_line_and_some_definitions(self):
        with patch.dict(os.environ, {"ASTRA_CONJECTURE_SKIP_CRITIQUE_WHEN_POSED": "1"}):
            self.assertTrue(_request_is_posed(POSED))
            self.assertFalse(_request_is_posed(VAGUE))
            self.assertFalse(_request_is_posed("Claim: x = 1"))
        with patch.dict(os.environ, {"ASTRA_CONJECTURE_SKIP_CRITIQUE_WHEN_POSED": "0"}):
            self.assertFalse(_request_is_posed(POSED))


class AgreementLine(unittest.TestCase):
    def test_parses_plain_and_decorated_lines(self):
        self.assertEqual(_split_agreement("AGREEMENT: SAME\nThe conjecture."),
                         ("SAME", "", "The conjecture."))
        verdict, reason, body = _split_agreement(
            "**AGREEMENT:** DIFFERENT - B uses another metric signature\nMerged text")
        self.assertEqual((verdict, body), ("DIFFERENT", "Merged text"))
        self.assertIn("metric signature", reason)
        self.assertEqual(_split_agreement("agreement: same\nx")[0], "SAME")

    def test_missing_line_is_unreadable(self):
        self.assertIsNone(_split_agreement("The conjecture, no verdict line.")[0])
        self.assertIsNone(_split_agreement("")[0])
        self.assertIsNone(_split_agreement("AGREEMENT: SAMEISH\nx")[0])


class Ensemble(unittest.IsolatedAsyncioTestCase):
    async def _run(self, intuition, switch, gated_reply="AGREEMENT: SAME\nmerged without critique"):
        calls = {"critique": 0, "gated_merge": 0, "full_merge": 0}

        async def generate(_self, axiomatic_base, intuition):
            return "Conjecture from %s" % _self.provider

        async def call_api(_self, system, user):
            if "RIVAL" in user:
                calls["critique"] += 1
                return "critique"
            if system.endswith(_AGREEMENT_GATE):
                calls["gated_merge"] += 1
                calls["gated_input"] = user
                return gated_reply
            calls["full_merge"] += 1
            calls["full_input"] = user
            return "merged after critique"

        env = {"ASTRA_CONJECTURE_SKIP_CRITIQUE_WHEN_POSED": switch}
        with patch.dict(os.environ, env), \
                patch.object(ASTRAIntelligence, "generate_conjecture", generate), \
                patch.object(ASTRAIntelligence, "_call_api", call_api):
            merged, _used, trace = await _ensemble_conjecture(
                ["codex_cli", "agy_cli"], "axioms", intuition, 30, "codex_cli")
        return merged, trace, calls

    async def test_agreeing_proposals_skip_the_critique(self):
        merged, trace, calls = await self._run(POSED, "1")
        self.assertEqual(merged, "merged without critique")
        self.assertEqual((calls["critique"], calls["gated_merge"], calls["full_merge"]), (0, 1, 0))
        self.assertIn("Conjecture from agy_cli", calls["gated_input"])
        self.assertEqual(trace["critiques"], [])
        self.assertEqual(trace["critique_skipped"], "posed_request_agreed")
        self.assertEqual(trace["agreement_gate"]["agreement"], "SAME")

    async def test_disagreeing_proposals_bring_the_critique_back(self):
        merged, trace, calls = await self._run(
            POSED, "1", "AGREEMENT: DIFFERENT - A tests the trace, B the anticommutator\nx")
        self.assertEqual(merged, "merged after critique")
        self.assertEqual((calls["critique"], calls["gated_merge"], calls["full_merge"]), (2, 1, 1))
        self.assertIn("Critica de agy_cli", calls["full_input"])
        self.assertEqual(len(trace["critiques"]), 2)
        self.assertNotIn("critique_skipped", trace)
        self.assertEqual(trace["agreement_gate"]["agreement"], "DIFFERENT")
        self.assertIn("anticommutator", trace["agreement_gate"]["reason"])

    async def test_unreadable_gate_is_treated_as_disagreement(self):
        merged, trace, calls = await self._run(POSED, "1", "Just a conjecture, no verdict line")
        self.assertEqual(merged, "merged after critique")
        self.assertEqual(calls["critique"], 2)
        self.assertEqual(trace["agreement_gate"]["agreement"], "UNREADABLE")

    async def test_vague_request_never_asks_the_gate(self):
        _merged, trace, calls = await self._run(VAGUE, "1")
        self.assertEqual((calls["critique"], calls["gated_merge"], calls["full_merge"]), (2, 0, 1))
        self.assertNotIn("agreement_gate", trace)


if __name__ == "__main__":
    unittest.main()
