"""Two additions from the Research IR evaluation, 2026-08-30.

Both come from `docs/architecture/ASTRA2_RESEARCH_IR_EVALUATION.md`, which
compared a proposal Nelson developed outside the repo against what ASTRA 2
already had. Most of the proposal was already implemented; these two were
genuinely missing, and both are cheap because they rest on structures that
already run.

**Failed paths keep their boundary.** `exhausted_method_families` answers the
hard gate's question -- may this family be proposed again -- and a bare "no"
is all a gate needs. It is not all a proposer needs. A branch that died
because convexity fails below alpha = 0.731 established something reusable:
the method still holds above it. The reason was already written to the ledger
by BRANCH_STATUS_CHANGED and then discarded by the state reducer; the
boundary did not exist at all.

**Approximations are a claim type.** "f ≈ g" with no regime and no error
bound is not a weaker claim than an equality, it is not a claim at all,
because no observation can contradict it. Making the missing bound generate
an entry in `unresolved_obligations` is the point: it is how a physical
statement produces a mathematical one the campaign can schedule.
"""
import unittest

from core.campaign_models import (
    ApproximationSpec,
    AssumptionDelta,
    Branch,
    BranchStatus,
    BudgetVector,
    Claim,
    ClaimType,
    CampaignModelError,
    EvidenceKind,
    EvidencePlan,
    PriorityVector,
    canonical_sha256,
)

TS = "2026-08-30T00:00:00Z"
COMMIT = "0" * 40


def make_branch(**overrides) -> Branch:
    base = dict(
        branch_id="brn_alpha-0001",
        campaign_id="cmp_alpha-0001",
        created_at=TS,
        source_commit=COMMIT,
        direction="Attack the bound through convexity of F.",
        method_family="convexity",
        material_difference="Uses convexity instead of a spectral estimate.",
        assumption_delta=AssumptionDelta(added=("F twice differentiable",), removed=()),
        evidence_plan=EvidencePlan(
            description="Symbolic check of F'' sign on the parameter range.",
            kind=EvidenceKind.SYMBOLIC,
            estimated_cost=BudgetVector(
                cycles=1,
                model_calls=4,
                wall_seconds=600,
                execution_seconds=120,
                human_interventions=0,
                remote_jobs=0,
            ),
        ),
        priority_vector=PriorityVector(
            information_gain=0.6,
            evidence_strength=0.4,
            methodological_independence=0.7,
            goal_advancement=0.5,
            estimated_cost=0.3,
            instability_risk=0.2,
        ),
        budget=BudgetVector(
            cycles=4,
            model_calls=16,
            wall_seconds=2400,
            execution_seconds=480,
            human_interventions=0,
            remote_jobs=0,
        ),
        deliverable_refs=("lower bound",),
    )
    base.update(overrides)
    return Branch(**base)


def make_claim(**overrides) -> Claim:
    base = dict(
        claim_id="clm_alpha-0001",
        campaign_id="cmp_alpha-0001",
        created_at=TS,
        source_commit=COMMIT,
        statement="For all real x, x**2 >= 0.",
        claim_type=ClaimType.UNIVERSAL,
        domain="real analysis",
        scope="all real x",
        quantifiers=("forall x in R",),
        assumptions=("standard ordering of R",),
    )
    base.update(overrides)
    return Claim(**base)


REASON = "F'' changes sign for alpha < 0.731, so convexity fails there."
BOUNDARY = "Convexity approach remains viable for alpha >= 0.731."


