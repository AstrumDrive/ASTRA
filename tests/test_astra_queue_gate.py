"""The ForceCommand gate reaches only the job manager (docs/ASTRUM_ACCESO_POR_USUARIO.md)."""

import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest

GATE = Path(__file__).resolve().parents[1] / "remote" / "astra_queue_gate.sh"
REFUSAL = "only reaches the ASTRA job manager"


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "needs a POSIX bash")
class QueueGateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.bin = Path(self.temporary.name)
        stub = self.bin / "sudo"
        stub.write_text('#!/bin/bash\nprintf "SUDO %s STDIN %s\\n" "$*" "$(cat)"\n', encoding="utf-8")
        logger = self.bin / "logger"
        logger.write_text("#!/bin/bash\ntrue\n", encoding="utf-8")
        for path in (stub, logger):
            path.chmod(path.stat().st_mode | stat.S_IXUSR)
        self.gate = self.bin / "gate"
        self.gate.write_text(
            GATE.read_text(encoding="utf-8").replace("/usr/bin/sudo", str(stub)),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temporary.cleanup()

    def run_gate(self, request, stdin='{"action":"capacity"}'):
        env = dict(os.environ, SSH_ORIGINAL_COMMAND=request, PATH=f"{self.bin}:{os.environ['PATH']}")
        return subprocess.run(
            ["bash", str(self.gate)], input=stdin, capture_output=True, text=True, env=env, timeout=30
        )

    def test_astra_rpc_command_is_forwarded_with_its_stdin(self):
        for request in (
            "~/astra-worker/venv/bin/python ~/astra-worker/astra_cluster_manager.py rpc",
            "'/opt/py' '~/astra-worker/astra_cluster_manager.py' rpc",
        ):
            result = self.run_gate(request)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("SUDO -n -u astrum /usr/local/sbin/astra-queue-rpc", result.stdout)
            self.assertIn('STDIN {"action":"capacity"}', result.stdout)

    def test_info_sends_the_info_action(self):
        result = self.run_gate("info", stdin="")
        self.assertEqual(result.returncode, 0)
        self.assertIn('STDIN {"action":"info"}', result.stdout)

    def test_everything_else_is_refused_without_reaching_sudo(self):
        for request in (
            "",
            "bash -i",
            "~/astra-worker/astra_cluster_manager.py rpc; rm -rf ~",
            "python ~/astra-worker/astra_remote_worker.py",
            "hostname; ~/astra-worker/astra_engine.sh list",
            "scp -t /tmp",
            "internal-sftp",
            "xastra_cluster_manager.py rpc",
        ):
            result = self.run_gate(request)
            self.assertEqual(result.returncode, 2, request)
            self.assertIn(REFUSAL, result.stdout)
            self.assertNotIn("SUDO", result.stdout)


if __name__ == "__main__":
    unittest.main()
