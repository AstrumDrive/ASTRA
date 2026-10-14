"""Tokens per call, per agent and per role (1.1.16)."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from astra_tool import _cli_usage
from core.cli_backend import CliResult, usage_from
from core.llm_client import ASTRAIntelligence

CODEX_OUT = "\n".join([
    '{"type":"thread.started","thread_id":"x"}',
    '{"type":"item.completed","item":{"type":"agent_message","text":"OK"}}',
    '{"type":"turn.completed","usage":{"input_tokens":13830,"cached_input_tokens":11008,'
    '"cache_write_input_tokens":0,"output_tokens":5,"reasoning_output_tokens":2}}',
])
CLAUDE_OUT = json.dumps({"result": "OK", "total_cost_usd": 0.13, "usage": {
    "input_tokens": 2, "cache_read_input_tokens": 26217, "cache_creation_input_tokens": 16331,
    "output_tokens": 4}})


class UsageFrom(unittest.TestCase):
    def test_codex_turn_completed(self):
        self.assertEqual(usage_from("codex", CODEX_OUT),
                         {"input": 13830, "cached": 11008, "output": 5, "reasoning": 2})

    def test_claude_json_counts_cache_as_input(self):
        self.assertEqual(usage_from("claude", CLAUDE_OUT),
                         {"input": 2 + 26217 + 16331, "cached": 26217, "output": 4, "reasoning": 0})

    def test_nothing_to_read(self):
        self.assertEqual(usage_from("agy", "OK"), {})
        self.assertEqual(usage_from("codex", "not json"), {})


class AgentAndRoleTotals(unittest.IsolatedAsyncioTestCase):
    async def test_agent_accumulates_every_answered_call(self):
        agent = ASTRAIntelligence(provider="codex_cli", cli_models="gpt-6-luna", cli_timeout=60)
        res = CliResult(True, text="OK", usage={"input": 100, "cached": 40, "output": 7, "reasoning": 3})
        with patch("core.cli_backend.call_cli", return_value=res):
            await agent._call_api("s", "u")
            await agent._call_api("s", "u")
        self.assertEqual(agent.cli_usage, {"calls": 2, "input": 200, "cached": 80, "output": 14, "reasoning": 6})

    def test_roles_are_summed_and_totalled(self):
        a = SimpleNamespace(cli_usage={"calls": 1, "input": 10, "cached": 0, "output": 1, "reasoning": 0})
        b = SimpleNamespace(cli_usage={"calls": 2, "input": 30, "cached": 5, "output": 2, "reasoning": 1})
        silent = SimpleNamespace(cli_usage={"calls": 0, "input": 0, "cached": 0, "output": 0, "reasoning": 0})
        out = _cli_usage([("reviewer", a), ("reviewer", b), ("navigator", silent)])
        self.assertEqual(out["reviewer"]["calls"], 3)
        self.assertEqual(out["total"]["input"], 40)
        self.assertNotIn("navigator", out)


if __name__ == "__main__":
    unittest.main()
