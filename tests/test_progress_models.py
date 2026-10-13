"""The progress window shows the model and effort of every stage (1.1.15)."""
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from astra_tool import agent_models, rung_label  # noqa: E402
from astra_progress import models_lines  # noqa: E402


class RungLabel(unittest.TestCase):
    def test_rung_effort_wins_and_cli_wide_effort_fills_in(self):
        env = {"ASTRA_CODEX_MODELS": "gpt-6.1-sol@ultra,gpt-6-luna@xhigh",
               "ASTRA_CLAUDE_MODELS": "claude-opus-5-5,sonnet",
               "ASTRA_AGY_EFFORT": "high"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("ASTRA_CLAUDE_EFFORT", None)
            self.assertEqual(rung_label("codex"), "gpt-6.1-sol@ultra")
            self.assertEqual(rung_label("codex", "gpt-6.1-sol@max,gpt-6-luna"), "gpt-6.1-sol@max")
            self.assertEqual(rung_label("claude"), "claude-opus-5-5@default")
            self.assertEqual(rung_label("agy", "gemini-3.8-flash"), "gemini-3.8-flash@high")

    def test_agent_record_carries_the_model_that_answered(self):
        agent = SimpleNamespace(cli_kind="codex", cli_models="gpt-6.1-sol@ultra,gpt-6-luna@xhigh",
                                cli_last_model="gpt-6-luna@xhigh")
        rec = agent_models(agent)
        self.assertEqual(rec, {"cli": "codex", "planned": "gpt-6.1-sol@ultra", "used": "gpt-6-luna@xhigh"})
        self.assertIsNone(agent_models(SimpleNamespace(cli_kind=None)))


class WindowLines(unittest.TestCase):
    MODELS = {
        "conjecture": {"cli": "codex+agy", "planned": "codex gpt-6.1-sol@ultra + agy gemini-3.8-flash@high"},
        "translator": {"cli": "claude", "planned": "claude-opus-5-5@high"},
        "reviewer": {"cli": "codex", "planned": "gpt-6.1-sol@max", "used": "gpt-6-luna@xhigh"},
        "analyst": {"cli": "codex", "planned": "gpt-6.1-sol@ultra", "used": "gpt-6.1-sol@ultra"},
    }

    def test_one_line_per_stage_with_current_and_fallback_marks(self):
        lines = models_lines(self.MODELS, current_phase="translate")
        text = "\n".join(lines)
        self.assertEqual(lines[0], "Models    :")
        self.assertIn("translate  claude     claude-opus-5-5@high  <- now", text)
        self.assertIn("-> answered by gpt-6-luna@xhigh (fallback)", text)
        analyze = [l for l in lines if l.strip().startswith("analyze")][0]
        self.assertNotIn("fallback", analyze)
        self.assertTrue(all(l.isascii() for l in lines))

    def test_nothing_when_the_heartbeat_has_no_models(self):
        self.assertEqual(models_lines({}), [])


if __name__ == "__main__":
    unittest.main()


class HeartbeatCarriesModels(unittest.IsolatedAsyncioTestCase):
    async def test_a_cycle_writes_models_into_its_heartbeat(self):
        import json

        import astra_tool
        from tests.cycle_artifacts import remove_cycle_artifacts
        from tests.test_input_request_cycle import DECIDED_CODE, _fake, _run

        fake = _fake(DECIDED_CODE, {"status": "REFUTED", "reasoning": "sign check failed"})
        base_init = fake.__init__

        def init(self, provider, cli_models=None, cli_timeout=None):
            base_init(self, provider, cli_models, cli_timeout)
            self.cli_kind = {"claude_cli": "claude", "codex_cli": "codex", "agy_cli": "agy"}.get(provider)
            self.cli_last_model = None

        fake.__init__ = init
        with patch.dict(os.environ, {"ASTRA_CODE_REVIEW": "0", "ASTRA_CODEX_MODELS": "gpt-6.1-sol@ultra"}, clear=False):
            result = await _run(fake, {})
        try:
            with open(astra_tool._progress_path(), encoding="utf-8") as fh:
                beat = json.load(fh)
            self.assertEqual(beat["stage"], "done")
            self.assertEqual(beat["models"]["conjecture"]["planned"], "gpt-6.1-sol@ultra")
            self.assertEqual(beat["models"]["translator"]["cli"], "claude")
            self.assertIsNone(astra_tool._PROGRESS_MODELS)
        finally:
            remove_cycle_artifacts(result)
