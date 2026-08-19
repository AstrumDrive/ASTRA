import os
import tempfile
import unittest
from unittest.mock import patch

from core.cli_backend import _agy_argv, _claude_argv, _codex_builder, _invoke_once, _kill_tree


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


class CliBackendTests(unittest.TestCase):
    def test_claude_text_phases_disable_all_builtin_tools(self):
        command = _claude_argv("prompt.txt", "claude-opus-4-8", "", "")
        argv = command["argv"]
        tools_index = argv.index("--tools")
        self.assertEqual(argv[tools_index + 1], "")
        self.assertNotIn("--disallowed-tools", argv)
        self.assertIn("--strict-mcp-config", argv)

    def test_agy_uses_maximum_supported_effort_by_default(self):
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            encoding="utf-8",
            delete=False,
        ) as handle:
            handle.write("test prompt")
            prompt_path = handle.name
        try:
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("ASTRA_AGY_EFFORT", None)
                argv = _agy_argv(
                    prompt_path,
                    "gemini-3.1-pro-high",
                    "",
                    "",
                )
            effort_index = argv.index("--effort")
            self.assertEqual(argv[effort_index + 1], "high")
            self.assertIn("gemini-3.1-pro-high", argv)
        finally:
            os.remove(prompt_path)

    def test_codex_uses_native_stdin_invocation_on_macos(self):
        with patch("core.cli_backend.os.name", "posix"), patch(
            "core.cli_backend.shutil.which",
            return_value="/opt/homebrew/bin/codex",
        ), patch.dict(
            os.environ,
            {"ASTRA_CODEX_REASONING": "xhigh"},
            clear=False,
        ):
            command = _codex_builder(
                "/tmp/prompt.txt",
                "gpt-5.6-sol",
                "/tmp/output.txt",
                "/tmp/astra/workspace",
            )
        self.assertEqual(command["stdin_file"], "/tmp/prompt.txt")
        self.assertEqual(command["argv"][0], "/opt/homebrew/bin/codex")
        self.assertNotIn("powershell", command["argv"])
        self.assertIn('model_reasoning_effort="xhigh"', command["argv"])
        self.assertEqual(command["argv"][-1], "-")

    def test_posix_timeout_kills_the_process_group(self):
        with patch("core.cli_backend.os.name", "posix"), patch(
            "core.cli_backend.os.getpgid",
            return_value=4321,
            create=True,
        ), patch("core.cli_backend.os.killpg", create=True) as killpg:
            with patch("core.cli_backend.signal.SIGKILL", 9, create=True):
                _kill_tree(1234)
        killpg.assert_called_once()
        self.assertEqual(killpg.call_args.args[0], 4321)


if __name__ == "__main__":
    unittest.main()
