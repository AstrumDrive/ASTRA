"""SSH transport failures to ASTRUM (outage of 2026-10-07): retried, probed
before any model phase, and never reported as a CODE_ERROR."""
from __future__ import annotations

import json
import os
import subprocess
import unittest
from unittest.mock import AsyncMock, patch

from core.cluster_client import cluster_rpc, execute_cluster_code
from core.remote_executor import probe_remote_transport
from core.remote_transport import is_transport_failure
from tests.cycle_artifacts import remove_cycle_artifacts
from tests.test_input_request_cycle import DECIDED_CODE, _fake, _run

# Verbatim stderr of the 2026-10-07 cycles (Tailscale ProxyCommand).
OUTAGE = "Connection to UNKNOWN port 65535 timed out\r\n"
ENV = {
    "ASTRA_REMOTE_HOST": "astrum",
    "ASTRA_REMOTE_TRANSPORT_BACKOFF": "0",
    "ASTRA_REMOTE_TRANSPORT_RETRIES": "2",
}


def _proc(code, out="", err=""):
    return subprocess.CompletedProcess(args=["ssh"], returncode=code, stdout=out, stderr=err)


class RecogniseTransportFailure(unittest.TestCase):
    def test_the_outage_signature_is_a_transport_failure(self):
        self.assertTrue(is_transport_failure(255, "", OUTAGE))
        self.assertTrue(is_transport_failure(255, "", "kex_exchange_identification: read: Connection reset"))
        self.assertTrue(is_transport_failure(
            255, "", "ssh: connect to host 100.1.2.3 port 22: Connection timed out"))

    def test_a_session_that_started_is_not_retried(self):
        # The remote command may already be running: retrying could duplicate it.
        self.assertFalse(is_transport_failure(255, "", "Connection to astrum closed by remote host."))
        self.assertFalse(is_transport_failure(255, "partial output", OUTAGE))
        self.assertFalse(is_transport_failure(1, "", OUTAGE))
        self.assertFalse(is_transport_failure(None, "", OUTAGE))


class RetryTransport(unittest.IsolatedAsyncioTestCase):
    async def test_a_transient_outage_is_retried_and_the_job_runs(self):
        ok = _proc(0, json.dumps({"job_id": "j1", "result": {"stdout": "VERDICT: PASS", "exit_code": 0}}))
        with patch.dict(os.environ, ENV, clear=False), patch(
            "core.cluster_client.subprocess.run", side_effect=[_proc(255, err=OUTAGE), ok]
        ) as run:
            status = await cluster_rpc({"action": "submit_wait"})
        self.assertEqual(run.call_count, 2)
        self.assertEqual(status["job_id"], "j1")

    async def test_a_lasting_outage_is_marked_and_bounded(self):
        with patch.dict(os.environ, ENV, clear=False), patch(
            "core.cluster_client.subprocess.run", return_value=_proc(255, err=OUTAGE)
        ) as run:
            status = await cluster_rpc({"action": "submit_wait"})
        self.assertEqual(run.call_count, 3)  # first try + 2 retries
        self.assertTrue(status["transport_error"])
        self.assertIn("did not run", status["error"])

    async def test_the_cluster_result_carries_the_transport_flag(self):
        status = {"error": "ASTRUM unreachable", "exit_code": 255, "transport_error": True,
                  "transport_attempts": 3}
        with patch("core.cluster_client.cluster_rpc", new=AsyncMock(return_value=status)):
            result = await execute_cluster_code("print(1)", 30, "python")
        self.assertTrue(result["transport_error"])
        self.assertEqual(result["exit_code"], 255)

    async def test_a_mid_session_drop_is_not_retried(self):
        with patch.dict(os.environ, ENV, clear=False), patch(
            "core.cluster_client.subprocess.run",
            return_value=_proc(255, err="Connection to astrum closed by remote host."),
        ) as run:
            status = await cluster_rpc({"action": "submit_wait"})
        self.assertEqual(run.call_count, 1)
        self.assertNotIn("transport_error", status)

    async def test_probe_reports_reachability(self):
        with patch.dict(os.environ, ENV, clear=False), patch(
            "core.remote_executor.subprocess.run", return_value=_proc(0)
        ):
            self.assertTrue((await probe_remote_transport())["ok"])
        with patch.dict(os.environ, ENV, clear=False), patch(
            "core.remote_executor.subprocess.run", return_value=_proc(255, err=OUTAGE)
        ):
            probe = await probe_remote_transport()
        self.assertFalse(probe["ok"])
        self.assertEqual(probe["attempts"], 3)


class CycleOnOutage(unittest.IsolatedAsyncioTestCase):
    async def test_unreachable_astrum_stops_the_cycle_before_any_model_phase(self):
        fake = _fake(DECIDED_CODE, {"status": "REFUTED", "reasoning": "not reached"})
        probe = AsyncMock(return_value={"ok": False, "attempts": 3, "error": "ASTRUM unreachable"})
        with patch("core.remote_executor.probe_remote_transport", new=probe):
            result = await _run(fake, {"oracle": "astrum"})
        try:
            self.assertEqual(result["status"], "TOOL_ERROR")
            self.assertEqual(result["phase"], "oracle_preflight")
            self.assertTrue(result["transport_error"])
            self.assertEqual(fake.seen["conjectures"], 0)
        finally:
            remove_cycle_artifacts(result)

    async def test_outage_at_execution_is_not_a_code_error_and_skips_repair(self):
        fake = _fake(DECIDED_CODE, {"status": "CODE_ERROR", "reasoning": "not reached"})
        down = {"stdout": "", "stderr": "ASTRUM unreachable over SSH after 3 attempt(s)",
                "exit_code": 255, "engine": "remote", "transport_error": True,
                "transport_attempts": 3}
        execute = AsyncMock(return_value=down)
        with patch.dict(os.environ, {"ASTRA_CODE_REVIEW": "0"}, clear=False), patch(
            "core.executor.execute_python_code", new=execute
        ):
            result = await _run(fake, {"oracle": "local"})
        try:
            self.assertEqual(result["status"], "TOOL_ERROR", result.get("error"))
            self.assertEqual(result["phase"], "execute")
            self.assertTrue(result["transport_error"])
            self.assertEqual(result["code"], DECIDED_CODE)
            self.assertNotIn("analysis_conjectures", fake.seen)
            self.assertEqual(execute.await_count, 1)
        finally:
            remove_cycle_artifacts(result)

    async def test_local_cycles_do_not_probe(self):
        fake = _fake(DECIDED_CODE, {"status": "REFUTED", "reasoning": "sign check failed"})
        probe = AsyncMock(return_value={"ok": False, "attempts": 1, "error": "x"})
        with patch.dict(os.environ, {"ASTRA_CODE_REVIEW": "0"}, clear=False), patch(
            "core.remote_executor.probe_remote_transport", new=probe
        ):
            result = await _run(fake, {"oracle": "local"})
        try:
            probe.assert_not_awaited()
            self.assertEqual(result["status"], "REFUTED", result.get("error"))
        finally:
            remove_cycle_artifacts(result)


if __name__ == "__main__":
    unittest.main()
