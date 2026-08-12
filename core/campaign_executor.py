"""Stage 2: the atomic ASTRA cycle wrapped as a campaign Episode executor.

The cycle itself is untouched: this module builds the cycle request from
campaign state, runs the existing worker through an injectable
``cycle_runner`` (the real ``_do_cycle`` is only the default), and
transcribes the outcome into append-only ledger events — budget charges,
Evidence, the Episode with its five separate status axes, and the live
promotion of portfolio alternatives to PROPOSED branch records gated by the
deterministic admissibility policy.

Epistemic mapping (documented, deterministic):

- ``API_ERROR``   -> operation FAILED, claim NOT_TESTED, no evidence
                     (nothing executed; a provider failure proves nothing).
- ``CODE_ERROR``  -> operation FAILED, claim NOT_TESTED, evidence outcome
                     OPERATIONAL_ERROR.  A traceback never refutes a claim.
                     Finer failure classes (INVALID_VALIDATOR,
                     NUMERICAL_INSTABILITY, FORMALIZATION_FAILURE) will be
                     mapped when the audit trail exposes them explicitly;
                     OPERATIONAL_ERROR is the conservative default.
- ``REFUTED``     -> operation COMPLETED, claim REFUTED, evidence outcome
                     SCIENTIFIC_REFUTATION.
- ``VALIDATED``   -> operation COMPLETED, claim SUPPORTED, evidence SUPPORTS.
- ``WEAK_PASS``   -> operation COMPLETED, claim INCONCLUSIVE, evidence
                     INCONCLUSIVE.
- anything else (``PARTIAL``, unknown) -> operation FAILED, claim
                     NOT_TESTED, no evidence.

Evidence strength is SCOPED only when the independent code review APPROVED
the validator and the operation completed; PRELIMINARY otherwise.  Budget
accounting fails closed: a real overspend is charged up to the remaining
limit with the actual amount preserved in the event reason, and the run
report raises the ``budget_exhausted`` flag for the controller stage.

No MCP, GUI, ASTRUM, or production changes.  Tests drive everything with a
fake ``cycle_runner``; no model or network calls are required.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from core.campaign_models import (
    Actor,
    BUDGET_DIMENSIONS,
    Branch,
    BranchStatus,
    BudgetVector,
    CampaignStatus,
    Claim,
    ClaimStatus,
    Episode,
    EvidenceOutcome,
    EvidenceStrength,
    GoalCoverage,
    OperationStatus,
    REQUIRED_EVIDENCE_METADATA,
    SCHEMA_VERSION,
    new_record_id,
    utc_now_iso,
)
from core.campaign_policy import (
    CampaignState,
    evaluate_branch_admissibility,
)
from core.campaign_portfolio import (
    Portfolio,
    PortfolioError,
    portfolio_to_records,
)
from core.campaign_store import CampaignStore


class CampaignExecutorError(RuntimeError):
    """The executor refused to run or record an episode."""


@dataclass(frozen=True)
class OutcomeAxes:
    """The five-axis projection of one cycle result (never collapsed)."""

    operation_status: OperationStatus
    claim_status: ClaimStatus
    evidence_outcome: EvidenceOutcome | None
    evidence_strength: EvidenceStrength | None
    goal_coverage: GoalCoverage


@dataclass(frozen=True)
class EpisodeRunReport:
    episode_id: str
    axes: OutcomeAxes
    tested_claim_ids: tuple[str, ...] = ()
    evidence_id: str | None = None
    promoted_branch_ids: tuple[str, ...] = ()
    rejected_branch_ids: tuple[str, ...] = ()
    budget_exhausted: bool = False
    notes: tuple[str, ...] = ()
    checkpoint_path: str | None = None


def map_cycle_outcome(result: Mapping[str, Any]) -> OutcomeAxes:
    """Deterministic five-axis projection of a cycle result dict."""
    status = str(result.get("status") or "").upper()
    scientific = str(result.get("scientific_status") or "").upper()
    review = result.get("code_review") or {}
    reviewed = str(review.get("status") or "").upper() == "APPROVED"
    goal_raw = str(
        ((result.get("goal_coverage") or {}).get("status")) or ""
    ).lower()
    if goal_raw == "complete":
        goal = GoalCoverage.COMPLETE
    elif goal_raw == "partial":
        goal = GoalCoverage.PARTIAL
    else:
        goal = GoalCoverage.NONE
    strength = EvidenceStrength.SCOPED if reviewed else EvidenceStrength.PRELIMINARY

    if status == "API_ERROR":
        return OutcomeAxes(
            OperationStatus.FAILED, ClaimStatus.NOT_TESTED, None, None, goal
        )
    if status == "CODE_ERROR":
        return OutcomeAxes(
            OperationStatus.FAILED,
            ClaimStatus.NOT_TESTED,
            EvidenceOutcome.OPERATIONAL_ERROR,
            EvidenceStrength.PRELIMINARY,
            goal,
        )
    if status == "REFUTED" or scientific in {"ATOMIC_REFUTED", "REFUTED"}:
        return OutcomeAxes(
            OperationStatus.COMPLETED,
            ClaimStatus.REFUTED,
            EvidenceOutcome.SCIENTIFIC_REFUTATION,
            strength,
            goal,
        )
    if status == "VALIDATED" or scientific in {"ATOMIC_VALIDATED", "VALIDATED"}:
        return OutcomeAxes(
            OperationStatus.COMPLETED,
            ClaimStatus.SUPPORTED,
            EvidenceOutcome.SUPPORTS,
            strength,
            goal,
        )
    if status == "WEAK_PASS":
        return OutcomeAxes(
            OperationStatus.COMPLETED,
            ClaimStatus.INCONCLUSIVE,
            EvidenceOutcome.INCONCLUSIVE,
            EvidenceStrength.PRELIMINARY,
            goal,
        )
    return OutcomeAxes(
        OperationStatus.FAILED, ClaimStatus.NOT_TESTED, None, None, goal
    )


def estimate_model_calls(result: Mapping[str, Any]) -> int:
    """Deterministic lower-bound estimate of observable model calls."""
    deliberation = result.get("deliberation") or {}
    proposals = len(deliberation.get("proposals") or [])
    critiques = len(deliberation.get("critiques") or [])
    merge = 1 if proposals > 1 else 0
    reviews = len(result.get("code_review_history") or []) or 1
    analysis = result.get("analysis") or {}
    analysts = len(analysis.get("ensemble") or []) or 1
    translator = 1
    return max(1, proposals + critiques + merge + translator + reviews + analysts)


def build_portfolio_context(state: CampaignState) -> dict[str, Any]:
    """Campaign context for the synthesis portfolio, including R4 families."""
    campaign = state.require_campaign()
    return {
        "deliverables": list(state.unresolved_deliverables()),
        "allowed_evidence_kinds": [
            item.value for item in campaign.allowed_evidence_classes
        ],
        "forbidden_method_families": list(state.exhausted_method_families()),
    }


def build_episode_request(
    state: CampaignState,
    branch: Branch,
    *,
    cycle_timeout_seconds: int | None = None,
) -> dict[str, Any]:
    """The request dict handed to the atomic cycle for one episode."""
    campaign = state.require_campaign()
    lines = [branch.direction]
    for claim_id in branch.claim_refs:
        claim = state.claims.get(claim_id)
        if claim is None:
            continue
        lines.append("")
        lines.append("ATOMIC CLAIM UNDER TEST:")
        lines.append(claim.statement)
        if claim.unresolved_obligations:
            lines.append("CRUX / NEXT DISCRIMINATING OBLIGATION:")
            lines.extend(f"- {item}" for item in claim.unresolved_obligations)
        break
    if cycle_timeout_seconds is None:
        remaining = state.remaining_budget()
        cycle_timeout_seconds = max(
            60, min(branch.budget.wall_seconds, remaining.wall_seconds)
        )
    return {
        "action": "cycle",
        "intuition": "\n".join(lines),
        "objective": campaign.objective,
        "cycle_timeout_seconds": int(cycle_timeout_seconds),
        "portfolio_context": build_portfolio_context(state),
    }


def _charge_budget(
    store: CampaignStore,
    state: CampaignState,
    charges: Mapping[str, int],
    *,
    occurred_at: str,
) -> tuple[bool, list[str]]:
    """Charge actual spend, clamping to the remaining limit fail-closed.

    Returns (budget_exhausted, notes).  A clamped charge keeps the real
    amount in the event reason so the ledger never under-reports silently.
    """
    campaign = state.require_campaign()
    spent = state.spent
    exhausted = False
    notes: list[str] = []
    for dimension in BUDGET_DIMENSIONS:
        amount = int(charges.get(dimension, 0) or 0)
        if amount <= 0:
            continue
        remaining = getattr(campaign.budget, dimension) - getattr(
            spent, dimension
        )
        if remaining <= 0:
            exhausted = True
            notes.append(
                f"budget dimension {dimension} already exhausted; "
                f"actual spend {amount} not chargeable"
            )
            continue
        charged = min(amount, remaining)
        reason = f"episode spend actual={amount}"
        if charged < amount:
            exhausted = True
            reason += f" clamped_to_remaining={charged}"
            notes.append(
                f"budget dimension {dimension} exhausted by this episode "
                f"(actual {amount}, charged {charged})"
            )
        store.append_event(
            event_type="BUDGET_CHARGED",
            payload={
                "dimension": dimension,
                "amount": charged,
                "reason": reason,
            },
            actor=Actor.SYSTEM,
            occurred_at=occurred_at,
        )
        spent = spent.charge(dimension, charged)
    return exhausted, notes


def _write_artifacts(
    store: CampaignStore, episode_id: str, result: Mapping[str, Any]
) -> dict[str, str]:
    """Persist validator code and stdout; return relpath -> sha256."""
    artifacts: dict[str, str] = {}
    execution = result.get("execution_result") or {}
    payloads = {
        "validator.py": result.get("code"),
        "stdout.txt": execution.get("stdout") or result.get("stdout"),
    }
    for name, content in payloads.items():
        if not isinstance(content, str) or not content.strip():
            continue
        relpath = f"artifacts/{episode_id}/{name}"
        target = store.campaign_dir / "artifacts" / episode_id / name
        target.parent.mkdir(parents=True, exist_ok=True)
        data = content.encode("utf-8")
        target.write_bytes(data)
        artifacts[relpath] = hashlib.sha256(data).hexdigest()
    return artifacts


def _resolve_tested_claims(
    store: CampaignStore,
    state: CampaignState,
    branch: Branch,
    portfolio: Portfolio | None,
    *,
    id_factory: Callable[[str], str],
    occurred_at: str,
    source_commit: str,
) -> tuple[tuple[str, ...], list[tuple[Claim, Branch]], list[str]]:
    """Identify the claim the cycle actually tested; record it if new.

    Returns (tested claim ids, alternative (Claim, Branch) records, notes).
    """
    notes: list[str] = []
    campaign = state.require_campaign()
    if portfolio is None:
        return branch.claim_refs, [], notes
    try:
        records = portfolio_to_records(
            portfolio,
            campaign,
            source_commit=source_commit,
            created_at=occurred_at,
            id_factory=id_factory,
            parent_branch_id=branch.branch_id,
        )
    except PortfolioError as exc:
        notes.append(f"portfolio not convertible to records: {exc}")
        return branch.claim_refs, [], notes
    selected_claim, _unused_branch = records[0]
    fingerprint = selected_claim.fingerprint()
    existing_id = next(
        (
            claim_id
            for claim_id, claim in state.claims.items()
            if claim.fingerprint() == fingerprint
        ),
        None,
    )
    if existing_id is not None:
        return (existing_id,), list(records[1:]), notes
    store.append_event(
        event_type="CLAIM_RECORDED",
        payload={
            "claim": selected_claim.to_dict(),
            "branch_id": branch.branch_id,
        },
        actor=Actor.SYSTEM,
        occurred_at=occurred_at,
    )
    return (selected_claim.claim_id,), list(records[1:]), notes


def _promote_alternatives(
    store: CampaignStore,
    alternatives: list[tuple[Claim, Branch]],
    *,
    episode_id: str,
    forbidden_families: tuple[str, ...],
    occurred_at: str,
) -> tuple[list[str], list[str], list[str]]:
    """Record minority candidates as PROPOSED branches and gate them.

    Every alternative is preserved as a record; the deterministic hard gates
    (plus the R4 forbidden-family rule) decide ADMISSIBLE versus REJECTED.
    """
    from dataclasses import replace

    promoted: list[str] = []
    rejected: list[str] = []
    notes: list[str] = []
    forbidden = {item.lower() for item in forbidden_families}
    for claim, branch in alternatives:
        # Repeated synthesis portfolios must not pile up duplicate branches:
        # an alternative whose method family and claim fingerprint are
        # already tracked by an existing branch is skipped, not re-created.
        state = store.replay().state
        fingerprint = claim.fingerprint()
        already = next(
            (
                other.branch_id
                for other in state.branches.values()
                if other.method_family == branch.method_family
                and any(
                    state.claims[claim_id].fingerprint() == fingerprint
                    for claim_id in other.claim_refs
                    if claim_id in state.claims
                )
            ),
            None,
        )
        if already is not None:
            notes.append(
                f"alternative {branch.method_family} already tracked by "
                f"{already}; skipped"
            )
            continue
        branch = replace(branch, parent_episode_id=episode_id)
        store.append_event(
            event_type="CLAIM_RECORDED",
            payload={"claim": claim.to_dict()},
            actor=Actor.SYSTEM,
            occurred_at=occurred_at,
        )
        store.append_event(
            event_type="BRANCH_CREATED",
            payload={"branch": branch.to_dict()},
            actor=Actor.SYSTEM,
            occurred_at=occurred_at,
        )
        state = store.replay().state
        gates = evaluate_branch_admissibility(
            state, state.branches[branch.branch_id]
        )
        family_forbidden = branch.method_family.lower() in forbidden
        admissible = gates.passed and not family_forbidden
        reason = json.dumps(
            {
                "hard_gates": gates.to_dict(),
                "forbidden_family": family_forbidden,
            },
            sort_keys=True,
        )
        store.append_event(
            event_type="BRANCH_STATUS_CHANGED",
            payload={
                "branch_id": branch.branch_id,
                "status": (
                    BranchStatus.ADMISSIBLE.value
                    if admissible
                    else BranchStatus.REJECTED.value
                ),
                "reason": reason[:2000],
            },
            actor=Actor.SYSTEM,
            occurred_at=occurred_at,
        )
        if admissible:
            promoted.append(branch.branch_id)
        else:
            rejected.append(branch.branch_id)
            if family_forbidden:
                notes.append(
                    f"alternative {branch.branch_id} rejected: method family "
                    f"{branch.method_family} is forbidden (R4)"
                )
    return promoted, rejected, notes


def record_episode_result(
    store: CampaignStore,
    branch_id: str,
    result: Mapping[str, Any],
    *,
    request: Mapping[str, Any] | None = None,
    evidence_metadata: Mapping[str, Any] | None = None,
    id_factory: Callable[[str], str] = new_record_id,
    now_iso: Callable[[], str] = utc_now_iso,
) -> EpisodeRunReport:
    """Transcribe one finished cycle result into ledger events."""
    if not isinstance(result, Mapping):
        raise CampaignExecutorError("Cycle result must be a mapping")
    replayed = store.replay()
    state = replayed.state
    campaign = state.require_campaign()
    if campaign.status is not CampaignStatus.ACTIVE:
        raise CampaignExecutorError(
            f"Episodes require an ACTIVE campaign; status is "
            f"{campaign.status.value}"
        )
    branch = state.branches.get(branch_id)
    if branch is None:
        raise CampaignExecutorError(f"Unknown branch: {branch_id!r}")
    if branch.status is not BranchStatus.ACTIVE:
        raise CampaignExecutorError(
            f"Episodes may only run on the ACTIVE branch; {branch_id} is "
            f"{branch.status.value}"
        )

    occurred_at = now_iso()
    axes = map_cycle_outcome(result)
    forbidden_families = state.exhausted_method_families()
    notes: list[str] = []

    timings_raw = result.get("timings") or {}
    timings = {
        str(phase): float(seconds)
        for phase, seconds in timings_raw.items()
        if isinstance(seconds, (int, float)) and not isinstance(seconds, bool)
    }
    wall_seconds = int(round(sum(timings.values())))
    execution_seconds = int(round(timings.get("execute", 0.0)))
    model_calls = estimate_model_calls(result)
    charges = {
        "cycles": 1,
        "model_calls": model_calls,
        "wall_seconds": wall_seconds,
        "execution_seconds": execution_seconds,
    }
    budget_exhausted, charge_notes = _charge_budget(
        store, state, charges, occurred_at=occurred_at
    )
    notes.extend(charge_notes)

    portfolio_data = (result.get("deliberation") or {}).get("portfolio")
    portfolio: Portfolio | None = None
    if isinstance(portfolio_data, Mapping):
        try:
            portfolio = Portfolio.from_dict(portfolio_data)
        except PortfolioError as exc:
            notes.append(f"recorded portfolio failed re-validation: {exc}")

    state = store.replay().state
    tested_claim_ids, alternatives, claim_notes = _resolve_tested_claims(
        store,
        state,
        branch,
        portfolio,
        id_factory=id_factory,
        occurred_at=occurred_at,
        source_commit=store.source_commit,
    )
    notes.extend(claim_notes)

    episode_id = id_factory("episode")
    evidence_id: str | None = None
    evidence_refs: tuple[str, ...] = ()
    if axes.evidence_outcome is not None and tested_claim_ids:
        kind = branch.evidence_plan.kind
        metadata = dict(evidence_metadata or {})
        missing = [
            key
            for key in REQUIRED_EVIDENCE_METADATA[kind]
            if key not in metadata
        ]
        if missing:
            raise CampaignExecutorError(
                f"{kind.value} evidence requires metadata keys {missing}; "
                "supply evidence_metadata or use an evidence kind without "
                "mandatory metadata"
            )
        state = store.replay().state
        first_claim = state.claims.get(tested_claim_ids[0])
        scope = first_claim.scope if first_claim is not None else branch.direction
        artifacts = _write_artifacts(store, episode_id, result)
        evidence_id = id_factory("evidence")
        store.append_event(
            event_type="EVIDENCE_RECORDED",
            payload={
                "evidence": {
                    "schema_version": SCHEMA_VERSION,
                    "evidence_id": evidence_id,
                    "campaign_id": store.campaign_id,
                    "created_at": occurred_at,
                    "source_commit": store.source_commit,
                    "claim_ids": list(tested_claim_ids),
                    "kind": kind.value,
                    "strength": axes.evidence_strength.value,
                    "scope": scope,
                    "engine": str(
                        result.get("oracle_mode")
                        or result.get("engine")
                        or "local"
                    ),
                    "outcome": axes.evidence_outcome.value,
                    "artifact_hashes": artifacts,
                    "independence_links": [],
                    "metadata": metadata,
                }
            },
            actor=Actor.ORACLE,
            occurred_at=occurred_at,
        )
        evidence_refs = (evidence_id,)
    elif axes.evidence_outcome is not None and not tested_claim_ids:
        notes.append(
            "cycle produced an outcome but the branch has no claim to "
            "attach evidence to; evidence skipped"
        )

    request = request or {}
    episode = Episode(
        episode_id=episode_id,
        campaign_id=store.campaign_id,
        branch_id=branch_id,
        created_at=occurred_at,
        source_commit=store.source_commit,
        inputs={
            "intuition": str(
                request.get("intuition") or result.get("intuition") or ""
            ),
            "objective": str(
                request.get("objective") or result.get("objective") or ""
            ),
        },
        providers={
            str(key): str(value)
            for key, value in (result.get("providers") or {}).items()
        },
        actual_models={
            str(key): str(value)
            for key, value in (result.get("actual_models") or {}).items()
        },
        budget=BudgetVector(
            cycles=1,
            model_calls=model_calls,
            wall_seconds=wall_seconds,
            execution_seconds=execution_seconds,
            human_interventions=0,
            remote_jobs=0,
        ),
        timings=timings,
        operation_status=axes.operation_status,
        claim_status=axes.claim_status,
        branch_status=branch.status,
        goal_coverage=axes.goal_coverage,
        claim_refs=tested_claim_ids,
        evidence_refs=evidence_refs,
        artifacts=tuple(
            f"artifacts/{episode_id}/{name}"
            for name in ("validator.py", "stdout.txt")
            if (store.campaign_dir / "artifacts" / episode_id / name).exists()
        ),
    )
    store.append_event(
        event_type="EPISODE_RECORDED",
        payload={"episode": episode.to_dict()},
        actor=Actor.SYSTEM,
        occurred_at=occurred_at,
    )

    promoted, rejected, promo_notes = _promote_alternatives(
        store,
        alternatives,
        episode_id=episode_id,
        forbidden_families=forbidden_families,
        occurred_at=occurred_at,
    )
    notes.extend(promo_notes)

    checkpoint = store.write_checkpoint()
    return EpisodeRunReport(
        episode_id=episode_id,
        axes=axes,
        tested_claim_ids=tested_claim_ids,
        evidence_id=evidence_id,
        promoted_branch_ids=tuple(promoted),
        rejected_branch_ids=tuple(rejected),
        budget_exhausted=budget_exhausted,
        notes=tuple(notes),
        checkpoint_path=str(checkpoint),
    )


async def run_episode(
    store: CampaignStore,
    branch_id: str,
    *,
    cycle_runner: Callable[[dict], Any] | None = None,
    cycle_timeout_seconds: int | None = None,
    evidence_metadata: Mapping[str, Any] | None = None,
    id_factory: Callable[[str], str] = new_record_id,
    now_iso: Callable[[], str] = utc_now_iso,
) -> EpisodeRunReport:
    """Run one bounded episode of the atomic cycle on the ACTIVE branch.

    Fail-closed pre-gates run BEFORE any model call: the campaign must be
    ACTIVE, the branch must be the ACTIVE branch, and the remaining campaign
    budget must cover the branch's cheapest discriminating evidence plan.
    """
    state = store.replay().state
    campaign = state.require_campaign()
    if campaign.status is not CampaignStatus.ACTIVE:
        raise CampaignExecutorError(
            f"Episodes require an ACTIVE campaign; status is "
            f"{campaign.status.value}"
        )
    branch = state.branches.get(branch_id)
    if branch is None:
        raise CampaignExecutorError(f"Unknown branch: {branch_id!r}")
    if branch.status is not BranchStatus.ACTIVE:
        raise CampaignExecutorError(
            f"Episodes may only run on the ACTIVE branch; {branch_id} is "
            f"{branch.status.value}"
        )
    remaining = state.remaining_budget()
    plan_cost = branch.evidence_plan.estimated_cost
    if not remaining.covers(plan_cost):
        raise CampaignExecutorError(
            "Remaining campaign budget does not cover the branch evidence "
            f"plan; remaining={remaining.to_dict()}, "
            f"plan={plan_cost.to_dict()}"
        )

    request = build_episode_request(
        state, branch, cycle_timeout_seconds=cycle_timeout_seconds
    )
    if cycle_runner is None:
        from astra_tool import _do_cycle

        cycle_runner = _do_cycle
    result = await cycle_runner(request)
    if not isinstance(result, Mapping):
        raise CampaignExecutorError(
            f"Cycle runner returned a non-mapping result: {type(result).__name__}"
        )
    return record_episode_result(
        store,
        branch_id,
        result,
        request=request,
        evidence_metadata=evidence_metadata,
        id_factory=id_factory,
        now_iso=now_iso,
    )
