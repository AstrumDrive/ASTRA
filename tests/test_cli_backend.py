import os
import tempfile
import unittest
from unittest.mock import patch

from core.cli_backend import (
    _agy_argv,
    _claude_argv,
    _codex_builder,
    _is_quota_error,
    _kill_tree,
    _model_ladder,
)


class CliBackendTests(unittest.TestCase):
    def test_current_claude_quota_wordings_are_classified_as_quota(self):
        """The ladder only descends when the failure is classified as quota.

        "hit your weekly limit" is what Claude Code prints today; it used to
        fall through as a generic error, so the ladder broke at the first rung
        and never tried the next model (cycle_20260819_231945_f371).
        """
        for message in (
            "You've hit your weekly limit · resets 5am (America/Buenos_Aires)",
            "You've hit your usage limit",
            "You have reached your usage limit for this plan",
            "5-hour limit reached",
            "rate limit exceeded",
            "429 Too Many Requests",
        ):
            with self.subTest(message=message):
                self.assertTrue(_is_quota_error(message))

    def test_real_failures_are_not_mistaken_for_quota(self):
        for message in (
            "exit 1: ModuleNotFoundError: No module named 'sympy'",
            "parseo fallo: JSONDecodeError: Expecting value",
            "perfil de cuenta claude invalido: home inexistente",
        ):
            with self.subTest(message=message):
                self.assertFalse(_is_quota_error(message))

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

    def test_agy_model_ladder_preserves_new_flash_fallback_order(self):
        ladder = _model_ladder(
            "agy",
            None,
            "gemini-3.1-pro-high,gemini-3.7-flash-high,gemini-3.5-flash-high",
        )
        self.assertEqual(
            ladder,
            [
                "gemini-3.1-pro-high",
                "gemini-3.7-flash-high",
                "gemini-3.5-flash-high",
            ],
        )

    def test_agy_forwards_gemini_37_alias_without_rewriting(self):
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            encoding="utf-8",
            delete=False,
        ) as handle:
            handle.write("test prompt")
            prompt_path = handle.name
        try:
            argv = _agy_argv(prompt_path, "gemini-3.7-flash-high", "", "")
            model_index = argv.index("--model")
            self.assertEqual(argv[model_index + 1], "gemini-3.7-flash-high")
        finally:
            os.remove(prompt_path)

    def test_codex_uses_native_stdin_invocation_on_macos(self):
        with patch("core.cli_backend.os.name", "posix"), patch(
            "core.cli_backend.shutil.which",
            return_value="/opt/homebrew/bin/codex",
        ), patch.dict(
            os.environ,
            {"ASTRA_CODEX_REASONING": "xhigh", "ASTRA_CODEX_BIN": ""},
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
