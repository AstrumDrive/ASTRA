"""A reply that is not a script is not a script to patch.

Measured 2026-08-14 (`docs/evidence/ASTRA2_PLAN_ARTIFACT_INJECTION_20260814.md`):
a leaked plan-mode line told the translator to read a file, and with no tools to
do it the model answered with forty repetitions of "**Tool call:** let me read
it". ASTRA fed that back as "your previous code, fix the unterminated string on
line 1" - an impossible instruction - and the next call spent all 64000 output
tokens without emitting a character.

A damaged script and a non-script both fail to parse, but they need opposite
treatments: patch the first, discard the second.
"""
import unittest
from unittest.mock import patch

from agents.translator import NOT_CODE_RETRY_INSTRUCTIONS
from astra_tool import _do_cycle
from core.validator_preflight import audit_validation_code, looks_like_prose

# Verbatim from the child CLI transcript, abridged.
REAL_PROSE = (
    "I'll start by reviewing the plan artifact the user pointed me to, then "
    "assess it before constructing the validator.\n\n"
    "**Tool call:**\nRead plan.md at the referenced path.\n\n"
    "**Tool call:**\n\nLet me read it.\n\n"
    "**Tool call:**\n\nI'll read the file now.\n\n"
    "**Tool:**\n\nI seem to be stuck. Let me actually make the tool call.\n"
)

# A real validator with one broken line: worth patching, must NOT be discarded.
DAMAGED_SCRIPT = (
    "import sympy as sp\n"
    "\n"
    "R = sp.Symbol('R', positive=True)\n"
    "expr = sp.Rational(1, 2) * R**2\n"
    "if expr.is_positive:\n"
    "    print('CHECK positive: OK'\n"          # <- missing paren
    "else:\n"
    "    print('CHECK positive: FAIL')\n"
)


class ClassificationTests(unittest.TestCase):
    def test_the_real_prose_is_recognised(self):
        self.assertTrue(looks_like_prose(REAL_PROSE))

    def test_a_damaged_script_keeps_its_right_to_a_repair(self):
        self.assertFalse(looks_like_prose(DAMAGED_SCRIPT))

    def test_working_code_is_never_prose(self):
        self.assertFalse(looks_like_prose("print('VERDICT: PASS')\n"))

    def test_the_labels_separate_the_two_cases(self):
        self.assertEqual(
            audit_validation_code(REAL_PROSE)["findings"][0]["label"],
            "not_code_at_all",
        )
        self.assertEqual(
            audit_validation_code(DAMAGED_SCRIPT)["findings"][0]["label"],
            "syntax_error",
        )

    def test_both_still_block(self):
        for code in (REAL_PROSE, DAMAGED_SCRIPT):
            with self.subTest(code=code[:32]):
                audit = audit_validation_code(code)
                self.assertEqual(audit["status"], "REVISE")
                self.assertEqual(audit["critical_count"], 1)


class RegenerationTests(unittest.IsolatedAsyncioTestCase):
    async def _run(self, first_reply):
        calls = []

        class FakeIntelligence:
            def __init__(self, provider, cli_models=None, cli_timeout=None):
                self.provider = provider
                self.cli_models = cli_models
                self.cli_timeout = cli_timeout
                self.cli_warnings = []
                self.cli_last_model = None
                self.cli_cost_usd = 0.0

            async def generate_conjecture(self, axiomatic_base, intuition):
                return "Prove the NEC is violated at p."

            async def translate_to_code(self, _conjecture, **kwargs):
                calls.append(kwargs)
                if len(calls) == 1:
                    return first_reply
                return "print('CHECK ok: OK')\nprint('VERDICT: PASS')\n"

            async def review_validation_code(self, **_kwargs):
                return {
                    "status": "APPROVED",
                    "reasoning": "fine",
                    "revision_instructions": "",
                    "coverage": [],
                    "defect_labels": [],
                    "runtime_checks": [],
                }

            async def repair_validation_code(self, *args, **_kwargs):
                return {"status": "REJECTED", "reason": "n/a",
                        "code": args[1], "edits": []}

            async def analyze_results(self, *_args, **_kwargs):
                return {"status": "VALIDATED", "reasoning": "ok"}

        env = {
            "ASTRA_CYCLE_CACHE": "0",
            "ASTRA_CONJECTURE_PROVIDER": "codex_cli",
            "ASTRA_VALIDATOR_REPAIR_VNEXT": "1",
            "ASTRA_VALIDATOR_REPAIR_STRATEGY": "local-patch",
            "ASTRA_VNEXT_MODEL_PATCH_MAX_REVISIONS": "1",
            "ASTRA_NAVIGATE_AFTER_CYCLE": "0",
            "ASTRA_MAX_RETRIES": "0",
            "ASTRA_ORACLE_MODE": "local",
        }
        providers = {
            "conjecture": "codex_cli", "translator": "claude_cli",
            "reviewer": "codex_cli", "analyst": "codex_cli",
            "navigator": "agy_cli", "synth": "codex_cli",
        }
        with patch.dict("os.environ", env, clear=False), patch(
            "core.preflight.phase_provider_map", return_value=providers
        ), patch("core.llm_client.ASTRAIntelligence", FakeIntelligence):
            result = await _do_cycle({
                "action": "cycle",
                "intuition": "Decide the NEC at the wall point.",
                "cycle_timeout_seconds": 120,
            })
        from pathlib import Path

        checkpoint = Path(result.get("checkpoint") or "")
        if checkpoint.name and checkpoint.exists():
            checkpoint.unlink()
        return calls, result

    async def test_prose_is_not_quoted_back_as_previous_code(self):
        calls, _result = await self._run(REAL_PROSE)
        self.assertEqual(len(calls), 2, "expected one regeneration")
        retry = calls[1]
        self.assertIsNone(retry.get("previous_code"))
        self.assertEqual(retry.get("previous_error"), NOT_CODE_RETRY_INSTRUCTIONS)

    async def test_a_damaged_script_is_still_handed_back_for_repair(self):
        calls, _result = await self._run(DAMAGED_SCRIPT)
        self.assertEqual(len(calls), 2)
        retry = calls[1]
        self.assertEqual(retry.get("previous_code"), DAMAGED_SCRIPT)
        self.assertNotEqual(
            retry.get("previous_error"), NOT_CODE_RETRY_INSTRUCTIONS
        )


if __name__ == "__main__":
    unittest.main()
