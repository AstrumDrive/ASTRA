import subprocess
import tempfile
import unittest
from unittest.mock import patch, AsyncMock

from astra_tool import _do_cycle, _apply_guard
from core.executor import execute_python_code
from core.timeout_recovery import output_text, recovery_instructions
from remote.astra_remote_worker import run_code
from tests.test_input_request_cycle import _fake, PROVIDERS
from tests.cycle_artifacts import remove_cycle_artifacts


class TimeoutRecoveryTests(unittest.IsolatedAsyncioTestCase):
    def test_timeout_cannot_be_reported_as_supported_or_refuted(self):
        for status in ("VALIDATED", "REFUTED"):
            result = _apply_guard({"status": status}, {"exit_code": 124})
            self.assertEqual(result["status"], "CODE_ERROR")
            self.assertEqual(result["original_claim_verdict"], "INCONCLUSIVE")
        self.assertEqual(output_text(b"PROGRESS step1"), "PROGRESS step1")
        self.assertIn("Change the blocked computational strategy", recovery_instructions({"exit_code":124},100))

    async def test_local_timeout_retains_partial_output(self):
        with tempfile.TemporaryDirectory() as work, patch.dict("os.environ", {"ASTRA_ORACLE_MODE":"local"}), patch(
            "core.executor.subprocess.run",
            side_effect=subprocess.TimeoutExpired("python",100,output=b"PROGRESS step1\n",stderr=b"warning"),
        ):
            result = await execute_python_code("print('test')",workspace_dir=work,timeout=100)
        self.assertEqual(result["exit_code"],124)
        self.assertIn("PROGRESS step1",result["stdout"])
        self.assertIn("warning",result["stderr"])

    def test_remote_worker_timeout_retains_partial_output(self):
        with tempfile.TemporaryDirectory() as work, patch(
            "remote.astra_remote_worker.command_for",return_value=["python","test.py"]
        ),patch("remote.astra_remote_worker.subprocess.run",side_effect=subprocess.TimeoutExpired(
            "python",100,output=b"PROGRESS remote_step\n",stderr=b"warning"
        )):
            result=run_code("print('test')",work,100)
        self.assertEqual(result["exit_code"],124)
        self.assertIn("PROGRESS remote_step",result["stdout"])

    async def test_three_attempt_limit_and_unchanged_strategy_stop(self):
        for change,expected in ((True,3),(False,1)):
            base=_fake("",{"status":"VALIDATED","reasoning":"Deliberately wrong timeout verdict"})
            class Fake(base):
                count=0
                async def translate_to_code(self,*args,**kwargs):
                    Fake.count+=1
                    return "print('CHECK test: OK')\nprint('VERDICT: PASS')\n# strategy "+str(Fake.count if change else 0)
            execute=AsyncMock(return_value={"stdout":"PROGRESS entered_stage\n","stderr":"TimeoutError","exit_code":124})
            env={"ASTRA_CYCLE_CACHE":"0","ASTRA_CODE_REVIEW":"1","ASTRA_CONJECTURE_PROVIDER":"codex_cli",
                 "ASTRA_VALIDATOR_REPAIR_VNEXT":"0","ASTRA_NAVIGATE_AFTER_CYCLE":"0","ASTRA_MAX_RETRIES":"9"}
            with patch.dict("os.environ",env),patch("core.preflight.phase_provider_map",return_value=PROVIDERS),patch(
                "core.llm_client.ASTRAIntelligence",Fake
            ),patch("core.executor.execute_python_code",execute):
                result=await _do_cycle({"intuition":"Single explicit claim for test.","exec_timeout":100,"cycle_timeout_seconds":1500})
            try:
                self.assertEqual(execute.await_count,expected,result.get("error"))
                self.assertTrue(all(c.kwargs["timeout"]<=100 for c in execute.await_args_list))
                self.assertEqual(len(result["execution_history"]),expected)
                self.assertEqual(result["original_claim_verdict"],"INCONCLUSIVE")
            finally:
                remove_cycle_artifacts(result)
