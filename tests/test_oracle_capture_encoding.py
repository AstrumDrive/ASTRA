"""Lean/CAS oracle captures must decode UTF-8, not the Windows locale.

Hardening for MCP production (which sets PYTHONIOENCODING but not PYTHONUTF8):
core/engine_router.py (CAS), core/formal_validators.py (Lean) and
core/remote_executor.py (remote transport) now pass encoding="utf-8",
errors="replace" to every Windows-side capture, so a non-ASCII maths/proof
output never becomes a lone surrogate that crashes a later prompt encode.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _has_surrogate(s):
    return isinstance(s, str) and any(0xD800 <= ord(c) <= 0xDFFF for c in s)


# UTF-8 bytes for U+0081 (C2 81) and U+009D (C2 9D) -- the cp1252-undefined bytes
# -- plus U+0394 (Greek delta, E2 96 94-ish) standing in for a maths symbol.
_EMIT = (
    "import sys; "
    "sys.stdout.buffer.write("
    "('cas ' + chr(0x81) + chr(0x9d) + ' \\u0394 ok').encode('utf-8'))"
)


class CASCaptureEncoding(unittest.TestCase):
    def test_run_decodes_engine_output_as_utf8(self):
        from core.engine_router import _run

        res = _run([sys.executable, "-c", _EMIT], timeout=30)
        out = res["stdout"]
        self.assertFalse(_has_surrogate(out), "CAS stdout carries a surrogate")
        out.encode("utf-8")  # must not raise (the pilot crash signature)
        self.assertIn("Δ", out)
        self.assertEqual(res["exit_code"], 0)

    def test_execute_external_cas_no_surrogates(self):
        from core import engine_router

        # Route the "sage" engine to a Python emitter so the real capture path
        # (execute_external_cas -> _run) runs without needing sage installed.
        with tempfile.TemporaryDirectory() as work:
            with patch.object(
                engine_router,
                "_command_for",
                return_value=[sys.executable, "-c", _EMIT],
            ):
                res = engine_router.execute_external_cas(
                    "print('x')", "sage", work, 30
                )
        self.assertFalse(_has_surrogate(res["stdout"]))
        res["stdout"].encode("utf-8")
        self.assertEqual(res["engine"], "sage")


class LeanCaptureEncoding(unittest.TestCase):
    def test_local_lean_capture_requests_utf8(self):
        # Guard: the native local Lean evaluator must pass encoding/errors to
        # subprocess.run. Lean is not installed in the test env, so mock the
        # subprocess and give a real temp dir as the pinned project.
        from core import formal_validators as fv

        calls = []

        class _Result:
            returncode = 0
            stdout = "compiled"
            stderr = ""

        def _recorder(*args, **kwargs):
            calls.append(kwargs)
            return _Result()

        with tempfile.TemporaryDirectory() as proj:
            env = {"ASTRA_LOCAL_LEAN4_ROOT": proj}
            with patch.dict(os.environ, env, clear=False):
                for key in (
                    "ASTRA_LOCAL_LEAN4_WSL_ROOT",
                    "ASTRA_LOCAL_LEAN4_WSL_LAKE_BIN",
                    "ASTRA_LOCAL_LAKE_BIN",
                ):
                    os.environ.pop(key, None)
                with patch("core.formal_validators.shutil.which", return_value="lake"), \
                     patch("core.formal_validators.subprocess.run", _recorder):
                    fv._evaluate_lean4_local("theorem t : 1 = 1 := rfl", 30)

        self.assertTrue(calls, "subprocess.run was never called")
        self.assertEqual(calls[0].get("encoding"), "utf-8")
        self.assertEqual(calls[0].get("errors"), "replace")


class RemoteCaptureEncoding(unittest.IsolatedAsyncioTestCase):
    """Both remote transports must decode the reply as UTF-8. cluster_enabled()
    is forced per test so which branch runs never depends on the ambient
    ASTRA_REMOTE_SCHEDULER (that non-determinism is exactly what an audit flagged).
    """

    class _Result:
        returncode = 0
        stdout = '{"exit_code": 0, "stdout": "", "stderr": "", "engine": "remote"}'
        stderr = ""

    async def _capture(self, *, cluster: bool, subprocess_target: str):
        from core import remote_executor as re

        calls = []

        def _recorder(*args, **kwargs):
            calls.append(kwargs)
            return self._Result()

        env = {"ASTRA_REMOTE_HOST": "astrum"}
        with patch.dict(os.environ, env, clear=False):
            with patch("core.cluster_client.cluster_enabled", return_value=cluster), \
                 patch(subprocess_target, _recorder):
                await re.execute_remote_code("print('x')", timeout=30)
        return calls

    async def test_direct_ssh_capture_requests_utf8(self):
        calls = await self._capture(
            cluster=False, subprocess_target="core.remote_executor.subprocess.run"
        )
        self.assertTrue(calls, "remote_executor._run_remote never ran")
        for kwargs in calls:
            self.assertEqual(kwargs.get("encoding"), "utf-8", kwargs)
            self.assertEqual(kwargs.get("errors"), "replace", kwargs)

    async def test_cluster_rpc_capture_requests_utf8(self):
        calls = await self._capture(
            cluster=True, subprocess_target="core.cluster_client.subprocess.run"
        )
        self.assertTrue(calls, "cluster_client._run never ran")
        for kwargs in calls:
            self.assertEqual(kwargs.get("encoding"), "utf-8", kwargs)
            self.assertEqual(kwargs.get("errors"), "replace", kwargs)


class SciCodeCaptureEncoding(unittest.TestCase):
    """The SciCode evaluator runs a Windows-Python harness child, so it needs
    BOTH a UTF-8 child env (to emit UTF-8) and a UTF-8-decoded capture."""

    def test_scicode_capture_requests_utf8_and_child_env(self):
        from core import external_evaluators as ee
        from core.external_benchmarks import ExternalCase

        calls = []

        class _Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        def _recorder(*args, **kwargs):
            calls.append(kwargs)
            return _Result()

        case = ExternalCase(
            benchmark="scicode",
            id="scicode_1_1",
            split="test",
            domain="science",
            task_type="code",
            evaluator="scicode_h5_tests",
            prompt="x",
            metadata={
                "step_number": "1.1",
                "test_cases": [],
                "required_dependencies": "",
            },
        )
        with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as h5:
            h5_path = Path(h5.name)
        try:
            with patch("core.external_evaluators.subprocess.run", _recorder):
                ee.evaluate_scicode_code(
                    case, "def f():\n    return 1\n", h5_path=h5_path
                )
        finally:
            h5_path.unlink(missing_ok=True)

        self.assertTrue(calls, "the SciCode harness subprocess never ran")
        self.assertEqual(calls[0].get("encoding"), "utf-8")
        self.assertEqual(calls[0].get("errors"), "replace")
        self.assertEqual((calls[0].get("env") or {}).get("PYTHONUTF8"), "1")


if __name__ == "__main__":
    unittest.main()
