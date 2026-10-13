"""Per-rung reasoning effort ('gpt-6.1-sol@ultra') and the 2026-10-12 ladders."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from core.architecture_contract import EXPECTED_PRIMARY_MODELS, audit_production_architecture
from core.cli_backend import _claude_argv, _codex_builder, split_model_effort


def _argv(built):
    return built["argv"] if isinstance(built, dict) else built


class SplitTests(unittest.TestCase):
    def test_split(self):
        self.assertEqual(split_model_effort("gpt-6.1-sol@ultra"), ("gpt-6.1-sol", "ultra"))
        self.assertEqual(split_model_effort("sonnet"), ("sonnet", None))
        self.assertEqual(split_model_effort("default@high"), (None, "high"))
        self.assertEqual(split_model_effort(None), (None, None))


class ClaudeEffortTests(unittest.TestCase):
    def test_rung_effort_is_passed_and_stripped_from_the_model(self):
        argv = _argv(_claude_argv("p.txt", "claude-fable-5-1@max", "", ""))
        self.assertEqual(argv[argv.index("--model") + 1], "claude-fable-5-1")
        self.assertEqual(argv[argv.index("--effort") + 1], "max")

    def test_no_effort_keeps_the_cli_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ASTRA_CLAUDE_EFFORT", None)
            argv = _argv(_claude_argv("p.txt", "claude-opus-5-5", "", ""))
        self.assertNotIn("--effort", argv)

    def test_an_effort_the_cli_refuses_is_dropped_not_sent(self):
        argv = _argv(_claude_argv("p.txt", "claude-opus-5-5@ultra", "", ""))
        self.assertNotIn("--effort", argv)


class CodexEffortTests(unittest.TestCase):
    def _text(self, os_name, model):
        with patch("core.cli_backend.os.name", os_name), patch(
            "core.cli_backend.shutil.which", return_value="codex"
        ), patch.dict(os.environ, {"ASTRA_CODEX_REASONING": "xhigh", "ASTRA_CODEX_BIN": ""}, clear=False):
            built = _codex_builder("p.txt", model, "out.txt", "ws")
        return " ".join(_argv(built)) if isinstance(built, dict) else built

    def test_rung_effort_wins_over_the_cli_wide_setting(self):
        for os_name in ("posix", "nt"):
            with self.subTest(os_name=os_name):
                text = self._text(os_name, "gpt-6.1-sol@ultra")
                self.assertIn("gpt-6.1-sol", text)
                self.assertNotIn("@ultra", text)
                self.assertIn("ultra", text)
                self.assertNotIn("xhigh", text)

    def test_plain_rung_keeps_the_cli_wide_effort(self):
        self.assertIn("xhigh", self._text("posix", "gpt-6-luna"))


class ContractTests(unittest.TestCase):
    def test_primaries_are_the_models_the_clis_offer_on_2026_10_12(self):
        self.assertEqual(EXPECTED_PRIMARY_MODELS["codex_cli"], "gpt-6.1-sol")
        self.assertEqual(EXPECTED_PRIMARY_MODELS["agy_cli"], "gemini-3.8-flash")

    def test_effort_suffix_does_not_break_the_primary_check(self):
        env = {
            "ASTRA_ARCHITECTURE_PROFILE": "no-ensemble",
            "ASTRA_CONJECTURE_PROVIDER": "codex_cli",
            "ASTRA_SYNTH_PROVIDER": "codex_cli",
            "ASTRA_TRANSLATOR_PROVIDER": "claude_cli",
            "ASTRA_REVIEWER_PROVIDER": "codex_cli",
            "ASTRA_ANALYST_PROVIDER": "codex_cli",
            "ASTRA_NAVIGATOR_PROVIDER": "agy_cli",
            "ASTRA_CODEX_MODELS": "gpt-6.1-sol@xhigh,gpt-6-luna@xhigh",
            "ASTRA_CONJECTURE_MODELS": "gpt-6.1-sol@ultra,gpt-6-luna@xhigh",
            "ASTRA_REVIEWER_MODELS": "gpt-6.1-sol@max,gpt-6-luna@xhigh",
            "ASTRA_ANALYST_MODELS": "gpt-6.1-sol@ultra,gpt-6-luna@xhigh",
            "ASTRA_CLAUDE_MODELS": "claude-opus-5-5@high,sonnet@high",
            "ASTRA_TRANSLATOR_MODELS": "claude-opus-5-5@high,sonnet@high",
            "ASTRA_AGY_MODELS": "gemini-3.8-flash@high",
            "ASTRA_CODEX_REASONING": "xhigh",
            "ASTRA_AGY_EFFORT": "high",
            "ASTRA_CODE_REVIEW": "1",
            "ASTRA_NAVIGATE_AFTER_CYCLE": "0",
            "ASTRA_VALIDATOR_REPAIR_VNEXT": "1",
            "ASTRA_VALIDATOR_REPAIR_STRATEGY": "local-patch",
        }
        audit = audit_production_architecture(env, check_binaries=False)
        model_checks = [c for c in audit["checks"] if c["id"].endswith("_model")]
        self.assertGreaterEqual(len(model_checks), 6)
        failed = [c for c in model_checks if not c["passed"]]
        self.assertEqual(failed, [], failed)


if __name__ == "__main__":
    unittest.main()
