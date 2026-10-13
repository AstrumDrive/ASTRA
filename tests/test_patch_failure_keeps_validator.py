"""A failed repair patch keeps the validator that already ran (1.1.11, from 2.0 1a99f89)."""
import unittest
from unittest.mock import patch

from astra_tool import _do_cycle
from tests.cycle_artifacts import remove_cycle_artifacts
from tests.test_input_request_cycle import GOAL, PROVIDERS, RAW, _fake

# Prints PASS with no check that could fail: the deterministic audit flags it,
# so a VALIDATED analysis is downgraded to WEAK_PASS and a repair is requested.
WEAK_CODE = "print('VERDICT: PASS')\n"


class PatchFailureKeepsValidator(unittest.IsolatedAsyncioTestCase):
    async def test_malformed_patch_on_weak_pass_finalizes_weak_pass(self):
        fake = _fake(WEAK_CODE, {"status": "VALIDATED", "reasoning": "looks fine"})

        async def bad_patch(self, *args, **kwargs):
            fake.seen["patches"] = fake.seen.get("patches", 0) + 1
            return {"status": "REJECTED", "reason": "malformed JSON in patch reply"}

        fake.repair_validation_code = bad_patch
        env = {
            "ASTRA_CYCLE_CACHE": "0",
            "ASTRA_CONJECTURE_PROVIDER": "codex_cli",
            "ASTRA_VALIDATOR_REPAIR_VNEXT": "1",
            "ASTRA_VALIDATOR_REPAIR_STRATEGY": "local-patch",
            "ASTRA_NAVIGATE_AFTER_CYCLE": "0",
            "ASTRA_MAX_RETRIES": "1",
            "ASTRA_ORACLE_MODE": "local",
            "ASTRA_CODE_REVIEW": "0",
        }
        with patch.dict("os.environ", env, clear=False), patch(
            "core.preflight.phase_provider_map", return_value=PROVIDERS
        ), patch("core.llm_client.ASTRAIntelligence", fake):
            result = await _do_cycle({"action": "cycle", "intuition": RAW, "objective": GOAL,
                                      "cycle_timeout_seconds": 1500})
        try:
            self.assertEqual(fake.seen.get("patches"), 1)
            self.assertEqual(result.get("status"), "WEAK_PASS", result.get("error"))
            self.assertNotEqual(result.get("status"), "TOOL_ERROR")
        finally:
            remove_cycle_artifacts(result)


if __name__ == "__main__":
    unittest.main()
