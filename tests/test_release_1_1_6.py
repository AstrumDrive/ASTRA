"""Regressions for the fixes shipped in 1.1.6 (technical-reference review, 2026-10-05)."""
from __future__ import annotations

import os
import re
import unittest
from unittest.mock import patch

from agents.reviewer import CODE_REVIEWER_VNEXT_PROMPT
from core.architecture_configs import architecture_roles
from core.architecture_contract import production_manifest
from core.cli_backend import _codex_builder
from tests.cycle_artifacts import remove_cycle_artifacts
from tests.test_input_request_cycle import DECIDED_CODE, _fake, _run


class AnalystBudgetGuardTests(unittest.IsolatedAsyncioTestCase):
    """The ANALYST minimum (90 s) existed since 1.1.1 but was never checked."""

    async def test_starved_analysis_returns_partial_without_calling_the_analyst(self):
        fake = _fake(DECIDED_CODE, {"status": "REFUTED", "reasoning": "should not be reached"})
        # 140 s wall - 60 s return buffer = 80 s usable < 90 s analyst minimum.
        # Review off, so the reviewer's own guard does not stop the cycle first.
        with patch.dict(os.environ, {"ASTRA_CODE_REVIEW": "0"}, clear=False):
            result = await _run(fake, {"cycle_timeout_seconds": 140})
        try:
            self.assertEqual(result.get("status"), "PARTIAL", result.get("error"))
            self.assertIn("analysis", result.get("error", ""))
            self.assertNotIn("analysis_conjectures", fake.seen)
        finally:
            remove_cycle_artifacts(result)

    async def test_ample_budget_still_analyses(self):
        fake = _fake(DECIDED_CODE, {"status": "REFUTED", "reasoning": "sign check failed"})
        with patch.dict(os.environ, {"ASTRA_CODE_REVIEW": "0"}, clear=False):
            result = await _run(fake, {"cycle_timeout_seconds": 1500})
        try:
            self.assertEqual(result.get("status"), "REFUTED", result.get("error"))
            self.assertIn("analysis_conjectures", fake.seen)
        finally:
            remove_cycle_artifacts(result)


class ManifestRolesTests(unittest.TestCase):
    def test_no_ensemble_manifest_declares_its_own_roles(self):
        # No provider variables: the role defaults must be no-ensemble's, not full's.
        env = {"ASTRA_ARCHITECTURE_PROFILE": "no-ensemble"}
        roles = production_manifest(env)["roles"]
        self.assertEqual(roles["proposers"], architecture_roles("no-ensemble")["proposers"])
        self.assertNotEqual(roles["proposers"], architecture_roles("full")["proposers"])


class CodexEffortDefaultTests(unittest.TestCase):
    def _argv_text(self, os_name):
        env = {k: v for k, v in os.environ.items() if k != "ASTRA_CODEX_REASONING"}
        env["ASTRA_CODEX_BIN"] = ""
        with patch("core.cli_backend.os.name", os_name), patch(
            "core.cli_backend.shutil.which", return_value="codex"
        ), patch.dict(os.environ, env, clear=True):
            command = _codex_builder("prompt.txt", None, "out.txt", "ws")
        return " ".join(command["argv"]) if isinstance(command, dict) else str(command)

    def test_unset_variable_defaults_to_the_audited_effort_on_posix(self):
        self.assertIn('model_reasoning_effort="xhigh"', self._argv_text("posix"))

    def test_unset_variable_defaults_to_the_audited_effort_on_windows(self):
        self.assertIn("xhigh", self._argv_text("nt"))


class ReviewerRuleNumberingTests(unittest.TestCase):
    def test_rule_numbers_are_unique(self):
        numbers = re.findall(r"(?m)^(\d+)\. ", CODE_REVIEWER_VNEXT_PROMPT)
        self.assertEqual(len(numbers), len(set(numbers)), numbers)


if __name__ == "__main__":
    unittest.main()
