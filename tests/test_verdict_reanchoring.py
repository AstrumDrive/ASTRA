"""Verdict re-anchoring: answer the user's claim, not only the conjecture.

Regression suite for the failure mode measured on 2026-08-12
(`docs/evidence/ASTRA2_H1_SMOKE_CLEAN_20260812.md`): ASTRA correctly refuted
seeded false claims but reported VALIDATED, because the cycle status
describes the conjecture it formed rather than the claim the user stated.
"""
import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.analyst import REFUTATION_ANALYST_PROMPT
from core.llm_client import (
    ORIGINAL_CLAIM_VERDICTS,
    ASTRAIntelligence,
    _normalize_original_claim_verdict,
)

ROOT = Path(__file__).resolve().parents[1]


def load_benchmark_runner():
    spec = importlib.util.spec_from_file_location(
        "run_quality_benchmarks", ROOT / "scripts" / "run_quality_benchmarks.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PromptContractTests(unittest.TestCase):
    def test_analyst_prompt_demands_re_anchoring(self):
        self.assertIn("original_claim_verdict", REFUTATION_ANALYST_PROMPT)
        self.assertIn("VERDICT RE-ANCHORING", REFUTATION_ANALYST_PROMPT)
        for verdict in ("SUPPORTED", "REFUTED", "INCONCLUSIVE", "SUBSTITUTED"):
            self.assertIn(verdict, REFUTATION_ANALYST_PROMPT)
        # The counterexample rule is the exact case measured in the canary.
        self.assertIn("counterexample to P", REFUTATION_ANALYST_PROMPT)

    def test_prompt_judges_the_proposition_not_the_hint(self):
        # Live finding 2026-08-12: seeded cases put a *hint* in the direction
        # field ("solves the DE but may fail the initial conditions") and the
        # decidable proposition in the objective. The analyst must judge the
        # proposition, never the hint.
        self.assertIn("Determine whether P", REFUTATION_ANALYST_PROMPT)
        self.assertIn("Never judge the hint", REFUTATION_ANALYST_PROMPT)


class NormalizationTests(unittest.TestCase):
    def test_known_verdicts_survive_and_are_upcased(self):
        for verdict in ("supported", "REFUTED", "Inconclusive", "substituted"):
            with self.subTest(verdict=verdict):
                parsed = _normalize_original_claim_verdict(
                    {"original_claim_verdict": verdict}, "the claim"
                )
                self.assertEqual(
                    parsed["original_claim_verdict"], verdict.upper()
                )

    def test_unknown_or_missing_never_fabricates_a_verdict(self):
        for payload in ({}, {"original_claim_verdict": "PROBABLY_TRUE"},
                        {"original_claim_verdict": None}):
            with self.subTest(payload=payload):
                parsed = _normalize_original_claim_verdict(
                    dict(payload), "the claim"
                )
                self.assertEqual(
                    parsed["original_claim_verdict"], "UNSPECIFIED"
                )

    def test_without_an_anchor_there_is_nothing_to_re_anchor_to(self):
        parsed = _normalize_original_claim_verdict(
            {"original_claim_verdict": "REFUTED"}, ""
        )
        self.assertEqual(parsed["original_claim_verdict"], "UNSPECIFIED")

    def test_an_objective_alone_is_a_valid_anchor(self):
        # The proposition normally lives in the objective, so a missing
        # direction must not suppress a real re-anchored verdict.
        parsed = _normalize_original_claim_verdict(
            {"original_claim_verdict": "REFUTED"},
            "Determine whether sqrt(x^2)=x for every real x.",
        )
        self.assertEqual(parsed["original_claim_verdict"], "REFUTED")

    def test_closed_enum_is_the_single_source(self):
        self.assertEqual(
            set(ORIGINAL_CLAIM_VERDICTS),
            {"SUPPORTED", "REFUTED", "INCONCLUSIVE", "SUBSTITUTED",
             "UNSPECIFIED"},
        )


class AnalystWiringTests(unittest.IsolatedAsyncioTestCase):
    async def test_original_claim_reaches_the_analyst_and_returns_re_anchored(self):
        analyst = ASTRAIntelligence(provider="codex_cli")
        prompts = []

        async def fake_call(_system, user):
            prompts.append(user)
            return json.dumps(
                {
                    "status": "VALIDATED",
                    "reasoning": "The counterexample x=-1 is exact.",
                    "original_claim_verdict": "REFUTED",
                    "original_claim_reasoning": (
                        "The validated conjecture is a counterexample to the "
                        "user's universal claim, so the claim is false."
                    ),
                }
            )

        analyst._call_api = fake_call
        result = await analyst.analyze_results(
            "x=-1 is an exact counterexample to sqrt(x^2)=x",
            {
                "exit_code": 0,
                "stdout": "CHECK witness: OK\nVERDICT: PASS",
                "stderr": "",
                "validation_code": "print('VERDICT: PASS')",
                "code_review": {"status": "APPROVED"},
            },
            shared_goal="Determine whether sqrt(x^2)=x for every real x.",
            original_claim="Test the universal real-domain claim.",
        )
        # The objective carries the decidable proposition; the direction is a
        # hint. Both reach the analyst, labeled for what they are.
        self.assertIn("SHARED FINAL OBJECTIVE", prompts[0])
        self.assertIn("Determine whether sqrt(x^2)=x", prompts[0])
        self.assertIn("CURRENT DIRECTION OR HINT", prompts[0])
        # The two axes stay separate and disagree, which is the whole point.
        self.assertEqual(result["status"], "VALIDATED")
        self.assertEqual(result["original_claim_verdict"], "REFUTED")

    async def test_missing_field_degrades_to_unspecified_not_to_a_guess(self):
        analyst = ASTRAIntelligence(provider="codex_cli")

        async def fake_call(_system, _user):
            return json.dumps({"status": "VALIDATED", "reasoning": "ok"})

        analyst._call_api = fake_call
        result = await analyst.analyze_results(
            "some conjecture",
            {
                "exit_code": 0,
                "stdout": "VERDICT: PASS",
                "stderr": "",
                "validation_code": "print('VERDICT: PASS')",
                "code_review": {"status": "APPROVED"},
            },
            original_claim="some user claim",
        )
        self.assertEqual(result["original_claim_verdict"], "UNSPECIFIED")


class BenchmarkScoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = load_benchmark_runner()

    def test_refuted_re_anchor_is_no_longer_a_false_acceptance(self):
        # The exact shape measured in the clean smoke run.
        result = {"status": "VALIDATED", "original_claim_verdict": "REFUTED"}
        self.assertEqual(self.runner._reanchored_status(result), "REFUTED")

    def test_supported_re_anchor_scores_as_validated(self):
        result = {"status": "VALIDATED", "original_claim_verdict": "SUPPORTED"}
        self.assertEqual(self.runner._reanchored_status(result), "VALIDATED")

    def test_unanswered_questions_are_distinct_from_both_truth_values(self):
        for verdict in ("SUBSTITUTED", "INCONCLUSIVE"):
            with self.subTest(verdict=verdict):
                observed = self.runner._reanchored_status(
                    {"status": "VALIDATED", "original_claim_verdict": verdict}
                )
                self.assertEqual(observed, verdict)
                self.assertNotIn(observed, {"VALIDATED", "REFUTED"})

    def test_absent_field_keeps_historical_behavior(self):
        self.assertEqual(
            self.runner._reanchored_status({"status": "VALIDATED"}),
            "VALIDATED",
        )
        self.assertEqual(
            self.runner._reanchored_status(
                {"status": "REFUTED", "original_claim_verdict": "UNSPECIFIED"}
            ),
            "REFUTED",
        )

    def test_operational_statuses_are_never_re_anchored(self):
        for status in ("CODE_ERROR", "API_ERROR", "TIMEOUT", "TOOL_ERROR"):
            with self.subTest(status=status):
                self.assertEqual(
                    self.runner._reanchored_status(
                        {"status": status,
                         "original_claim_verdict": "SUPPORTED"}
                    ),
                    status,
                )

    def test_false_acceptance_rate_drops_to_zero_on_the_measured_records(self):
        from core.quality_metrics import _scientific_metrics

        def record(case_id, expected, observed):
            return {
                "id": case_id,
                "track": "cycle",
                "expected": expected,
                "observed": observed,
                "correct": observed == expected,
            }

        # Before: the two correct refutations were scored as VALIDATED.
        before = _scientific_metrics(
            [
                record("sqrt_false", "REFUTED", "VALIDATED"),
                record("ode_false", "REFUTED", "VALIDATED"),
                record("true_case", "VALIDATED", "VALIDATED"),
            ]
        )
        self.assertEqual(before["false_acceptance_rate"], 1.0)
        # After re-anchoring the same cycles score their real epistemic result.
        after = _scientific_metrics(
            [
                record("sqrt_false", "REFUTED", "REFUTED"),
                record("ode_false", "REFUTED", "REFUTED"),
                record("true_case", "VALIDATED", "VALIDATED"),
            ]
        )
        self.assertEqual(after["false_acceptance_rate"], 0.0)
        self.assertEqual(after["strict_accuracy"], 1.0)


class CycleOutputTests(unittest.IsolatedAsyncioTestCase):
    async def test_cycle_exposes_the_re_anchored_axis_without_collapsing(self):
        class FakeIntelligence:
            def __init__(self, provider, cli_models=None, cli_timeout=None):
                self.provider = provider
                self.cli_models = cli_models
                self.cli_timeout = cli_timeout
                self.cli_warnings = []
                self.cli_last_model = provider
                self.cli_cost_usd = 0.0
                self.seen_original_claim = None

            async def generate_conjecture(self, **_kwargs):
                return (
                    "[Hypothesis]\nx=-1 is an exact counterexample to the "
                    "universal claim."
                )

            async def translate_to_code(self, *_args, **_kwargs):
                return (
                    "ok = (-1) ** 2 == 1\n"
                    "print(f\"CHECK witness: {'OK' if ok else 'FAIL'}\")\n"
                    "print('VERDICT: PASS' if ok else 'VERDICT: FAIL')\n"
                )

            async def review_validation_code(self, **_kwargs):
                return {
                    "status": "APPROVED",
                    "reasoning": "Exact witness.",
                    "revision_instructions": "",
                    "coverage": ["witness"],
                    "defect_labels": [],
                    "runtime_checks": [],
                }

            async def analyze_results(self, *_args, **kwargs):
                FakeIntelligence.last_original_claim = kwargs.get(
                    "original_claim"
                )
                return {
                    "status": "VALIDATED",
                    "reasoning": "The counterexample executed exactly.",
                    "original_claim_verdict": "REFUTED",
                    "original_claim_reasoning": (
                        "The validated counterexample falsifies the claim."
                    ),
                    "goal_coverage": "COMPLETE",
                    "goal_resolved": True,
                }

        from astra_tool import _do_cycle

        providers = {
            "conjecture": "codex_cli",
            "translator": "claude_cli",
            "reviewer": "codex_cli",
            "analyst": "codex_cli",
            "navigator": "agy_cli",
            "synth": "codex_cli",
        }
        env = {
            "ASTRA_CYCLE_CACHE": "0",
            "ASTRA_CONJECTURE_PROVIDER": "codex_cli",
            "ASTRA_NAVIGATE_AFTER_CYCLE": "0",
            "ASTRA_MAX_RETRIES": "0",
            "ASTRA_ORACLE_MODE": "local",
        }
        with patch.dict("os.environ", env, clear=False), patch(
            "core.preflight.phase_provider_map", return_value=providers
        ), patch("core.llm_client.ASTRAIntelligence", FakeIntelligence):
            result = await _do_cycle(
                {
                    "action": "cycle",
                    "intuition": "For all real x, sqrt(x^2) = x.",
                    "objective": "Decide the identity.",
                    "cycle_timeout_seconds": 120,
                }
            )

        self.assertEqual(
            FakeIntelligence.last_original_claim,
            "For all real x, sqrt(x^2) = x.",
        )
        self.assertEqual(result["status"], "VALIDATED")
        self.assertEqual(result["original_claim_verdict"], "REFUTED")
        self.assertIn("falsifies", result["original_claim_reasoning"])
        checkpoint = Path(result["checkpoint"])
        if checkpoint.exists():
            checkpoint.unlink()


if __name__ == "__main__":
    unittest.main()
