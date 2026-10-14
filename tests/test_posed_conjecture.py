"""A posed request skips the cross-critique round of the conjecture (1.1.18)."""
import os
import unittest
from unittest.mock import patch

from astra_tool import _ensemble_conjecture, _request_is_posed
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


class Ensemble(unittest.IsolatedAsyncioTestCase):
    async def _run(self, intuition, switch):
        calls = {"critique": 0, "merge": 0}

        async def generate(_self, axiomatic_base, intuition):
            return "Conjecture from %s" % _self.provider

        async def call_api(_self, system, user):
            if "RIVAL" in user:
                calls["critique"] += 1
                return "critique"
            calls["merge"] += 1
            calls["merge_input"] = user
            return "merged conjecture"

        env = {"ASTRA_CONJECTURE_SKIP_CRITIQUE_WHEN_POSED": switch}
        with patch.dict(os.environ, env), \
                patch.object(ASTRAIntelligence, "generate_conjecture", generate), \
                patch.object(ASTRAIntelligence, "_call_api", call_api):
            merged, used, trace = await _ensemble_conjecture(
                ["codex_cli", "agy_cli"], "axioms", intuition, 30, "codex_cli")
        return merged, trace, calls

    async def test_posed_request_merges_without_critiques(self):
        merged, trace, calls = await self._run(POSED, "1")
        self.assertEqual(merged, "merged conjecture")
        self.assertEqual(calls["critique"], 0)
        self.assertEqual(calls["merge"], 1)
        self.assertIn("Conjecture from agy_cli", calls["merge_input"])
        self.assertEqual(trace["critiques"], [])
        self.assertEqual(trace["critique_skipped"], "posed_request")

    async def test_vague_request_keeps_the_critique_round(self):
        _merged, trace, calls = await self._run(VAGUE, "1")
        self.assertEqual(calls["critique"], 2)
        self.assertEqual(len(trace["critiques"]), 2)
        self.assertNotIn("critique_skipped", trace)


if __name__ == "__main__":
    unittest.main()
