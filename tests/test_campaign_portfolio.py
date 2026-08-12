"""Stage 1: structured portfolio from the ensemble synthesis (R1, R3, R4)."""
import json
import unittest
from unittest.mock import patch

from agents.analyst import REFUTATION_ANALYST_PROMPT
from agents.conjecture import CONJECTURE_ENGINE_PROMPT
from astra_tool import _MERGE_SYSTEM, _ensemble_conjecture
from core.campaign_models import (
    BudgetVector,
    Campaign,
    CampaignStatus,
    EvidenceKind,
)
from core.campaign_policy import CampaignState, evaluate_branch_admissibility
from core.campaign_portfolio import (
    DEFAULT_PLAN_COST,
    Portfolio,
    PortfolioError,
    extract_portfolio_block,
    forbidden_family_violations,
    negative_prompt_block,
    parse_portfolio,
    portfolio_instruction_block,
    portfolio_to_records,
)

COMMIT = "a" * 40
TS = "2026-08-12T00:00:00Z"
SHA = "b" * 64


def make_candidate_dict(**overrides) -> dict:
    base = {
        "statement": "For all real x, x**2 >= 0.",
        "claim_type": "UNIVERSAL",
        "domain": "real analysis",
        "scope": "all real x",
        "quantifiers": ["forall x in R"],
        "assumptions": ["standard ordering of R"],
        "tolerance": None,
        "units": None,
        "method_family": "symbolic_residual",
        "material_difference": "Exact simplification instead of sampling.",
        "assumption_delta": {"added": [], "removed": []},
        "evidence_plan": {
            "description": "Symbolic residual check.",
            "kind": "SYMBOLIC",
        },
        "deliverable": "identity proof",
        "direction": "Attack via exact residual simplification.",
        "crux": "Show the residual simplifies to zero in the general case.",
    }
    base.update(overrides)
    return base


def make_portfolio_dict(**overrides) -> dict:
    base = {
        "schema_version": "astra-portfolio/0.1",
        "selected": make_candidate_dict(),
        "alternatives": [
            make_candidate_dict(
                statement="A bounded numerical scan finds no negative value.",
                method_family="numerical_scan",
                material_difference="Sampling instead of exact simplification.",
                evidence_plan={
                    "description": "Dense scan on a bounded grid.",
                    "kind": "NUMERICAL",
                },
                crux=None,
            )
        ],
    }
    base.update(overrides)
    return base


def fenced(payload: dict) -> str:
    return "```astra-portfolio\n" + json.dumps(payload) + "\n```"


def make_campaign(**overrides) -> Campaign:
    base = dict(
        campaign_id="cmp_stage1-001",
        created_at=TS,
        source_commit=COMMIT,
        objective="Decide whether the bounded identity family holds.",
        success_definition="Every mandatory deliverable has credible evidence.",
        deliverables=("identity proof", "counterexample report"),
        frozen_resources={"brief.md": SHA},
        allowed_evidence_classes=(EvidenceKind.SYMBOLIC, EvidenceKind.NUMERICAL),
        budget=BudgetVector(
            cycles=10,
            model_calls=40,
            wall_seconds=3600,
            execution_seconds=1800,
            human_interventions=2,
            remote_jobs=4,
        ),
        status=CampaignStatus.ACTIVE,
    )
    base.update(overrides)
    return Campaign(**base)


def sequential_id_factory():
    counter = {"n": 0}
    prefixes = {"claim": "clm", "branch": "brn"}

    def factory(kind: str) -> str:
        counter["n"] += 1
        return f"{prefixes[kind]}_conv-{counter['n']:04d}"

    return factory


