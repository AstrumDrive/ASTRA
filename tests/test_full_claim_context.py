"""Regression for source audit 20261005: author and reviewer saw different specs."""
import unittest

from astra_tool import build_translation_input
from core.llm_client import ASTRAIntelligence
from tests.test_input_request_cycle import _fake, _run, DECIDED_CODE
from tests.cycle_artifacts import remove_cycle_artifacts


CLAIM = "Definitions: " + "x" * 6000 + "\nD_s=the prescribed disk; z_aff=all nine coordinates; epsilon cap exact."


class FullClaimContextTests(unittest.IsolatedAsyncioTestCase):
    async def test_cycle_reviewer_receives_same_authoritative_context_as_author(self):
        fake = _fake(DECIDED_CODE, {"status": "REFUTED", "reasoning": "test evidence"})
        result = await _run(fake, {"intuition": CLAIM})
        try:
            self.assertIn(CLAIM, fake.seen["translation_inputs"][0])
            self.assertTrue(fake.seen["review_conjectures"])
            for context in fake.seen["review_conjectures"]:
                self.assertEqual(context, fake.seen["translation_inputs"][0])
        finally:
            remove_cycle_artifacts(result)

    async def test_real_reviewer_prompt_preserves_tail_definitions(self):
        client = ASTRAIntelligence(provider="codex_cli")
        seen = []

        async def fake_call(system, user):
            seen.append(user)
            return '{"status":"REJECT","reasoning":"test only"}'

        client._call_api = fake_call
        context = build_translation_input("goal", CLAIM, "", "Only domain containment")
        await client.review_validation_code("goal", context, "print('VERDICT: FAIL')")
        self.assertIn(context, seen[0])

    async def test_real_repair_prompt_preserves_tail_definitions(self):
        client = ASTRAIntelligence(provider="claude_cli")
        seen = []

        async def fake_call(system, user):
            seen.append(user)
            return '{"status":"CANNOT_PATCH","reason":"test only","edits":[]}'

        client._call_api = fake_call
        context = build_translation_input("goal", CLAIM, "", "Only domain containment")
        await client.repair_validation_code(context, "print('VERDICT: FAIL')", "test repair")
        self.assertIn(context, seen[0])


if __name__ == "__main__":
    unittest.main()
