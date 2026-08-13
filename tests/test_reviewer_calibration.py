"""Reviewer calibration: decisive legs decide, auxiliary ones do not block.

Regression suite for the reliability bottleneck measured on 2026-08-12
(`docs/evidence/ASTRA2_H1_STANDARD_20260812.md`): three of 23 scientific
cases died operationally because the reviewer blocked validators whose
decisive legs its own reasoning called sound, objecting only to supplemental
sampling or finite grids. The calibration must remove that failure mode
WITHOUT weakening the scientific gate.
"""
import json
import unittest

from agents.reviewer import CODE_REVIEWER_PROMPT, CODE_REVIEWER_VNEXT_PROMPT
from core.llm_client import ASTRAIntelligence


class PromptContractTests(unittest.TestCase):
    def test_vnext_prompt_defines_decisive_versus_auxiliary(self):
        self.assertIn("DECISIVE VERSUS AUXILIARY LEGS", CODE_REVIEWER_VNEXT_PROMPT)
        self.assertIn("auxiliary_notes", CODE_REVIEWER_VNEXT_PROMPT)
        self.assertIn(
            "Do NOT return REVISE for an auxiliary imperfection",
            CODE_REVIEWER_VNEXT_PROMPT,
        )

    def test_the_gate_guard_is_stated_with_the_deciding_test(self):
        self.assertIn("THIS NEVER WEAKENS THE GATE", CODE_REVIEWER_VNEXT_PROMPT)
        self.assertIn("whether PASS DEPENDS on the", CODE_REVIEWER_VNEXT_PROMPT)
        self.assertIn("weak leg", CODE_REVIEWER_VNEXT_PROMPT)
        # Sampling that carries the verdict remains a labeled decisive defect.
        self.assertIn("sampling_as_proof", CODE_REVIEWER_VNEXT_PROMPT)

    def test_base_audit_rules_survive_the_addendum(self):
        # The calibration is additive: every base rule the gate depends on is
        # still present in the prompt actually sent in production.
        for rule in (
            "Reject self-confirming validators",
            "numerical sampling presented as proof",
            "hard-coded PASS",
            "unreachable FAIL paths",
            "honest failure over a false validation",
        ):
            with self.subTest(rule=rule):
                self.assertIn(rule, CODE_REVIEWER_PROMPT)
                self.assertIn(rule, CODE_REVIEWER_VNEXT_PROMPT)

    def test_addendum_extends_rather_than_replaces(self):
        self.assertTrue(
            CODE_REVIEWER_VNEXT_PROMPT.startswith(CODE_REVIEWER_PROMPT)
        )


class ParsingTests(unittest.IsolatedAsyncioTestCase):
    async def review_with(self, payload):
        reviewer = ASTRAIntelligence(provider="codex_cli")

        async def fake_call(_system, _user):
            return json.dumps(payload)

        reviewer._call_api = fake_call
        return await reviewer.review_validation_code(
            "Prove an identity", "For all x, x=x", "print('VERDICT: PASS')"
        )

    async def test_auxiliary_notes_are_captured_on_approval(self):
        result = await self.review_with(
            {
                "status": "APPROVED",
                "reasoning": "Exact symbolic leg decides the claim.",
                "revision_instructions": "",
                "coverage": ["exact identity"],
                "defect_labels": [],
                "runtime_checks": [],
                "auxiliary_notes": [
                    "The 101-point sample is illustrative and does not carry "
                    "the verdict."
                ],
            }
        )
        self.assertEqual(result["status"], "APPROVED")
        self.assertEqual(len(result["auxiliary_notes"]), 1)
        self.assertIn("illustrative", result["auxiliary_notes"][0])

    async def test_auxiliary_notes_never_change_the_status(self):
        result = await self.review_with(
            {
                "status": "REVISE",
                "reasoning": "Decisive leg missing.",
                "revision_instructions": "Add the exact leg.",
                "coverage": [],
                "defect_labels": ["sampling_as_proof"],
                "runtime_checks": [],
                "auxiliary_notes": ["grid is coarse"],
            }
        )
        self.assertEqual(result["status"], "REVISE")
        self.assertEqual(result["defect_labels"], ["sampling_as_proof"])
        self.assertEqual(result["auxiliary_notes"], ["grid is coarse"])

    async def test_missing_field_defaults_to_empty_not_absent(self):
        result = await self.review_with(
            {
                "status": "APPROVED",
                "reasoning": "ok",
                "revision_instructions": "",
                "coverage": [],
                "defect_labels": [],
                "runtime_checks": [],
            }
        )
        self.assertEqual(result["auxiliary_notes"], [])

    async def test_malformed_auxiliary_notes_degrade_safely(self):
        for value in ("not a list", 42, None, {"a": 1}):
            with self.subTest(value=value):
                result = await self.review_with(
                    {
                        "status": "APPROVED",
                        "reasoning": "ok",
                        "revision_instructions": "",
                        "coverage": [],
                        "defect_labels": [],
                        "runtime_checks": [],
                        "auxiliary_notes": value,
                    }
                )
                self.assertEqual(result["auxiliary_notes"], [])

    async def test_defect_label_whitelist_is_unchanged(self):
        result = await self.review_with(
            {
                "status": "REVISE",
                "reasoning": "bad",
                "revision_instructions": "fix",
                "coverage": [],
                "defect_labels": ["sampling_as_proof", "invented_label"],
                "runtime_checks": [],
                "auxiliary_notes": [],
            }
        )
        self.assertEqual(result["defect_labels"], ["sampling_as_proof"])


if __name__ == "__main__":
    unittest.main()