class PortfolioParsingTests(unittest.TestCase):
    def test_valid_block_parses_and_strips_the_conjecture(self):
        text = "Consensus conjecture text.\n\n" + fenced(make_portfolio_dict())
        result = parse_portfolio(text)
        self.assertIsNone(result.error)
        self.assertEqual(result.conjecture_text, "Consensus conjecture text.")
        self.assertEqual(
            result.portfolio.selected.method_family, "symbolic_residual"
        )
        self.assertEqual(len(result.portfolio.alternatives), 1)

    def test_missing_block_is_fail_soft(self):
        result = parse_portfolio("Just a conjecture, no block.")
        self.assertIsNone(result.portfolio)
        self.assertIn("missing", result.error)
        self.assertEqual(result.conjecture_text, "Just a conjecture, no block.")

    def test_invalid_json_reports_error_and_still_strips(self):
        text = "Conjecture.\n\n```astra-portfolio\n{not json\n```"
        result = parse_portfolio(text)
        self.assertIsNone(result.portfolio)
        self.assertIn("not valid JSON", result.error)
        self.assertEqual(result.conjecture_text, "Conjecture.")

    def test_unknown_schema_version_fails_content_validation(self):
        payload = make_portfolio_dict(schema_version="astra-portfolio/9.9")
        result = parse_portfolio(fenced(payload))
        self.assertIsNone(result.portfolio)
        self.assertIn("schema version", result.error)

    def test_selected_candidate_requires_the_crux(self):
        payload = make_portfolio_dict()
        payload["selected"]["crux"] = None
        result = parse_portfolio(fenced(payload))
        self.assertIsNone(result.portfolio)
        self.assertIn("crux", result.error)

    def test_more_than_four_candidates_fails(self):
        payload = make_portfolio_dict()
        payload["alternatives"] = [
            make_candidate_dict(method_family=f"family_{i}", crux=None)
            for i in range(4)
        ]
        result = parse_portfolio(fenced(payload))
        self.assertIsNone(result.portfolio)
        self.assertIn("at most 4", result.error)

    def test_duplicate_method_families_fail(self):
        payload = make_portfolio_dict()
        payload["alternatives"][0]["method_family"] = "symbolic_residual"
        result = parse_portfolio(fenced(payload))
        self.assertIsNone(result.portfolio)
        self.assertIn("materially different", result.error)

    def test_unknown_claim_type_and_kind_fail(self):
        payload = make_portfolio_dict()
        payload["selected"]["claim_type"] = "VIBES"
        self.assertIn(
            "claim_type", parse_portfolio(fenced(payload)).error
        )
        payload = make_portfolio_dict()
        payload["selected"]["evidence_plan"]["kind"] = "GUESSWORK"
        self.assertIn(
            "evidence kind", parse_portfolio(fenced(payload)).error
        )

    def test_unknown_candidate_field_fails_closed(self):
        payload = make_portfolio_dict()
        payload["selected"]["confidence"] = 0.99
        result = parse_portfolio(fenced(payload))
        self.assertIsNone(result.portfolio)
        self.assertIn("unknown=['confidence']", result.error)

    def test_last_block_wins_and_every_block_is_stripped(self):
        stale = make_portfolio_dict()
        stale["selected"]["method_family"] = "stale_family"
        fresh = make_portfolio_dict()
        text = "Head.\n" + fenced(stale) + "\nMiddle.\n" + fenced(fresh)
        block, stripped = extract_portfolio_block(text)
        self.assertIn("symbolic_residual", block)
        self.assertNotIn("astra-portfolio", stripped)
        self.assertIn("Head.", stripped)
        self.assertIn("Middle.", stripped)

    def test_portfolio_round_trip_is_stable(self):
        portfolio = Portfolio.from_dict(make_portfolio_dict())
        again = Portfolio.from_dict(json.loads(json.dumps(portfolio.to_dict())))
        self.assertEqual(portfolio.to_dict(), again.to_dict())

    def test_machine_paths_are_rejected_in_portable_fields(self):
        payload = make_portfolio_dict()
        payload["selected"]["statement"] = r"See C:\Users\nelson\proof.py"
        result = parse_portfolio(fenced(payload))
        self.assertIsNone(result.portfolio)
        self.assertIn("machine-specific", result.error)


class ForbiddenFamilyTests(unittest.TestCase):
    def test_violations_are_detected_case_insensitively(self):
        portfolio = Portfolio.from_dict(make_portfolio_dict())
        self.assertEqual(
            forbidden_family_violations(portfolio, ["Symbolic_Residual"]),
            ("symbolic_residual",),
        )
        self.assertEqual(
            forbidden_family_violations(portfolio, ["something_else"]), ()
        )

    def test_negative_prompt_block_content(self):
        text = negative_prompt_block(["numerical_scan", "symbolic_residual"])
        self.assertIn("DO NOT use them", text)
        self.assertIn("numerical_scan", text)
        self.assertIn("materially different", text)
        self.assertEqual(negative_prompt_block([]), "")

    def test_instruction_block_carries_the_contract(self):
        text = portfolio_instruction_block(
            deliverables=("identity proof",),
            allowed_evidence_kinds=(EvidenceKind.SYMBOLIC,),
            forbidden_families=("numerical_scan",),
        )
        self.assertIn("```astra-portfolio", text)
        self.assertIn("crux", text)
        self.assertIn("identity proof", text)
        self.assertIn("SYMBOLIC", text)
        self.assertIn("DO NOT use them", text)
        self.assertIn("materially different", text)


