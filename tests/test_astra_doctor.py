"""The doctor must tell a restricted-context WSL denial apart from a missing engine.

Sage, Maxima and Cadabra live in Debian WSL on this workstation. From a normal
shell they route and the doctor shows them PASS. From a restricted context (the
Codex sandbox, whose token cannot reach WSL) available_cas() returns None for
all of them and the architecture contract fails closed -- correct as a gate,
but it must NOT read as "the engines are not installed". These tests pin the two
renderings so a future refactor cannot quietly collapse them back together.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import astra_doctor  # noqa: E402


def _run_doctor():
    with patch.object(sys, "argv", ["astra_doctor.py", "--json"]):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            astra_doctor.main()
    report = json.loads(buffer.getvalue())
    return {check["name"]: check for check in report["checks"]}


class AstraDoctorWslAwarenessTests(unittest.TestCase):
    def test_denied_wsl_is_reported_as_a_context_not_a_missing_engine(self):
        denied = {"state": "denied", "detail": "Wsl/Service/E_ACCESSDENIED"}
        cas_none = {"sage": None, "maxima": None, "cadabra": None, "lean4": None}
        arch_fail = {
            "status": "FAIL",
            "required_failures": [
                "scientific_engine_sage",
                "scientific_engine_maxima",
                "scientific_engine_cadabra",
            ],
        }
        with patch("platform.system", return_value="Windows"), patch(
            "core.engine_router.wsl_probe_state", return_value=denied
        ), patch(
            "core.engine_router.available_cas", return_value=cas_none
        ), patch(
            "astra_doctor.audit_production_architecture", return_value=arch_fail
        ), patch("astra_doctor._cli_available", return_value=True):
            checks = _run_doctor()

        self.assertEqual(checks["wsl_bridge"]["status"], "OPTIONAL_MISSING")
        self.assertIn("DENIED in this context", checks["wsl_bridge"]["detail"])
        for engine in ("optional:sage", "optional:maxima", "optional:cadabra2"):
            self.assertIn("denied via WSL", checks[engine]["detail"])
            self.assertIn("not missing", checks[engine]["detail"])
        # The contract still fails closed, but the human-facing line says why.
        self.assertIn("WSL-routed engines", checks["architecture_contract"]["detail"])
        self.assertIn(
            "engines are installed", checks["architecture_contract"]["detail"]
        )

    def test_reachable_wsl_reports_the_routed_engines_as_present(self):
        ok = {"state": "ok", "detail": "wsl -d Debian reachable"}
        cas_ok = {
            "sage": "wsl -d Debian -- sage",
            "maxima": "wsl -d Debian -- maxima",
            "cadabra": "wsl -d Debian -- cadabra2",
            "lean4": None,
        }
        arch_pass = {"status": "PASS", "required_failures": []}
        with patch("platform.system", return_value="Windows"), patch(
            "core.engine_router.wsl_probe_state", return_value=ok
        ), patch(
            "core.engine_router.available_cas", return_value=cas_ok
        ), patch(
            "astra_doctor.audit_production_architecture", return_value=arch_pass
        ), patch("astra_doctor._cli_available", return_value=True):
            checks = _run_doctor()

        self.assertEqual(checks["wsl_bridge"]["status"], "PASS")
        for engine in ("optional:sage", "optional:maxima", "optional:cadabra2"):
            self.assertEqual(checks[engine]["status"], "PASS")
            self.assertIn("wsl -d Debian", checks[engine]["detail"])


class CliVersionTests(unittest.TestCase):
    """The pinned models are refused (400) by old CLIs: Opus 5.5 by Claude Code
    older than 2.1.280, GPT-6 Luna by Codex older than 0.157 on a ChatGPT
    account. The doctor must say so before a model phase does."""

    def _checks_with_versions(self, versions):
        ok = {"state": "ok", "detail": "wsl -d Debian reachable"}
        arch_pass = {"status": "PASS", "required_failures": []}

        def fake_version(location):
            return versions.get(Path(location).stem)

        with patch("platform.system", return_value="Windows"), patch(
            "core.engine_router.wsl_probe_state", return_value=ok
        ), patch(
            "core.engine_router.available_cas", return_value={}
        ), patch(
            "astra_doctor.audit_production_architecture", return_value=arch_pass
        ), patch("astra_doctor._cli_available", return_value=True), patch(
            "shutil.which", side_effect=lambda name: f"C:/fake/bin/{name}.exe"
        ), patch("astra_doctor.cli_version", side_effect=fake_version):
            return _run_doctor()

    def test_old_clis_fail_with_their_upgrade_commands(self):
        checks = self._checks_with_versions({"claude": (2, 1, 237), "codex": (0, 153, 0)})
        self.assertEqual(checks["cli:claude_version"]["status"], "FAIL")
        self.assertIn("2.1.237", checks["cli:claude_version"]["detail"])
        self.assertIn("2.1.280", checks["cli:claude_version"]["detail"])
        self.assertIn("npm install -g @anthropic-ai/claude-code", checks["cli:claude_version"]["detail"])
        self.assertEqual(checks["cli:codex_version"]["status"], "FAIL")
        self.assertIn("0.153.0", checks["cli:codex_version"]["detail"])
        self.assertIn("0.157.0", checks["cli:codex_version"]["detail"])
        self.assertIn("codex update", checks["cli:codex_version"]["detail"])

    def test_current_clis_pass(self):
        checks = self._checks_with_versions({"claude": (2, 1, 282), "codex": (0, 157, 0)})
        self.assertEqual(checks["cli:claude_version"]["status"], "PASS")
        self.assertEqual(checks["cli:codex_version"]["status"], "PASS")

    def test_unreadable_version_fails_closed(self):
        checks = self._checks_with_versions({})
        self.assertEqual(checks["cli:claude_version"]["status"], "FAIL")
        self.assertIn("unknown", checks["cli:claude_version"]["detail"])
        self.assertEqual(checks["cli:codex_version"]["status"], "FAIL")

    def test_parser_reads_both_banners(self):
        for banner, expected in (
            ("2.1.282 (Claude Code)\n", (2, 1, 282)),
            ("codex-cli 0.157.0\n", (0, 157, 0)),
        ):
            completed = subprocess.CompletedProcess([], 0, stdout=banner)
            with patch("astra_doctor.subprocess.run", return_value=completed):
                self.assertEqual(astra_doctor.cli_version("x"), expected)
        with patch("astra_doctor.subprocess.run", side_effect=OSError("no such file")):
            self.assertIsNone(astra_doctor.cli_version("x"))


if __name__ == "__main__":
    unittest.main()
