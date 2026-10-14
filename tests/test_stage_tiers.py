"""Strong models plan and decide, lighter ones write and re-check (1.1.16)."""
import os
import unittest
from unittest.mock import patch

from agents.translator import PLAN_BLOCK_HEADER
from core.architecture_contract import audit_production_architecture
from tests.cycle_artifacts import remove_cycle_artifacts
from tests.test_architecture_contract import ArchitectureContractTests
from tests.test_input_request_cycle import DECIDED_CODE, _fake, _run

PLAN = "1. PROPOSITION: P\n4. DECISIVE LEGS: exact\n5. FAIL ROUTE: residual nonzero"


def _planned_fake(review_script=None):
    fake = _fake(DECIDED_CODE, {"status": "REFUTED", "reasoning": "sign check failed"})
    fake.seen["plans"] = 0
    fake.seen["review_models"] = []

    async def plan_validation(self, translation_input):
        fake.seen["plans"] += 1
        return PLAN

    fake.plan_validation = plan_validation
    if review_script is not None:
        async def review_validation_code(self, **kwargs):
            fake.seen["review_models"].append(self.cli_models)
            return dict(review_script.pop(0))

        async def repair_validation_code(self, *args, **kwargs):
            return {"status": "APPLIED", "code": DECIDED_CODE + "# patched\n"}

        fake.review_validation_code = review_validation_code
        fake.repair_validation_code = repair_validation_code
    return fake


class PlannerPhase(unittest.IsolatedAsyncioTestCase):
    async def test_the_plan_reaches_the_code_author(self):
        fake = _planned_fake()
        with patch.dict(os.environ, {"ASTRA_CODE_REVIEW": "0", "ASTRA_AUTHOR_SPLIT": "1"}, clear=False):
            result = await _run(fake, {})
        try:
            self.assertEqual(fake.seen["plans"], 1)
            author_input = fake.seen["translation_inputs"][0]
            self.assertIn(PLAN_BLOCK_HEADER, author_input)
            self.assertIn("5. FAIL ROUTE: residual nonzero", author_input)
            self.assertIn("plan", result.get("timings", {}))
        finally:
            remove_cycle_artifacts(result)

    async def test_no_plan_phase_when_the_split_is_off(self):
        fake = _planned_fake()
        with patch.dict(os.environ, {"ASTRA_CODE_REVIEW": "0", "ASTRA_AUTHOR_SPLIT": "0"}, clear=False):
            result = await _run(fake, {})
        try:
            self.assertEqual(fake.seen["plans"], 0)
            self.assertNotIn(PLAN_BLOCK_HEADER, fake.seen["translation_inputs"][0])
        finally:
            remove_cycle_artifacts(result)


class ReviewerFollowupLadder(unittest.IsolatedAsyncioTestCase):
    async def test_second_review_uses_the_lighter_ladder(self):
        revise = {"status": "REVISE", "reasoning": "tighten", "revision_instructions": "add a FAIL leg",
                  "coverage": [], "defect_labels": ["unreachable_failure"], "runtime_checks": []}
        approve = {"status": "APPROVED", "reasoning": "ok", "revision_instructions": "",
                   "coverage": ["all"], "defect_labels": [], "runtime_checks": []}
        fake = _planned_fake([revise, approve])
        env = {"ASTRA_CODE_REVIEW": "1", "ASTRA_REVIEWER_MODELS": "gpt-6.1-sol@max",
               "ASTRA_REVIEWER_FOLLOWUP_MODELS": "gpt-6-luna@xhigh"}
        with patch.dict(os.environ, env, clear=False):
            result = await _run(fake, {})
        try:
            self.assertGreaterEqual(len(fake.seen["review_models"]), 2, result.get("error"))
            self.assertEqual(fake.seen["review_models"][0], "gpt-6.1-sol@max")
            self.assertEqual(fake.seen["review_models"][1], "gpt-6-luna@xhigh")
        finally:
            remove_cycle_artifacts(result)


class SplitContract(unittest.TestCase):
    def _env(self, **extra):
        env = ArchitectureContractTests().canonical_environment()
        env.update(extra)
        return env

    def test_split_needs_a_top_planner_and_allows_a_sonnet_author(self):
        ok = audit_production_architecture(self._env(
            ASTRA_AUTHOR_SPLIT="1", ASTRA_PLANNER_MODELS="claude-fable-5-1@max,claude-opus-5-5@max",
            ASTRA_TRANSLATOR_MODELS="sonnet@high,claude-opus-5-5@high"), check_binaries=False)
        self.assertNotIn("author_effective_model", ok["required_failures"])
        self.assertNotIn("planner_effective_model", ok["required_failures"])
        weak = audit_production_architecture(self._env(
            ASTRA_AUTHOR_SPLIT="1", ASTRA_PLANNER_MODELS="sonnet",
            ASTRA_TRANSLATOR_MODELS="sonnet@high"), check_binaries=False)
        self.assertIn("planner_effective_model", weak["required_failures"])


if __name__ == "__main__":
    unittest.main()
