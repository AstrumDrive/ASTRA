"""`# ASTRA_ENGINE: blender`: headless Blender 4.2 LTS on ASTRUM (renders and
animations through the job queue, 13 October 2026). Blender exists only on
ASTRUM, so it routes like the other managed engines (sci, pkgs)."""
from __future__ import annotations

import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from core.engine_router import detect_engine as client_detect
from core.executor import execute_python_code
from core.remote_executor import execute_remote_engine
from remote.astra_cluster_manager import _default_cpu, _detect_engine as queue_detect
from remote.astra_remote_worker import command_for, detect_engine as worker_detect

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = "# ASTRA_ENGINE: blender\nimport bpy\nprint(bpy.app.version_string)\n"


class Detection(unittest.TestCase):
    def test_every_layer_recognizes_the_marker(self):
        self.assertEqual(client_detect(SCRIPT), "blender")
        self.assertEqual(worker_detect(SCRIPT), "blender")
        self.assertEqual(queue_detect(SCRIPT), "blender")
        self.assertEqual(_default_cpu("blender"), 4)

    def test_the_worker_uses_the_central_runner(self):
        with tempfile.TemporaryDirectory() as temporary:
            runner = Path(temporary) / "astra_engine.sh"
            runner.write_text("#!/bin/sh\n", encoding="utf-8")
            os.chmod(runner, 0o700)
            with patch.dict(os.environ, {"ASTRA_REMOTE_ENGINE_RUNNER": str(runner)}, clear=False):
                command = command_for("blender", str(Path(temporary) / "render.py"))
        self.assertEqual(command[:2], [str(runner), "blender"])


class Runner(unittest.TestCase):
    def test_the_engine_script_runs_blender_headless_and_strict(self):
        text = (ROOT / "remote" / "astra_engine.sh").read_text(encoding="utf-8")
        self.assertIn('[blender]="$H/opt/blender-4.2.23-linux-x64/blender"', text)
        self.assertRegex(text, r"for k in [^;\n]*\bblender\b")          # listed by `list`
        self.assertIn('-b --factory-startup --python-exit-code 1 --python "$SCRIPT" -- "$@"', text)


class Routing(unittest.IsolatedAsyncioTestCase):
    async def test_local_oracle_refuses_it(self):
        with patch.dict(os.environ, {"ASTRA_ORACLE_MODE": "local"}, clear=False):
            result = await execute_python_code(SCRIPT, timeout=30)
        self.assertEqual(result["exit_code"], -2)
        self.assertIn("ASTRUM-managed", result["stderr"])

    async def test_remote_oracle_goes_through_the_registry(self):
        response = {"stdout": "4.2.23\n", "stderr": "", "exit_code": 0, "engine": "python"}
        with patch("core.remote_executor.execute_remote_code",
                   new=AsyncMock(return_value=response)) as remote:
            result = await execute_remote_engine(SCRIPT, "blender", timeout=90)
        wrapper = remote.await_args.args[0]
        self.assertIn("'blender'", wrapper)
        self.assertEqual(result["engine"], "blender")

    async def test_certified_preludes_stay_on_the_python_engine(self):
        code = "# ASTRA_ENGINE: blender\n# ASTRA_CERTIFIED: verdict\nimport bpy\n"
        with patch.dict(os.environ, {"ASTRA_ORACLE_MODE": "remote"}, clear=False):
            result = await execute_python_code(code, timeout=30)
        self.assertEqual(result["exit_code"], -2)
        self.assertTrue(re.search(r"Python engine only", result["stderr"]))


if __name__ == "__main__":
    unittest.main()