class ClosureBoundary(unittest.TestCase):
    def test_branch_records_reason_and_boundary(self):
        branch = make_branch(closure_reason=REASON, closure_boundary=BOUNDARY)
        self.assertEqual(branch.closure_reason, REASON)
        self.assertEqual(branch.closure_boundary, BOUNDARY)

    def test_absent_by_default(self):
        branch = make_branch()
        self.assertIsNone(branch.closure_reason)
        self.assertIsNone(branch.closure_boundary)

    def test_boundary_without_reason_is_rejected(self):
        # A surviving region with no stated failure cannot be interpreted:
        # "viable for alpha >= 0.731" means nothing without knowing what went
        # wrong below it.
        with self.assertRaises(CampaignModelError) as ctx:
            make_branch(closure_boundary=BOUNDARY)
        self.assertIn("closure_boundary requires closure_reason", str(ctx.exception))

    def test_with_status_carries_them(self):
        closed = make_branch(status=BranchStatus.ACTIVE).with_status(
            BranchStatus.EXHAUSTED,
            closure_reason=REASON,
            closure_boundary=BOUNDARY,
        )
        self.assertIs(closed.status, BranchStatus.EXHAUSTED)
        self.assertEqual(closed.closure_reason, REASON)
        self.assertEqual(closed.closure_boundary, BOUNDARY)

    def test_a_later_transition_does_not_erase_an_earlier_closure(self):
        # SUSPENDED carries a reason too, and a branch resumed and closed
        # again would otherwise lose what the first closure established.
        suspended = make_branch(
            status=BranchStatus.SUSPENDED,
            closure_reason=REASON,
            closure_boundary=BOUNDARY,
        )
        resumed = suspended.with_status(BranchStatus.ACTIVE)
        self.assertEqual(resumed.closure_reason, REASON)
        self.assertEqual(resumed.closure_boundary, BOUNDARY)

    def test_round_trip(self):
        branch = make_branch(closure_reason=REASON, closure_boundary=BOUNDARY)
        restored = Branch.from_dict(branch.to_dict())
        self.assertEqual(restored, branch)

    def test_a_record_written_before_the_fields_existed_still_loads(self):
        # Two campaigns are persisted under workspace/campaigns; making these
        # fields required would have made both unreadable.
        payload = make_branch().to_dict()
        payload.pop("closure_reason")
        payload.pop("closure_boundary")
        restored = Branch.from_dict(payload)
        self.assertIsNone(restored.closure_reason)
        self.assertIsNone(restored.closure_boundary)

    def test_unknown_keys_are_still_fatal(self):
        # The optional set must not become a hole that swallows typos.
        payload = make_branch().to_dict()
        payload["closure_boundry"] = "typo"
        with self.assertRaises(CampaignModelError):
            Branch.from_dict(payload)


class ApproximationClaims(unittest.TestCase):
    def spec(self, **overrides) -> ApproximationSpec:
        base = dict(
            exact="the full resolvent",
            approximate="its second-order expansion",
            regime="epsilon << 1",
            order="O(epsilon^3)",
        )
        base.update(overrides)
        return ApproximationSpec(**base)

    def test_approximation_requires_a_spec(self):
        with self.assertRaises(CampaignModelError) as ctx:
            make_claim(claim_type=ClaimType.APPROXIMATION)
        self.assertIn("requires an ApproximationSpec", str(ctx.exception))

    def test_other_claim_types_may_not_carry_a_spec(self):
        with self.assertRaises(CampaignModelError):
            make_claim(claim_type=ClaimType.UNIVERSAL, approximation=self.spec())

    def test_missing_error_bound_generates_an_open_goal(self):
        # The whole point of the type: the physics just produced a
        # mathematics problem, and it becomes schedulable rather than prose.
        claim = make_claim(
            claim_type=ClaimType.APPROXIMATION, approximation=self.spec()
        )
        self.assertEqual(len(claim.unresolved_obligations), 1)
        obligation = claim.unresolved_obligations[0]
        self.assertIn("rigorous error bound", obligation)
        self.assertIn("epsilon << 1", obligation)
        self.assertIn("O(epsilon^3)", obligation)

    def test_a_stated_bound_generates_nothing(self):
        claim = make_claim(
            claim_type=ClaimType.APPROXIMATION,
            approximation=self.spec(error_bound="|R| <= C epsilon^3, C = 4.1"),
        )
        self.assertEqual(claim.unresolved_obligations, ())
        self.assertTrue(claim.approximation.is_rigorous)

    def test_the_obligation_is_not_duplicated(self):
        spec = self.spec()
        claim = make_claim(
            claim_type=ClaimType.APPROXIMATION,
            approximation=spec,
            unresolved_obligations=(spec.open_obligation(),),
        )
        self.assertEqual(len(claim.unresolved_obligations), 1)

    def test_existing_obligations_survive(self):
        claim = make_claim(
            claim_type=ClaimType.APPROXIMATION,
            approximation=self.spec(),
            unresolved_obligations=("Show the expansion converges.",),
        )
        self.assertEqual(len(claim.unresolved_obligations), 2)
        self.assertIn("Show the expansion converges.", claim.unresolved_obligations)

    def test_round_trip(self):
        claim = make_claim(
            claim_type=ClaimType.APPROXIMATION,
            approximation=self.spec(error_bound="|R| <= C epsilon^3"),
        )
        self.assertEqual(Claim.from_dict(claim.to_dict()), claim)

    def test_regimes_are_distinguished_by_fingerprint(self):
        # Same quantity, different regime: two claims, not one.
        near = make_claim(
            claim_type=ClaimType.APPROXIMATION, approximation=self.spec()
        )
        far = make_claim(
            claim_type=ClaimType.APPROXIMATION,
            approximation=self.spec(regime="epsilon >> 1"),
        )
        self.assertNotEqual(near.fingerprint(), far.fingerprint())

    def test_fingerprints_of_ordinary_claims_are_unchanged(self):
        # A persisted claim carries its fingerprint and `from_dict` verifies
        # it against a recomputation, so adding an unconditional key would
        # have made every stored claim unreadable. Pinned against the exact
        # payload the fingerprint had before this change.
        claim = make_claim()
        expected = canonical_sha256(
            {
                "statement": claim.statement,
                "domain": claim.domain,
                "quantifiers": list(claim.quantifiers),
                "assumptions": list(claim.assumptions),
                "tolerance": claim.tolerance,
                "units": claim.units,
                "scope": claim.scope,
            }
        )
        self.assertEqual(claim.fingerprint(), expected)

    def test_a_claim_written_before_the_field_existed_still_loads(self):
        payload = make_claim().to_dict()
        payload.pop("approximation")
        self.assertIsNone(Claim.from_dict(payload).approximation)


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# The reducer and the proposer-facing notes
# ---------------------------------------------------------------------------

