"""Config writers of scripts/setup_windows_collaborator.ps1, exercised on temp files."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "setup_windows_collaborator.ps1"


def _powershell() -> str | None:
    return shutil.which("powershell") or shutil.which("pwsh")


@unittest.skipUnless(os.name == "nt" and _powershell(), "needs Windows PowerShell")
class SetupWindowsCollaboratorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def ps(self, body: str) -> subprocess.CompletedProcess:
        command = f". '{SCRIPT}'; {body}"
        result = subprocess.run(
            [_powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_script_parses_without_errors(self):
        result = self.ps(
            "$errors = $null; [System.Management.Automation.Language.Parser]::ParseFile("
            f"'{SCRIPT}', [ref]$null, [ref]$errors) | Out-Null; $errors.Count"
        )
        self.assertEqual(result.stdout.strip(), "0")

    def test_dot_sourcing_does_not_run_the_setup(self):
        result = self.ps("'loaded'")
        self.assertEqual(result.stdout.strip(), "loaded")

    def test_ssh_config_is_created(self):
        config = self.root / "ssh" / "config"
        self.ps(f"Set-AstrumSshConfig -ConfigPath '{config}' -User ivaylo -HostName 100.64.0.9")
        text = config.read_text(encoding="utf-8")
        self.assertIn("Host astrum\n    HostName 100.64.0.9\n    User ivaylo\n", text)
        self.assertIn("StrictHostKeyChecking accept-new", text)
        self.assertNotIn("\r", text)

    def test_ssh_config_replaces_old_astrum_block_and_keeps_other_hosts(self):
        config = self.root / "config"
        config.write_text(
            "Host github.com\n    User git\n\nHost astrum\n    HostName 1.2.3.4\n    User astrum\n"
            "    IdentityFile ~/.ssh/old\n\nHost other\n    HostName example.org\n",
            encoding="utf-8",
        )
        self.ps(f"Set-AstrumSshConfig -ConfigPath '{config}' -User ivaylo -HostName 100.64.0.9")
        text = config.read_text(encoding="utf-8")
        self.assertEqual(text.count("Host astrum"), 1)
        self.assertNotIn("User astrum", text)
        self.assertNotIn("~/.ssh/old", text)
        self.assertIn("Host github.com\n    User git\n", text)
        self.assertIn("Host other\n    HostName example.org\n", text)
        self.assertIn("    User ivaylo\n", text)

    def test_ssh_config_is_idempotent(self):
        config = self.root / "config"
        for _ in range(2):
            self.ps(f"Set-AstrumSshConfig -ConfigPath '{config}' -User ivaylo -HostName 100.64.0.9")
        first = config.read_text(encoding="utf-8")
        self.ps(f"Set-AstrumSshConfig -ConfigPath '{config}' -User ivaylo -HostName 100.64.0.9")
        self.assertEqual(config.read_text(encoding="utf-8"), first)
        self.assertEqual(first.count("Host astrum"), 1)

    def test_env_block_replaces_remote_keys_and_keeps_the_rest(self):
        env = self.root / ".env"
        env.write_text(
            "ASTRA_PROVIDER=codex_cli\nASTRA_REMOTE_SCHEDULER=0\nASTRA_CLIENT_ID=nelson\n"
            "ASTRA_REMOTE_HOST='old'\nOTHER=1\n",
            encoding="utf-8",
        )
        self.ps(f"Set-AstraEnvBlock -EnvPath '{env}' -ClientId ivaylo")
        lines = env.read_text(encoding="utf-8").splitlines()
        self.assertIn("ASTRA_PROVIDER=codex_cli", lines)
        self.assertIn("OTHER=1", lines)
        self.assertIn("ASTRA_REMOTE_SCHEDULER=1", lines)
        self.assertIn("ASTRA_CLIENT_ID=ivaylo", lines)
        self.assertIn("ASTRA_REMOTE_HOST=astrum", lines)
        for key in ("ASTRA_REMOTE_SCHEDULER", "ASTRA_CLIENT_ID", "ASTRA_REMOTE_HOST"):
            self.assertEqual(sum(1 for line in lines if line.startswith(key + "=")), 1, key)

    def test_claude_config_is_created_without_bom(self):
        config = self.root / "Claude" / "claude_desktop_config.json"
        self.ps(
            f"Set-ClaudeDesktopMcp -ConfigPath '{config}' -PythonExe 'C:\\Dev\\ASTRA\\venv\\Scripts\\python.exe' "
            "-ServerScript 'C:\\Dev\\ASTRA\\mcp_server\\server.py'"
        )
        raw = config.read_bytes()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
        data = json.loads(raw.decode("utf-8"))
        self.assertEqual(data["mcpServers"]["astra"]["command"], "C:\\Dev\\ASTRA\\venv\\Scripts\\python.exe")
        self.assertEqual(data["mcpServers"]["astra"]["args"], ["C:\\Dev\\ASTRA\\mcp_server\\server.py"])

    def test_claude_config_merge_keeps_preferences_and_other_servers(self):
        config = self.root / "claude_desktop_config.json"
        original = {
            "mcpServers": {"other": {"command": "x.exe", "args": ["a", "b"]},
                           "astra": {"command": "old.exe", "args": ["old.py"]}},
            "preferences": {"keepAwakeEnabled": True, "list": ["one"], "nested": {"deep": {"k": 1}}},
        }
        config.write_bytes(b"\xef\xbb\xbf" + json.dumps(original).encode("utf-8"))
        self.ps(
            f"Set-ClaudeDesktopMcp -ConfigPath '{config}' -PythonExe 'C:\\new\\python.exe' "
            "-ServerScript 'C:\\new\\server.py'"
        )
        data = json.loads(config.read_text(encoding="utf-8"))
        self.assertEqual(data["mcpServers"]["other"], {"command": "x.exe", "args": ["a", "b"]})
        self.assertEqual(data["mcpServers"]["astra"], {"command": "C:\\new\\python.exe", "args": ["C:\\new\\server.py"]})
        self.assertEqual(data["preferences"]["list"], ["one"])
        self.assertEqual(data["preferences"]["nested"], {"deep": {"k": 1}})
        self.assertTrue(data["preferences"]["keepAwakeEnabled"])
        backups = list(self.root.glob("claude_desktop_config.json.*.bak"))
        self.assertEqual(len(backups), 1)

    def test_find_python312_returns_a_real_312_interpreter(self):
        result = self.ps("Find-Python312")
        path = result.stdout.strip()
        if not path:
            self.skipTest("no Python 3.12 on this machine")
        self.assertNotIn("WindowsApps", path)
        version = subprocess.run([path, "-c", "import sys; print(sys.version_info[:2])"],
                                 capture_output=True, text=True, timeout=60).stdout.strip()
        self.assertEqual(version, "(3, 12)")

    def test_main_refuses_to_run_without_user_and_host(self):
        result = subprocess.run(
            [_powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT)],
            capture_output=True, text=True, timeout=120,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("-AstrumUser NAME -AstrumHost", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
