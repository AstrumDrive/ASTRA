"""Stage 5: development-only ``astra_campaign_*`` interfaces.

Plain Python functions over a campaigns root directory (default
``workspace/campaigns``, always ignored by Git).  They compose the layers
built in the previous stages — store, policy, portfolio, executor, decision,
resume — into the five verbs the architecture review reserved for
development use:

- ``astra_campaign_start``      create (and optionally activate) a campaign,
                                seed branches from an initial portfolio, and
                                select the first active branch;
- ``astra_campaign_status``     strictly read-only resume report;
- ``astra_campaign_step``       one episode -> decision -> ledger step;
- ``astra_campaign_stop``       pause or cancel;
- ``astra_campaign_reactivate`` PAUSED -> ACTIVE after human review;
- ``astra_campaign_list``       enumerate campaigns under the root.

**These interfaces must not be registered in the production MCP before
acceptance** (`ASTRA2_ACCEPTANCE.md`).  This module never imports
``mcp_server`` and a regression test pins both facts.  Every function opens
its own store and releases the single-writer lock before returning, so
sequential calls from different sessions never deadlock.  No model calls
happen here; ``astra_campaign_step`` only reaches models through the real
cycle when no ``cycle_runner`` is injected.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping

from core.campaign_decision import (
    CampaignDecisionError,
    StepReport,
    campaign_step,
    select_initial_branch,
)
from core.campaign_models import (
    Actor,
    BranchStatus,
    BudgetVector,
    Campaign,
    CampaignStatus,
    EvidenceKind,
    CampaignModelError,
    new_record_id,
    utc_now_iso,
    validate_record_id,
)
from core.campaign_policy import evaluate_branch_admissibility
from core.campaign_portfolio import (
    Portfolio,
    PortfolioError,
    portfolio_to_records,
)
from core.campaign_resume import resume_campaign
from core.campaign_store import CampaignStore
from core.campaign_executor import EpisodeRunReport

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAMPAIGNS_ROOT = ROOT / "workspace" / "campaigns"


class CampaignApiError(RuntimeError):
    """A development interface refused an invalid request."""


_HEX_RE = re.compile(r"^[0-9a-f]{7,40}$")


def _git_dir(root: Path) -> Path | None:
    """Resolve ``root``'s git directory, handling the worktree/submodule
    ``gitdir: <path>`` file form. Pure filesystem, never a subprocess."""
    dot_git = root / ".git"
    if dot_git.is_dir():
        return dot_git
    if dot_git.is_file():
        try:
            text = dot_git.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if text.startswith("gitdir:"):
            target = text[len("gitdir:") :].strip()
            path = Path(target) if os.path.isabs(target) else (root / target).resolve()
            return path if path.exists() else None
    return None


def _read_head_commit(root: Path) -> str | None:
    """Return HEAD's commit id by reading git ref files directly, or ``None``.

    Deliberately does NOT shell out to ``git``. A ``git`` subprocess on the
    MCP server's hot path can wedge indefinitely in this environment — a
    ``git rev-parse HEAD`` was observed stuck for 30+ minutes despite a 10 s
    timeout, hanging every ``astra_campaign_*`` call that funnels through here
    before it touches disk. Reading the ref files is pure local I/O and cannot
    block on a child process, an inherited stdio handle, or a credential
    helper.
    """
    gitdir = _git_dir(root)
    if gitdir is None:
        return None
    # In a linked worktree, loose/packed refs live in the common dir.
    commondir = gitdir
    commondir_file = gitdir / "commondir"
    if commondir_file.is_file():
        try:
            rel = commondir_file.read_text(encoding="utf-8").strip()
            commondir = (
                Path(rel) if os.path.isabs(rel) else (gitdir / rel).resolve()
            )
        except OSError:
            commondir = gitdir
    try:
        head = (gitdir / "HEAD").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not head.startswith("ref:"):
        # Detached HEAD: the file holds the raw object id.
        return head.lower() if _HEX_RE.match(head) else None
    ref = head[len("ref:") :].strip()
    # 1) loose ref, checked in the worktree gitdir then the common dir
    for base in (gitdir, commondir):
        loose = base / ref
        try:
            if loose.is_file():
                sha = loose.read_text(encoding="utf-8").strip()
                if _HEX_RE.match(sha):
                    return sha.lower()
        except OSError:
            pass
    # 2) packed-refs
    try:
        for raw in (commondir / "packed-refs").read_text(
            encoding="utf-8"
        ).splitlines():
            line = raw.strip()
            if not line or line[0] in "#^":
                continue
            parts = line.split(" ", 1)
            if len(parts) == 2 and parts[1].strip() == ref and _HEX_RE.match(parts[0]):
                return parts[0].lower()
    except OSError:
        pass
    return None


def _resolve_source_commit(explicit: str | None) -> str:
    if explicit:
        return explicit
    env = (os.environ.get("ASTRA_SOURCE_COMMIT") or "").strip()
    if env:
        return env
    commit = _read_head_commit(ROOT)
    if commit:
        return commit
    # Last-resort fallback for an exotic git layout the direct reader missed.
    # Never reached in a normal checkout, and hardened so it cannot reproduce
    # the hang above: stdin is /dev/null (git can neither block on nor inherit
    # the MCP stdio transport), interactive prompts and credential UIs are
    # disabled, and the timeout is short.
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
            env={
                **os.environ,
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_OPTIONAL_LOCKS": "0",
                "GCM_INTERACTIVE": "never",
            },
        )
        sha = completed.stdout.strip()
        if _HEX_RE.match(sha):
            return sha.lower()
    except (OSError, subprocess.SubprocessError):
        pass
    raise CampaignApiError(
        "Cannot resolve source_commit: pass it explicitly or set "
        "ASTRA_SOURCE_COMMIT"
    )


def _open_store(
    campaign_id: str, root: Path | str | None, source_commit: str | None
) -> CampaignStore:
    return CampaignStore(
        Path(root) if root is not None else DEFAULT_CAMPAIGNS_ROOT,
        campaign_id,
        source_commit=_resolve_source_commit(source_commit),
    )


def _seed_portfolio_branches(
    store: CampaignStore,
    campaign: Campaign,
    portfolio: Portfolio,
    *,
    id_factory: Callable[[str], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    """Record every candidate as claim + PROPOSED branch, then gate it."""
    records = portfolio_to_records(
        portfolio,
        campaign,
        source_commit=store.source_commit,
        created_at=now_iso(),
        id_factory=id_factory,
    )
    admissible: list[str] = []
    rejected: list[str] = []
    for claim, branch in records:
        occurred_at = now_iso()
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
        store.append_event(
            event_type="BRANCH_STATUS_CHANGED",
            payload={
                "branch_id": branch.branch_id,
                "status": (
                    BranchStatus.ADMISSIBLE.value
                    if gates.passed
                    else BranchStatus.REJECTED.value
                ),
                "reason": f"initial portfolio gates: {gates.to_dict()}"[:2000],
            },
            actor=Actor.SYSTEM,
            occurred_at=occurred_at,
        )
        (admissible if gates.passed else rejected).append(branch.branch_id)
    return {"admissible": admissible, "rejected": rejected}


def astra_campaign_start(
    *,
    objective: str,
    success_definition: str,
    deliverables: list[str],
    allowed_evidence_classes: list[str],
    budget: Mapping[str, int],
    frozen_resources: Mapping[str, str] | None = None,
    initial_portfolio: Mapping[str, Any] | None = None,
    campaign_id: str | None = None,
    activate: bool = True,
    root: Path | str | None = None,
    source_commit: str | None = None,
    id_factory: Callable[[str], str] = new_record_id,
    now_iso: Callable[[], str] = utc_now_iso,
) -> dict[str, Any]:
    """Create a campaign; optionally seed and select its first branch."""
    campaign_id = campaign_id or id_factory("campaign")
    validate_record_id(campaign_id, "campaign")
    store = _open_store(campaign_id, root, source_commit)
    try:
        try:
            campaign = Campaign(
                campaign_id=campaign_id,
                created_at=now_iso(),
                source_commit=store.source_commit,
                objective=objective,
                success_definition=success_definition,
                deliverables=tuple(deliverables),
                frozen_resources=dict(frozen_resources or {}),
                allowed_evidence_classes=tuple(
                    EvidenceKind(item) for item in allowed_evidence_classes
                ),
                budget=BudgetVector.from_dict(budget),
            )
        except (CampaignModelError, ValueError) as exc:
            raise CampaignApiError(f"Invalid campaign definition: {exc}") from exc
        store.append_event(
            event_type="CAMPAIGN_CREATED",
            payload={"campaign": campaign.to_dict()},
            actor=Actor.HUMAN,
            occurred_at=campaign.created_at,
        )
        seeding: dict[str, Any] = {"admissible": [], "rejected": []}
        if activate:
            store.append_event(
                event_type="CAMPAIGN_STATUS_CHANGED",
                payload={"status": CampaignStatus.ACTIVE.value},
                actor=Actor.HUMAN,
                occurred_at=now_iso(),
            )
        if initial_portfolio is not None:
            try:
                portfolio = Portfolio.from_dict(initial_portfolio)
            except PortfolioError as exc:
                raise CampaignApiError(
                    f"Invalid initial portfolio: {exc}"
                ) from exc
            try:
                seeding = _seed_portfolio_branches(
                    store,
                    campaign,
                    portfolio,
                    id_factory=id_factory,
                    now_iso=now_iso,
                )
            except PortfolioError as exc:
                raise CampaignApiError(
                    f"Initial portfolio not convertible: {exc}"
                ) from exc
            if activate and seeding["admissible"]:
                select_initial_branch(
                    store, id_factory=id_factory, now_iso=now_iso
                )
        store.write_checkpoint()
        report = resume_campaign(store, rebuild_checkpoint=False)
        return {"campaign_id": campaign_id, "seeding": seeding,
                **report.to_dict()}
    finally:
        store.close()


def astra_campaign_status(
    campaign_id: str,
    *,
    root: Path | str | None = None,
    source_commit: str | None = None,
) -> dict[str, Any]:
    """Strictly read-only status; never takes the writer lock."""
    store = _open_store(campaign_id, root, source_commit)
    try:
        return resume_campaign(store, rebuild_checkpoint=False).to_dict()
    finally:
        store.close()


def _step_report_to_dict(report: StepReport) -> dict[str, Any]:
    episode: EpisodeRunReport = report.episode
    return {
        "episode_id": episode.episode_id,
        "operation_status": episode.axes.operation_status.value,
        "claim_status": episode.axes.claim_status.value,
        "evidence_outcome": (
            episode.axes.evidence_outcome.value
            if episode.axes.evidence_outcome
            else None
        ),
        "goal_coverage": episode.axes.goal_coverage.value,
        "tested_claim_ids": list(episode.tested_claim_ids),
        "evidence_id": episode.evidence_id,
        "promoted_branch_ids": list(episode.promoted_branch_ids),
        "rejected_branch_ids": list(episode.rejected_branch_ids),
        "budget_exhausted": episode.budget_exhausted,
        "episode_notes": list(episode.notes),
        "decision_rule": report.plan.rule,
        "decisions": [
            {
                "decision_id": decision.decision_id,
                "action": decision.action.value,
                "subject_branch_id": decision.subject_branch_id,
                "reasons": list(decision.reasons),
            }
            for decision in report.plan.decisions
        ],
        "plan_notes": list(report.plan.notes),
        "events_appended": report.events_appended,
    }


async def astra_campaign_step(
    campaign_id: str,
    *,
    root: Path | str | None = None,
    source_commit: str | None = None,
    cycle_runner: Callable[[dict], Any] | None = None,
    model_recommendation: Mapping[str, Any] | None = None,
    evidence_metadata: Mapping[str, Any] | None = None,
    cycle_timeout_seconds: int | None = None,
    id_factory: Callable[[str], str] = new_record_id,
    now_iso: Callable[[], str] = utc_now_iso,
) -> dict[str, Any]:
    """Run one campaign step; auto-selects the first branch when needed."""
    store = _open_store(campaign_id, root, source_commit)
    try:
        report = resume_campaign(store)
        if report.next_action == "select_initial_branch":
            select_initial_branch(store, id_factory=id_factory, now_iso=now_iso)
            report = resume_campaign(store, rebuild_checkpoint=False)
        if report.next_action != "campaign_step":
            raise CampaignApiError(
                f"Campaign {campaign_id} cannot step now; next action is "
                f"{report.next_action!r}"
            )
        try:
            step = await campaign_step(
                store,
                cycle_runner=cycle_runner,
                model_recommendation=model_recommendation,
                evidence_metadata=evidence_metadata,
                cycle_timeout_seconds=cycle_timeout_seconds,
                id_factory=id_factory,
                now_iso=now_iso,
            )
        except CampaignDecisionError as exc:
            raise CampaignApiError(str(exc)) from exc
        status = resume_campaign(store, rebuild_checkpoint=False).to_dict()
        return {"step": _step_report_to_dict(step), "status": status}
    finally:
        store.close()


def astra_campaign_stop(
    campaign_id: str,
    *,
    mode: str = "pause",
    reason: str | None = None,
    root: Path | str | None = None,
    source_commit: str | None = None,
    now_iso: Callable[[], str] = utc_now_iso,
) -> dict[str, Any]:
    """Pause (resumable) or cancel (terminal) a campaign."""
    statuses = {
        "pause": CampaignStatus.PAUSED.value,
        "cancel": CampaignStatus.CANCELLED.value,
    }
    if mode not in statuses:
        raise CampaignApiError(
            f"Unknown stop mode {mode!r}; use 'pause' or 'cancel'"
        )
    store = _open_store(campaign_id, root, source_commit)
    try:
        payload: dict[str, Any] = {"status": statuses[mode]}
        if reason:
            payload["reason"] = str(reason)[:2000]
        try:
            store.append_event(
                event_type="CAMPAIGN_STATUS_CHANGED",
                payload=payload,
                actor=Actor.HUMAN,
                occurred_at=now_iso(),
            )
        except Exception as exc:
            raise CampaignApiError(f"Cannot stop campaign: {exc}") from exc
        store.write_checkpoint()
        return resume_campaign(store, rebuild_checkpoint=False).to_dict()
    finally:
        store.close()


def astra_campaign_reactivate(
    campaign_id: str,
    *,
    root: Path | str | None = None,
    source_commit: str | None = None,
    now_iso: Callable[[], str] = utc_now_iso,
) -> dict[str, Any]:
    """PAUSED -> ACTIVE after an explicit human review."""
    store = _open_store(campaign_id, root, source_commit)
    try:
        try:
            store.append_event(
                event_type="CAMPAIGN_STATUS_CHANGED",
                payload={"status": CampaignStatus.ACTIVE.value},
                actor=Actor.HUMAN,
                occurred_at=now_iso(),
            )
        except Exception as exc:
            raise CampaignApiError(f"Cannot reactivate campaign: {exc}") from exc
        store.write_checkpoint()
        return resume_campaign(store, rebuild_checkpoint=False).to_dict()
    finally:
        store.close()


def astra_campaign_list(
    *,
    root: Path | str | None = None,
    source_commit: str | None = None,
) -> list[dict[str, Any]]:
    """Enumerate campaigns under the root, read-only, tolerating damage."""
    base = Path(root) if root is not None else DEFAULT_CAMPAIGNS_ROOT
    if not base.exists():
        return []
    entries: list[dict[str, Any]] = []
    for child in sorted(base.iterdir()):
        if not child.is_dir() or not (child / "events.jsonl").exists():
            continue
        try:
            validate_record_id(child.name, "campaign")
        except CampaignModelError:
            continue
        try:
            entries.append(
                astra_campaign_status(
                    child.name, root=base, source_commit=source_commit
                )
            )
        except Exception as exc:
            entries.append(
                {
                    "campaign_id": child.name,
                    "health": "ERROR",
                    "next_action": "inspect_manually",
                    "notes": [f"status failed: {exc}"],
                }
            )
    return entries
