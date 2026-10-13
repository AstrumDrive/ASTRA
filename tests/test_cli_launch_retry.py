"""Transient CLI launch failures are retried (1.1.11, from ASTRA 2.0 bcffa0a)."""
import os
import unittest
from unittest.mock import patch

from core.cli_backend import _invoke_once


class _FakeProc:
    """Minimal stand-in for a launched process that returns a clean result."""

    def __init__(self, stdout="VERDICT: PASS\n"):
        self.pid = 4242
        self.returncode = 0
        self._stdout = stdout

    def communicate(self, timeout=None):
        return self._stdout, ""


def _invoke_codex(popen):
    """Run _invoke_once for a trivial codex build with a patched Popen."""
    with patch.dict("core.cli_backend._BUILDERS", {"codex": lambda pf, m, of, ws: ["codex"]}), \
            patch("core.cli_backend.subprocess.Popen", popen), \
            patch.dict("core.cli_backend._PARSERS", {"codex": lambda out, of: (out, 0.0)}), \
            patch("core.cli_backend.time.sleep", lambda s: None):
        return _invoke_once("codex", "pf", "of", None, ".", dict(os.environ), 5)


class LaunchRetryTests(unittest.TestCase):
    def test_a_transient_launch_failure_is_retried_then_succeeds(self):
        calls = {"n": 0}

        def flaky(cmd, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise PermissionError(5, "Access is denied")  # [WinError 5]
            return _FakeProc()

        res = _invoke_codex(flaky)
        self.assertEqual(calls["n"], 2)  # one transient, then success
        self.assertTrue(res.ok)

    def test_a_missing_command_is_not_retried(self):
        calls = {"n": 0}

        def missing(cmd, **kw):
            calls["n"] += 1
            raise FileNotFoundError(2, "No such file or directory")

        res = _invoke_codex(missing)
        self.assertEqual(calls["n"], 1)  # a missing binary is terminal
        self.assertFalse(res.ok)
        self.assertIn("no instalado", res.error)

    def test_a_persistent_transient_failure_exhausts_attempts(self):
        calls = {"n": 0}

        def always_denied(cmd, **kw):
            calls["n"] += 1
            raise PermissionError(5, "Access is denied")

        with patch.dict(os.environ, {"ASTRA_CLI_LAUNCH_ATTEMPTS": "3"}):
            res = _invoke_codex(always_denied)
        self.assertEqual(calls["n"], 3)
        self.assertFalse(res.ok)
        self.assertIn("lanzamiento fallo", res.error)


if __name__ == "__main__":
    unittest.main()
