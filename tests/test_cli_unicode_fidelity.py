"""Non-ASCII prompt fidelity through the Windows PowerShell CLI pipeline.

Measured 2026-08-12: Windows PowerShell 5.1 pipes to native executables using
``$OutputEncoding``, which defaults to us-ascii, and ``Get-Content`` without
``-Encoding`` reads a BOM-less file as ANSI.  A Lean validator's ``forall``
binder reached Codex as ``???`` (one ``?`` per UTF-8 byte) and the reviewer
correctly rejected the corrupted source, costing the cycle.  Spanish accents
in the consensus conjectures degraded the same way.

The integration test drives the real ``powershell.exe`` when it exists, so it
proves the fix on the interpreter ASTRA actually spawns rather than on the
PowerShell 7 that a developer shell may provide.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from core.cli_backend import _PS_UTF8_PREAMBLE, _codex_builder, _ps_codex

UNICODE_PROMPT = "forall: \u2200 nat: \u2115 real: \u211d accent: ra\u00edz"


class BuilderContractTests(unittest.TestCase):
    def test_codex_command_declares_utf8_before_reading(self):
        command = _ps_codex("C:/tmp/prompt.txt", None, "C:/tmp/out.json", "C:/ws")
        self.assertTrue(command.startswith(_PS_UTF8_PREAMBLE))
        self.assertIn("Get-Content -Raw -Encoding UTF8", command)
        # The encoding must be set before the pipe, not after it.
        self.assertLess(
            command.index("OutputEncoding"), command.index("Get-Content")
        )

    def test_utf8_encoding_is_created_without_a_bom(self):
        self.assertIn("UTF8Encoding $false", _PS_UTF8_PREAMBLE)

    def test_posix_route_bypasses_powershell_entirely(self):
        if os.name == "nt":
            self.skipTest("POSIX builder path is not selected on Windows")
        built = _codex_builder("/tmp/prompt.txt", None, "/tmp/out.json", "/ws")
        self.assertIsInstance(built, dict)
        self.assertIn("stdin_file", built)


@unittest.skipUnless(os.name == "nt", "Windows PowerShell pipeline only")
class PowerShellPipelineTests(unittest.TestCase):
    """Drive powershell.exe for real: the bug is interpreter-specific."""

    @classmethod
    def setUpClass(cls):
        cls.powershell = shutil.which("powershell.exe") or shutil.which(
            "powershell"
        )
        if not cls.powershell:
            raise unittest.SkipTest("powershell.exe not available")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        # Exactly how ASTRA writes a prompt file: UTF-8, no BOM.
        self.prompt = self.tmp / "prompt.txt"
        self.prompt.write_text(UNICODE_PROMPT, encoding="utf-8")
        self.receiver = self.tmp / "recv.py"
        self.receiver.write_text(
            "import sys\n"
            "sys.stdout.buffer.write(sys.stdin.buffer.read())\n",
            encoding="ascii",
        )

    def run_pipeline(self, prefix: str, read_flags: str) -> str:
        command = (
            f"{prefix}Get-Content -Raw {read_flags}-LiteralPath "
            f"'{self.prompt}' | & '{sys.executable}' '{self.receiver}'"
        )
        completed = subprocess.run(
            [self.powershell, "-NoProfile", "-NonInteractive", "-Command",
             command],
            capture_output=True,
            timeout=120,
        )
        return completed.stdout.decode("utf-8", errors="replace")

    def test_unfixed_pipeline_destroys_non_ascii(self):
        # Documents the defect; if this ever stops failing the guard below is
        # no longer load-bearing and the workaround can be revisited.
        received = self.run_pipeline("", "")
        if "\u2200" in received:
            self.skipTest(
                "this PowerShell already pipes UTF-8; the fix is a no-op here"
            )
        self.assertIn("?", received)

    def test_fixed_pipeline_preserves_every_character(self):
        received = self.run_pipeline(_PS_UTF8_PREAMBLE, "-Encoding UTF8 ")
        for character in ("\u2200", "\u2115", "\u211d", "\u00ed"):
            with self.subTest(character=character):
                self.assertIn(character, received)
        self.assertNotIn("???", received)


if __name__ == "__main__":
    unittest.main()
