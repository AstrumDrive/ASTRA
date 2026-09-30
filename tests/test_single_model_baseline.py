"""The single-model baseline arm measures one unaided model, nothing else.

Recommendation 2 of docs/evidence/ASTRA_EFFICIENCY_AUDIT_20260930.md: the
question "is ASTRA more than the models used separately" needs an arm where
one model proposes once, writes the validator, reads the oracle output and
answers, with no reviewer, no deterministic guard, no repair loop, no retry
and no navigation. These tests pin that the arm is wired exactly that way and
that the guard switch it relies on really disables the degradation.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from core.architecture_configs import (
    ARCHITECTURE_ROLES,
    SINGLE_MODEL_ENVIRONMENT,
    architecture_environment,
)


class SingleModelArmTests(unittest.TestCase):
    def test_one_proposal_by_the_same_model_everywhere(self):
        roles = ARCHITECTURE_ROLES["single-model"]
        self.assertEqual(roles["proposers"], ["codex_cli"])
        for role in ("synthesizer", "author", "reviewer", "repairer"):
            self.assertEqual(roles[role], "codex_cli")

    def test_environment_removes_every_safety_net_but_execution(self):
        env = architecture_environment("single-model", base={"ASTRA_CODE_REVIEW": "1", "ASTRA_MAX_RETRIES": "2"})
        self.assertEqual(env["ASTRA_CONJECTURE_PROVIDER"], "codex_cli")
        self.assertEqual(env["ASTRA_TRANSLATOR_PROVIDER"], "codex_cli")
        self.assertEqual(env["ASTRA_ANALYST_PROVIDER"], "codex_cli")
        for key, value in SINGLE_MODEL_ENVIRONMENT.items():
            self.assertEqual(env[key], value, key)
        self.assertEqual(env["ASTRA_CODE_REVIEW"], "0")
        self.assertEqual(env["ASTRA_VERDICT_GUARD"], "0")
        self.assertEqual(env["ASTRA_MAX_RETRIES"], "0")
        self.assertEqual(env["ASTRA_CYCLE_CACHE"], "0")

    def test_other_arms_keep_the_guard(self):
        env = architecture_environment("no-ensemble", base={})
        self.assertNotIn("ASTRA_VERDICT_GUARD", env)
        self.assertNotIn("ASTRA_CODE_REVIEW", env)


class GuardSwitchTests(unittest.TestCase):
    def test_guard_degrades_by_default_and_not_when_switched_off(self):
        from astra_tool import _apply_guard

        suspect = {"guard": {"verdict_suspect": True, "reasons": ["no reachable FAIL"]}}
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ASTRA_VERDICT_GUARD", None)
            degraded = _apply_guard({"status": "VALIDATED", "reasoning": "ok"}, suspect)
        self.assertEqual(degraded["status"], "WEAK_PASS")
        with patch.dict(os.environ, {"ASTRA_VERDICT_GUARD": "0"}, clear=False):
            kept = _apply_guard({"status": "VALIDATED", "reasoning": "ok"}, suspect)
        self.assertEqual(kept["status"], "VALIDATED")


if __name__ == "__main__":
    unittest.main()