from core.campaign_executor import build_portfolio_context  # noqa: E402
from core.campaign_models import (  # noqa: E402
    Actor,
    Campaign,
    EventEnvelope,
)
from core.campaign_policy import CampaignState, replay_events  # noqa: E402

SHA = "b" * 64
LEDGER_CAMPAIGN = "cmp_bnd-0001"


def _budget() -> BudgetVector:
    return BudgetVector(
        cycles=10,
        model_calls=40,
        wall_seconds=3600,
        execution_seconds=1800,
        human_interventions=2,
        remote_jobs=4,
    )


class LedgerBuilder:
    """Chained, validated envelopes without touching the filesystem."""

    def __init__(self):
        self.events: list[EventEnvelope] = []

    def add(self, event_type: str, payload: dict) -> None:
        sequence = len(self.events) + 1
        self.events.append(
            EventEnvelope.create(
                event_id=f"evt_b{sequence:04d}",
                campaign_id=LEDGER_CAMPAIGN,
                sequence=sequence,
                event_type=event_type,
                occurred_at=TS,
                source_commit=COMMIT,
                actor=Actor.SYSTEM,
                payload=payload,
                previous_event_sha256=(
                    self.events[-1].event_sha256 if self.events else None
                ),
            )
        )

    def state(self) -> CampaignState:
        return replay_events(self.events)


def seeded(branch_status_events: list[dict]) -> CampaignState:
    builder = LedgerBuilder()
    builder.add(
        "CAMPAIGN_CREATED",
        {
            "campaign": Campaign(
                campaign_id=LEDGER_CAMPAIGN,
                created_at=TS,
                source_commit=COMMIT,
                objective="Decide whether the lower bound holds.",
                success_definition="Every deliverable has credible evidence.",
                deliverables=("lower bound",),
                frozen_resources={"brief.md": SHA},
                allowed_evidence_classes=(EvidenceKind.SYMBOLIC,),
                budget=_budget(),
            ).to_dict()
        },
    )
    builder.add("CAMPAIGN_STATUS_CHANGED", {"status": "ACTIVE"})
    builder.add(
        "BRANCH_CREATED",
        {"branch": make_branch(campaign_id=LEDGER_CAMPAIGN).to_dict()},
    )
    for payload in branch_status_events:
        builder.add("BRANCH_STATUS_CHANGED", {**payload})
    return builder.state()


