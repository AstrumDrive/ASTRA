"""Codex runs without agent tools when ASTRA_CODEX_LEAN=1 (1.1.17)."""
import os
import unittest
from unittest.mock import patch

from core import cli_backend as cb


class CodexLean(unittest.TestCase):
    def test_off_by_default(self):
        with patch.dict(os.environ, {"ASTRA_CODEX_LEAN": "0"}, clear=False):
            self.assertEqual(cb.codex_lean_overrides(), ())
            self.assertNotIn("shell_tool", cb._ps_codex("p.txt", "gpt-6-luna@xhigh", "o.txt", "ws"))

    def test_windows_command_carries_every_override(self):
        with patch.dict(os.environ, {"ASTRA_CODEX_LEAN": "1"}, clear=False):
            cmd = cb._ps_codex("p.txt", "gpt-6-luna@xhigh", "o.txt", "ws")
        self.assertIn("-c 'features.shell_tool=false'", cmd)
        self.assertIn("-c 'web_search=\\\"disabled\\\"'", cmd)
        self.assertIn("model_reasoning_effort", cmd)
        self.assertEqual(cmd.count(" -c '"), 1 + len(cb.CODEX_LEAN_OVERRIDES))

    def test_posix_argv_carries_every_override(self):
        with patch.dict(os.environ, {"ASTRA_CODEX_LEAN": "'1'"}, clear=False), \
                patch.object(cb.os, "name", "posix"):
            spec = cb._codex_builder("p.txt", "gpt-6-luna@xhigh", "o.txt", "ws")
        argv = spec["argv"]
        for override in cb.CODEX_LEAN_OVERRIDES:
            self.assertIn(override, argv)
        self.assertEqual(argv[-1], "-")


if __name__ == "__main__":
    unittest.main()