class RecordConversionTests(unittest.TestCase):
    def test_portfolio_converts_to_valid_campaign_records(self):
        portfolio = Portfolio.from_dict(make_portfolio_dict())
        campaign = make_campaign()
        records = portfolio_to_records(
            portfolio,
            campaign,
            source_commit=COMMIT,
            created_at=TS,
            id_factory=sequential_id_factory(),
        )
        self.assertEqual(len(records), 2)
        claim, branch = records[0]
        self.assertEqual(claim.claim_id, "clm_conv-0001")
        self.assertEqual(branch.claim_refs, (claim.claim_id,))
        self.assertEqual(branch.deliverable_refs, ("identity proof",))
        self.assertEqual(branch.method_family, "symbolic_residual")
        self.assertEqual(
            claim.unresolved_obligations,
            ("Show the residual simplifies to zero in the general case.",),
        )
        alt_claim, alt_branch = records[1]
        self.assertEqual(alt_claim.unresolved_obligations, ())
        self.assertEqual(alt_branch.method_family, "numerical_scan")
        self.assertEqual(
            branch.evidence_plan.estimated_cost, DEFAULT_PLAN_COST
        )

    def test_converted_candidates_pass_the_hard_gates(self):
        portfolio = Portfolio.from_dict(make_portfolio_dict())
        campaign = make_campaign()
        records = portfolio_to_records(
            portfolio,
            campaign,
            source_commit=COMMIT,
            created_at=TS,
            id_factory=sequential_id_factory(),
        )
        state = CampaignState(campaign=campaign)
        for claim, _branch in records:
            state.claims[claim.claim_id] = claim
        for _claim, branch in records:
            result = evaluate_branch_admissibility(state, branch)
            self.assertTrue(
                result.passed,
                f"{branch.method_family} failed gates: {result.failed_gates}",
            )

    def test_conversion_requires_a_known_deliverable(self):
        payload = make_portfolio_dict()
        payload["selected"]["deliverable"] = None
        portfolio = Portfolio.from_dict(payload)
        with self.assertRaises(PortfolioError):
            portfolio_to_records(
                portfolio,
                make_campaign(),
                source_commit=COMMIT,
                created_at=TS,
                id_factory=sequential_id_factory(),
            )
        payload = make_portfolio_dict()
        payload["selected"]["deliverable"] = "a deliverable nobody defined"
        portfolio = Portfolio.from_dict(payload)
        with self.assertRaises(PortfolioError):
            portfolio_to_records(
                portfolio,
                make_campaign(),
                source_commit=COMMIT,
                created_at=TS,
                id_factory=sequential_id_factory(),
            )

    def test_conversion_is_deterministic(self):
        portfolio = Portfolio.from_dict(make_portfolio_dict())
        campaign = make_campaign()
        first = portfolio_to_records(
            portfolio,
            campaign,
            source_commit=COMMIT,
            created_at=TS,
            id_factory=sequential_id_factory(),
        )
        second = portfolio_to_records(
            portfolio,
            campaign,
            source_commit=COMMIT,
            created_at=TS,
            id_factory=sequential_id_factory(),
        )
        self.assertEqual(
            [(c.to_dict(), b.to_dict()) for c, b in first],
            [(c.to_dict(), b.to_dict()) for c, b in second],
        )


class FakeIntelligence:
    """Minimal stand-in for ASTRAIntelligence inside _ensemble_conjecture."""

    merge_output: str | None = ""
    merge_systems: list = []

    def __init__(self, provider, cli_models=None, cli_timeout=None):
        self.provider = provider
        self.cli_models = cli_models
        self.cli_timeout = cli_timeout
        self.cli_warnings = []
        self.cli_last_model = provider
        self.cli_cost_usd = 0.0

    async def generate_conjecture(self, axiomatic_base, intuition):
        return f"Proposal from {self.provider}."

    async def _call_api(self, system, user):
        if "sintetizador" in system:
            FakeIntelligence.merge_systems.append(system)
            return FakeIntelligence.merge_output
        return "Adversarial critique of the rivals."


class EnsembleWiringTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        FakeIntelligence.merge_systems = []
        FakeIntelligence.merge_output = ""

    async def run_ensemble(self, env=None, portfolio_context=None):
        with patch.dict(
            "os.environ", env or {"ASTRA_PORTFOLIO_SYNTH": "1"}, clear=False
        ), patch("core.llm_client.ASTRAIntelligence", FakeIntelligence):
            return await _ensemble_conjecture(
                ["codex_cli", "agy_cli"],
                "axioms",
                "problem",
                30,
                "codex_cli",
                portfolio_context=portfolio_context,
            )

    async def test_merge_emits_and_strips_the_portfolio(self):
        FakeIntelligence.merge_output = (
            "Consensus conjecture.\n\n" + fenced(make_portfolio_dict())
        )
        merged, _used, deliberation = await self.run_ensemble()
        self.assertEqual(merged, "Consensus conjecture.")
        self.assertNotIn("astra-portfolio", merged)
        self.assertEqual(
            deliberation["portfolio"]["selected"]["method_family"],
            "symbolic_residual",
        )
        self.assertNotIn("portfolio_error", deliberation)
        self.assertEqual(len(FakeIntelligence.merge_systems), 1)
        self.assertIn("```astra-portfolio", FakeIntelligence.merge_systems[0])

    async def test_missing_block_records_error_and_keeps_conjecture(self):
        FakeIntelligence.merge_output = "Consensus conjecture without block."
        merged, _used, deliberation = await self.run_ensemble()
        self.assertEqual(merged, "Consensus conjecture without block.")
        self.assertIsNone(deliberation["portfolio"])
        self.assertIn("missing", deliberation["portfolio_error"])

    async def test_env_gate_disables_the_portfolio_addendum(self):
        FakeIntelligence.merge_output = "Plain consensus."
        merged, _used, deliberation = await self.run_ensemble(
            env={"ASTRA_PORTFOLIO_SYNTH": "0"}
        )
        self.assertEqual(merged, "Plain consensus.")
        self.assertNotIn("portfolio", deliberation)
        self.assertNotIn(
            "astra-portfolio", FakeIntelligence.merge_systems[0]
        )

    async def test_forbidden_families_flow_through_prompt_and_detection(self):
        FakeIntelligence.merge_output = (
            "Consensus.\n\n" + fenced(make_portfolio_dict())
        )
        context = {
            "deliverables": ["identity proof"],
            "allowed_evidence_kinds": ["SYMBOLIC", "NUMERICAL"],
            "forbidden_method_families": ["symbolic_residual"],
        }
        _merged, _used, deliberation = await self.run_ensemble(
            portfolio_context=context
        )
        self.assertIn("DO NOT use them", FakeIntelligence.merge_systems[0])
        self.assertIn("identity proof", FakeIntelligence.merge_systems[0])
        self.assertEqual(
            deliberation["portfolio_forbidden_violations"],
            ["symbolic_residual"],
        )

    async def test_degraded_merge_reports_no_portfolio(self):
        FakeIntelligence.merge_output = None
        merged, _used, deliberation = await self.run_ensemble()
        self.assertIn("=== CONJETURA A", merged)
        self.assertIsNone(deliberation["portfolio"])
        self.assertIn("degraded", deliberation["portfolio_error"])


class PromptNeutralityTests(unittest.TestCase):
    """R1: prompts must never presuppose the hypothesis is true."""

    def test_conjecture_prompt_requires_a_neutral_stance(self):
        self.assertIn("prove OR refute", CONJECTURE_ENGINE_PROMPT)
        self.assertIn("never as a fact to confirm", CONJECTURE_ENGINE_PROMPT)

    def test_merge_prompt_requests_balanced_evidence(self):
        self.assertIn("prueba y refutacion", _MERGE_SYSTEM)

    def test_analyst_prompt_stays_free_of_confirmation_bias(self):
        self.assertIn("free of confirmation bias", REFUTATION_ANALYST_PROMPT)
        self.assertIn(
            "Actively consider both proof and refutation",
            REFUTATION_ANALYST_PROMPT,
        )


if __name__ == "__main__":
    unittest.main()