class ReducerCarriesTheClosure(unittest.TestCase):
    BRANCH = "brn_alpha-0001"

    def test_terminal_status_keeps_reason_and_boundary(self):
        # The reason was always in the ledger; the reducer used to drop it,
        # so nothing downstream could read it without replaying events.
        state = seeded(
            [
                {"branch_id": self.BRANCH, "status": "ADMISSIBLE"},
                {"branch_id": self.BRANCH, "status": "ACTIVE"},
                {
                    "branch_id": self.BRANCH,
                    "status": "EXHAUSTED",
                    "reason": REASON,
                    "boundary": BOUNDARY,
                },
            ]
        )
        branch = state.branches[self.BRANCH]
        self.assertIs(branch.status, BranchStatus.EXHAUSTED)
        self.assertEqual(branch.closure_reason, REASON)
        self.assertEqual(branch.closure_boundary, BOUNDARY)

    def test_activation_reason_is_not_a_closure(self):
        # Activations carry a reason too. Recording it as a closure would put
        # activation prose into the forbidden-family notes.
        state = seeded(
            [
                {"branch_id": self.BRANCH, "status": "ADMISSIBLE"},
                {
                    "branch_id": self.BRANCH,
                    "status": "ACTIVE",
                    "reason": "highest information gain this round",
                },
            ]
        )
        self.assertIsNone(state.branches[self.BRANCH].closure_reason)

    def test_closure_without_a_boundary_is_normal(self):
        state = seeded(
            [
                {"branch_id": self.BRANCH, "status": "ADMISSIBLE"},
                {"branch_id": self.BRANCH, "status": "ACTIVE"},
                {
                    "branch_id": self.BRANCH,
                    "status": "EXHAUSTED",
                    "reason": REASON,
                },
            ]
        )
        branch = state.branches[self.BRANCH]
        self.assertEqual(branch.closure_reason, REASON)
        self.assertIsNone(branch.closure_boundary)


class ExhaustedNotes(unittest.TestCase):
    def test_notes_expose_reason_and_boundary(self):
        state = CampaignState(
            branches={
                "brn_alpha-0001": make_branch(
                    status=BranchStatus.EXHAUSTED,
                    closure_reason=REASON,
                    closure_boundary=BOUNDARY,
                )
            }
        )
        notes = state.exhausted_method_notes()
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["method_family"], "convexity")
        self.assertEqual(notes[0]["reason"], REASON)
        self.assertEqual(notes[0]["boundary"], BOUNDARY)
        self.assertEqual(notes[0]["status"], "EXHAUSTED")

    def test_live_branches_are_not_listed(self):
        state = CampaignState(
            branches={"brn_alpha-0001": make_branch(status=BranchStatus.ACTIVE)}
        )
        self.assertEqual(state.exhausted_method_notes(), ())

    def test_notes_are_ordered_for_reproducible_prompts(self):
        state = CampaignState(
            branches={
                "brn_alpha-0002": make_branch(
                    branch_id="brn_alpha-0002",
                    status=BranchStatus.CLOSED,
                    closure_reason=REASON,
                ),
                "brn_alpha-0001": make_branch(
                    branch_id="brn_alpha-0001",
                    status=BranchStatus.REFUTED,
                    closure_reason=REASON,
                ),
            }
        )
        ids = [note["branch_id"] for note in state.exhausted_method_notes()]
        self.assertEqual(ids, ["brn_alpha-0001", "brn_alpha-0002"])

    def test_the_hard_gate_list_is_kept_alongside(self):
        # The gate consumes bare family names and must not start depending on
        # prose, so the notes are added rather than substituted.
        state = CampaignState(
            campaign=Campaign(
                campaign_id=LEDGER_CAMPAIGN,
                created_at=TS,
                source_commit=COMMIT,
                objective="Decide whether the lower bound holds.",
                success_definition="Every deliverable has credible evidence.",
                deliverables=("lower bound",),
                frozen_resources={"brief.md": SHA},
                allowed_evidence_classes=(EvidenceKind.SYMBOLIC,),
                budget=_budget(),
            ),
            branches={
                "brn_alpha-0001": make_branch(
                    status=BranchStatus.EXHAUSTED,
                    closure_reason=REASON,
                    closure_boundary=BOUNDARY,
                )
            },
        )
        context = build_portfolio_context(state)
        self.assertEqual(context["forbidden_method_families"], ["convexity"])
        self.assertEqual(len(context["exhausted_method_notes"]), 1)
        self.assertEqual(
            context["exhausted_method_notes"][0]["boundary"], BOUNDARY
        )
