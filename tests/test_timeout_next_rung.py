"""A timed-out call gets one retry on the next ladder rung (1.1.11, from 2.0)."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from core.cli_backend import CliResult
from core.llm_client import ASTRAIntelligence

TIMEOUT = "'gpt-6.1-sol@ultra': timeout tras 480s (arbol de procesos matado)"


def _agent(models="gpt-6.1-sol@ultra,gpt-6-luna@xhigh", budget=300):
    agent = ASTRAIntelligence(provider="codex_cli", cli_models=models, cli_timeout=480)
    agent.timeout_retry_budget = (lambda: budget) if budget is not None else None
    return agent


class NextRungDecision(unittest.TestCase):
    def test_drops_the_timed_out_rung_and_sizes_the_retry(self):
        agent = _agent()
        self.assertTrue(agent._next_rung_after_timeout(TIMEOUT))
        self.assertEqual(agent.cli_models, "gpt-6-luna@xhigh")
        self.assertEqual(agent.cli_timeout, 300)
        self.assertIn("AVISO TIMEOUT", agent.cli_warnings[-1])

    def test_no_retry_without_budget_rung_or_timeout(self):
        self.assertFalse(_agent(budget=0)._next_rung_after_timeout(TIMEOUT))
        self.assertFalse(_agent(budget=None)._next_rung_after_timeout(TIMEOUT))
        self.assertFalse(_agent(models="gpt-6.1-sol@ultra")._next_rung_after_timeout(TIMEOUT))
        self.assertFalse(_agent()._next_rung_after_timeout("CUOTA AGOTADA"))


class RetryThroughTheCall(unittest.IsolatedAsyncioTestCase):
    async def test_a_timeout_is_answered_by_the_next_rung_once(self):
        agent = _agent()
        calls = []

        def fake_call(kind, prompt, models=None, timeout=None):
            calls.append((models, timeout))
            if len(calls) == 1:
                return CliResult(False, error=TIMEOUT)
            return CliResult(True, text="VERDICT", model_used="gpt-6-luna@xhigh")

        with patch("core.cli_backend.call_cli", side_effect=fake_call):
            out = await agent._call_api("system", "user")
        self.assertEqual(out, "VERDICT")
        self.assertEqual(calls, [("gpt-6.1-sol@ultra,gpt-6-luna@xhigh", 480), ("gpt-6-luna@xhigh", 300)])

    async def test_a_second_timeout_is_not_retried_again(self):
        agent = _agent()
        with patch("core.cli_backend.call_cli", return_value=CliResult(False, error=TIMEOUT)) as call:
            out = await agent._call_api("system", "user")
        self.assertTrue(out.startswith("API_ERROR:"))
        self.assertEqual(call.call_count, 2)


if __name__ == "__main__":
    unittest.main()
