"""Automatic trajectory metrics computed from a campaign ledger (H3 adapter).

The frozen Research Trajectory Benchmark computes observable-process metrics
from its own run graph; its protocol and fingerprint must not change.  This
module computes the campaign-side analogues of those metrics **only from the
replayed campaign state**, so ASTRA 2.0 cells can sit beside the frozen
runner's control cells (``full-vnext1``, ``full-linear``) in the H3 pilot.

Honesty rules carried over from `RESEARCH_TRAJECTORY_BENCHMARK.md`:

- metrics are auditable process facts, never quality judgments — blinded
  experts (G4) remain the arbiter of scientific depth and usefulness;
- nothing is collapsed into a single score;
- the instruments differ across architectures (ledger versus run graph), so
  the comparison report must label these as campaign-side analogues, not
  identical measurements.

Definitions (deterministic, derived from the ledger only):

- ``credible_evidence_episodes``: episodes whose recorded evidence has a
  decisive scientific outcome (SUPPORTS or SCIENTIFIC_REFUTATION) at
  strength SCOPED or better.
- ``autonomous_loop_yield``: credible episodes / completed episodes.
- ``operational_failure_rate``: episodes with operation FAILED / completed.
- ``hypothesis_non_repetition``: distinct tested claim fingerprints /
  completed episodes (anti-loop check, exactly as in the frozen suite).
- ``recovery_rate``: among non-decisive episodes (claim NOT_TESTED or
  INCONCLUSIVE) that have a successor, the fraction whose next episode is
  decisive (claim SUPPORTED or REFUTED).
- ``branch_preservation``: branches recorded beyond the first — explicit
  alternatives retained as first-class records.
- ``evidence_per_model_call``: credible episodes / model calls spent.

No model, network, MCP, or remote calls.
"""
from __future__ import annotations

from typing import Any

from core.campaign_models import (
    BranchStatus,
    ClaimStatus,
    EvidenceOutcome,
    EvidenceStrength,
    OperationStatus,
)
from core.campaign_policy import CampaignState

_DECISIVE_OUTCOMES = frozenset(
    {EvidenceOutcome.SUPPORTS, EvidenceOutcome.SCIENTIFIC_REFUTATION}
)
_CREDIBLE_STRENGTHS = frozenset(
    {
        EvidenceStrength.SCOPED,
        EvidenceStrength.CORROBORATED,
        EvidenceStrength.CERTIFIED,
    }
)
_DECISIVE_CLAIM_STATUSES = frozenset(
    {ClaimStatus.SUPPORTED, ClaimStatus.REFUTED}
)
_NON_DECISIVE_CLAIM_STATUSES = frozenset(
    {ClaimStatus.NOT_TESTED, ClaimStatus.INCONCLUSIVE}
)


def _episode_is_credible(state: CampaignState, episode) -> bool:
    for evidence_id in episode.evidence_refs:
        evidence = state.evidence.get(evidence_id)
        if evidence is None:
            continue
        if (
            evidence.outcome in _DECISIVE_OUTCOMES
            and evidence.strength in _CREDIBLE_STRENGTHS
        ):
            return True
    return False


def campaign_trajectory_metrics(state: CampaignState) -> dict[str, Any]:
    """Campaign-side analogues of the frozen trajectory metrics."""
    episodes = list(state.episodes.values())  # ledger order
    completed = len(episodes)

    credible = sum(
        1 for episode in episodes if _episode_is_credible(state, episode)
    )
    operational_failures = sum(
        1
        for episode in episodes
        if episode.operation_status is OperationStatus.FAILED
    )

    fingerprints: set[str] = set()
    for episode in episodes:
        for claim_id in episode.claim_refs:
            claim = state.claims.get(claim_id)
            if claim is not None:
                fingerprints.add(claim.fingerprint())

    recovery_opportunities = 0
    recoveries = 0
    for index, episode in enumerate(episodes[:-1]):
        if episode.claim_status in _NON_DECISIVE_CLAIM_STATUSES:
            recovery_opportunities += 1
            if episodes[index + 1].claim_status in _DECISIVE_CLAIM_STATUSES:
                recoveries += 1

    refutations = sum(
        1
        for evidence in state.evidence.values()
        if evidence.outcome is EvidenceOutcome.SCIENTIFIC_REFUTATION
    )

    branch_statuses: dict[str, int] = {}
    for branch in state.branches.values():
        branch_statuses[branch.status.value] = (
            branch_statuses.get(branch.status.value, 0) + 1
        )

    decision_rules: dict[str, int] = {}
    for decision in state.decisions.values():
        rule = str(decision.policy_result.get("rule") or "unknown")
        decision_rules[rule] = decision_rules.get(rule, 0) + 1

    model_calls = state.spent.model_calls
    return {
        "episodes_completed": completed,
        "credible_evidence_episodes": credible,
        "autonomous_loop_yield": (credible / completed) if completed else None,
        "operational_failures": operational_failures,
        "operational_failure_rate": (
            (operational_failures / completed) if completed else None
        ),
        "distinct_claim_fingerprints": len(fingerprints),
        "hypothesis_non_repetition": (
            (len(fingerprints) / completed) if completed else None
        ),
        "recovery_opportunities": recovery_opportunities,
        "recoveries": recoveries,
        "recovery_rate": (
            (recoveries / recovery_opportunities)
            if recovery_opportunities
            else None
        ),
        "scientific_refutations": refutations,
        "branches_recorded": len(state.branches),
        "branch_preservation": max(0, len(state.branches) - 1),
        "branch_statuses": dict(sorted(branch_statuses.items())),
        "decisions_recorded": len(state.decisions),
        "decision_rules": dict(sorted(decision_rules.items())),
        "model_calls": model_calls,
        "wall_seconds": state.spent.wall_seconds,
        "execution_seconds": state.spent.execution_seconds,
        "evidence_per_model_call": (
            (credible / model_calls) if model_calls else None
        ),
        "goal_coverage": (
            state.goal_coverage().value if state.campaign else None
        ),
        "campaign_status": (
            state.campaign.status.value if state.campaign else None
        ),
        "instrument": "campaign-ledger-v1 (analogue of frozen trajectory metrics; not the identical instrument)",
    }
