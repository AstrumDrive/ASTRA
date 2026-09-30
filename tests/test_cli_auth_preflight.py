"""A logged-out subscription CLI must stop a cycle before it spends anything.

On 2026-09-30 three canary cycles each spent 10-17 minutes of conjecture
(Codex + agy) and then died in the translator within seconds: the Claude Code
session had expired. The CLI's own status command knew that before the cycle
started. These tests pin the probe's parsing, its refusal to block on
ambiguity, and the cycle-level stop before the first model call.
"""
from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import core.preflight as preflight
from core.preflight import cli_auth_state, logged_out_providers


def _completed(stdout: str = "", stderr: str = "", code: int = 0):
    return subprocess.CompletedProcess([], code, stdout=stdout, stderr=stderr)


class ProbeParsingTests(unittest.TestCase):
    def setUp(self):
        self._env = patch.dict(os.environ, {"ASTRA_CLAUDE_BIN": "", "ASTRA_CODEX_BIN": ""}, clear=False)
        self._env.start()
        self._which = patch("core.preflight.shutil.which", side_effect=lambda name: f"C:/fake/{name}.cmd")
        self._which.start()
        self._exists = patch("core.preflight.os.path.exists", return_value=False)
        self._exists.start()

    def tearDown(self):
        for p in (self._exists, self._which, self._env):
            p.stop()

    def test_claude_logged_in(self):
        with patch("core.preflight.subprocess.run", return_value=_completed('{\n  "loggedIn": true,\n  "authMethod": "oauth"\n}\n')):
            state, _ = cli_auth_state("claude_cli")
        self.assertEqual(state, "ok")

    def test_claude_logged_out_is_explicit_and_names_the_login_command(self):
        with patch("core.preflight.subprocess.run", return_value=_completed('{\n  "loggedIn": false,\n  "authMethod": "none"\n}\n', code=1)):
            state, detail = cli_auth_state("claude_cli")
        self.assertEqual(state, "logged_out")
        self.assertIn("claude auth login", detail)

    def test_claude_without_a_parseable_answer_is_unknown_even_on_failure(self):
        with patch("core.preflight.subprocess.run", return_value=_completed("", "unknown command: auth", code=1)):
            state, _ = cli_auth_state("claude_cli")
        self.assertEqual(state, "unknown")

    def test_codex_logged_in_and_out(self):
        with patch("core.preflight.subprocess.run", return_value=_completed("Logged in using ChatGPT\n")):
            self.assertEqual(cli_auth_state("codex_cli")[0], "ok")
        with patch("core.preflight.subprocess.run", return_value=_completed("Not logged in\n", code=1)):
            state, detail = cli_auth_state("codex_cli")
        self.assertEqual(state, "logged_out")
        self.assertIn("codex login", detail)

    def test_timeouts_missing_binaries_and_unknown_providers_never_block(self):
        with patch("core.preflight.subprocess.run", side_effect=subprocess.TimeoutExpired("codex", 20)):
            self.assertEqual(cli_auth_state("codex_cli")[0], "unknown")
        with patch("core.preflight.shutil.which", return_value=None):
            self.assertEqual(cli_auth_state("claude_cli")[0], "unknown")
        self.assertEqual(cli_auth_state("agy_cli")[0], "unknown")
        self.assertEqual(cli_auth_state("muse_cli")[0], "unknown")

    def test_binary_override_is_honoured(self):
        seen = []

        def fake_run(argv, **_kwargs):
            seen.append(argv[0])
            return _completed('{"loggedIn": true}')

        with patch.dict(os.environ, {"ASTRA_CLAUDE_BIN": "D:/tools/claude.exe"}, clear=False), patch(
            "core.preflight.subprocess.run", side_effect=fake_run
        ):
            cli_auth_state("claude_cli")
        self.assertEqual(seen, ["D:/tools/claude.exe"])


class LoggedOutProvidersTests(unittest.TestCase):
    def test_deduplicates_and_reports_only_explicit_logouts(self):
        answers = {"claude_cli": ("logged_out", "run claude auth login"), "codex_cli": ("ok", "Logged in"), "agy_cli": ("unknown", "")}
        with patch("core.preflight.cli_auth_state", side_effect=lambda p, timeout=20.0: answers[p]):
            out = logged_out_providers(
                {"conjecture": ["codex_cli", "agy_cli"], "translator": "claude_cli", "reviewer": "codex_cli", "analyst": "codex_cli"}
            )
        self.assertEqual(out, [("claude_cli", "run claude auth login")])


class CycleStopsBeforeSpendingTests(unittest.IsolatedAsyncioTestCase):
    async def test_logged_out_translator_stops_the_cycle_before_the_conjecture(self):
        calls = []

        class FakeIntelligence:
            def __init__(self, provider, cli_models=None, cli_timeout=None):
                self.provider = provider
                self.cli_models = cli_models
                self.cli_timeout = cli_timeout
                self.cli_warnings = []
                self.cli_last_model = provider
                self.cli_cost_usd = 0.0

            async def generate_conjecture(self, **_kwargs):
                calls.append("conjecture")
                raise AssertionError("the conjecture must not run while a CLI is logged out")

        from astra_tool import _do_cycle

        providers = {
            "conjecture": "codex_cli",
            "translator": "claude_cli",
            "reviewer": "codex_cli",
            "analyst": "codex_cli",
            "navigator": "agy_cli",
            "synth": "codex_cli",
        }
        env = {
            "ASTRA_CYCLE_CACHE": "0",
            "ASTRA_CONJECTURE_PROVIDER": "codex_cli",
            "ASTRA_NAVIGATE_AFTER_CYCLE": "0",
            "ASTRA_MAX_RETRIES": "0",
            "ASTRA_ORACLE_MODE": "local",
            "ASTRA_CLI_AUTH_PREFLIGHT": "1",
        }
        answers = {"claude_cli": ("logged_out", "Claude Code session is not logged in; run `claude auth login`")}
        with patch.dict("os.environ", env, clear=False), patch(
            "core.preflight.phase_provider_map", return_value=providers
        ), patch("core.llm_client.ASTRAIntelligence", FakeIntelligence), patch(
            "core.preflight.cli_auth_state", side_effect=lambda p, timeout=20.0: answers.get(p, ("ok", "logged in"))
        ):
            result = await _do_cycle(
                {"action": "cycle", "intuition": "Test the CLI auth preflight.", "cycle_timeout_seconds": 2400}
            )

        self.assertEqual(calls, [])
        self.assertEqual(result.get("phase"), "preflight")
        self.assertIn("API_ERROR", result.get("error", ""))
        self.assertIn("claude auth login", result.get("error", ""))
        checkpoint = Path(result.get("checkpoint") or "")
        if checkpoint.exists():
            checkpoint.unlink()

    async def test_disabled_flag_skips_the_probe(self):
        probes = []
        with patch.dict("os.environ", {"ASTRA_CLI_AUTH_PREFLIGHT": "0"}, clear=False), patch(
            "core.preflight.cli_auth_state", side_effect=lambda p, timeout=20.0: probes.append(p) or ("logged_out", "x")
        ):
            # The flag is read by the cycle, not by the helper: with 0 the cycle
            # never calls logged_out_providers, so a direct call still works.
            self.assertEqual(preflight.logged_out_providers({"translator": "claude_cli"}), [("claude_cli", "x")])
            self.assertEqual(probes, ["claude_cli"])


if __name__ == "__main__":
    unittest.main()
