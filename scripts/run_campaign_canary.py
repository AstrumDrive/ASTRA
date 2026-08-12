"""ASTRA 2.0 campaign canary runner (stage 6).

Dry-run by default: prints the frozen plan without touching models, disk
state, or quota.  ``--offline-smoke`` drives the complete campaign loop with
a canned cycle runner (zero model calls) as a release diagnostic.  ``--live``
consumes real CLI quota and therefore requires an explicit ``--yes`` AND a
matching pre-registration fingerprint
(`docs/benchmarks/ASTRA2_CANARY_PREREGISTRATION_V1.md`): if the protocol
document changed since it was frozen, the runner refuses to start.

The canary establishes operability only; it is never evidence of comparative
scientific uplift (see the pre-registration document, section 1).
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.campaign_api import (  # noqa: E402
    _resolve_source_commit,
    astra_campaign_start,
    astra_campaign_status,
    astra_campaign_step,
)
from core.campaign_models import new_record_id  # noqa: E402
from core.campaign_store import CampaignStore  # noqa: E402
from core.campaign_trajectory_metrics import (  # noqa: E402
    campaign_trajectory_metrics,
)
from core.research_programs import load_research_programs  # noqa: E402

PREREG_DOC = ROOT / "docs" / "benchmarks" / "ASTRA2_CANARY_PREREGISTRATION_V1.md"
PREREG_SHA = (
    ROOT / "docs" / "benchmarks" / "ASTRA2_CANARY_PREREGISTRATION_V1.sha256"
)
DEFAULT_CASE = "gr_invariant_audit"
DEFAULT_ROOT = ROOT / "workspace" / "campaigns"
DEFAULT_OUT = ROOT / "workspace" / "campaign_canary_runs"


def preregistration_fingerprint() -> str:
    # Line endings are normalized so the frozen fingerprint survives Git's
    # CRLF conversion on a fresh checkout (portability, not security).
    text = PREREG_DOC.read_text(encoding="utf-8").replace("\r\n", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify_preregistration() -> str:
    expected = PREREG_SHA.read_text(encoding="utf-8").strip()
    actual = preregistration_fingerprint()
    if actual != expected:
        raise SystemExit(
            "Pre-registration fingerprint mismatch: the protocol document "
            "changed after freezing. Re-freeze it explicitly before running."
        )
    return actual


def bootstrap_portfolio(program) -> dict:
    """Deterministic seed portfolio; real claims arrive with synthesis."""
    deliverable = program.deliverables[0]
    direction = program.linear_control_directions[0]
    return {
        "schema_version": "astra-portfolio/0.1",
        "selected": {
            "statement": (
                "The frozen brief direction yields at least one decisive, "
                "falsifiable atomic proposition testable by a compact "
                "validator within one episode."
            ),
            "claim_type": "SCOPED_EMPIRICAL",
            "domain": program.domain,
            "scope": "first campaign episode of the frozen brief",
            "quantifiers": ["one bounded atomic proposition per episode"],
            "assumptions": ["the frozen brief and resources are available"],
            "tolerance": None,
            "units": None,
            "method_family": "brief_bootstrap",
            "material_difference": (
                "Bootstrap branch created deterministically from the brief; "
                "materially different families arrive via synthesis "
                "portfolios."
            ),
            "assumption_delta": {"added": [], "removed": []},
            "evidence_plan": {
                "description": (
                    "First atomic validator produced by the cycle from the "
                    "brief direction."
                ),
                "kind": "SYMBOLIC",
            },
            "deliverable": deliverable,
            "direction": direction,
            "crux": (
                "Produce and decisively test the first atomic claim derived "
                "from the brief direction."
            ),
        },
        "alternatives": [],
    }


def build_plan(
    case_id: str = DEFAULT_CASE,
    *,
    max_cycles: int = 3,
    wall_ceiling_minutes: int = 60,
) -> dict:
    programs = {program.id: program for program in load_research_programs()}
    if case_id not in programs:
        raise SystemExit(f"Unknown frozen case: {case_id!r}")
    program = programs[case_id]
    cycles = max(1, min(program.budget.max_cycles, max_cycles))
    wall_minutes = max(1, min(program.budget.max_wall_minutes,
                              wall_ceiling_minutes))
    brief = program.research_brief()
    return {
        "case": program.id,
        "domain": program.domain,
        "objective": program.objective,
        "success_definition": program.success_definition,
        "deliverables": list(program.deliverables),
        "brief_sha256": hashlib.sha256(brief.encode("utf-8")).hexdigest(),
        "budget": {
            "cycles": cycles,
            "model_calls": cycles * 12,
            "wall_seconds": wall_minutes * 60,
            "execution_seconds": program.budget.execution_timeout_seconds
            * cycles,
            "human_interventions": 1,
            "remote_jobs": 0,
        },
        "allowed_evidence_classes": ["SYMBOLIC", "NUMERICAL", "COUNTEREXAMPLE"],
        "seed_portfolio": bootstrap_portfolio(program),
        "oracle": "local",
        "seed": 11,
    }


def _offline_stub_runner(plan: dict):
    """Canned VALIDATED cycles with a synthesis portfolio; zero models."""
    deliverable = plan["deliverables"][0]

    def candidate(family: str, statement: str, crux: str | None) -> dict:
        return {
            "statement": statement,
            "claim_type": "UNIVERSAL",
            "domain": plan["domain"],
            "scope": "bounded validator scope",
            "quantifiers": ["forall inputs in the bounded scope"],
            "assumptions": ["frozen brief assumptions"],
            "tolerance": None,
            "units": None,
            "method_family": family,
            "material_difference": f"Distinct method family {family}.",
            "assumption_delta": {"added": [], "removed": []},
            "evidence_plan": {
                "description": f"Cheapest discriminating check via {family}.",
                "kind": "SYMBOLIC",
            },
            "deliverable": deliverable,
            "direction": f"Continue through {family}.",
            "crux": crux,
        }

    async def runner(_request: dict) -> dict:
        return {
            "status": "VALIDATED",
            "scientific_status": "ATOMIC_VALIDATED",
            "code_review": {"status": "APPROVED"},
            "goal_coverage": {"status": "partial"},
            "code": "print('VERDICT: PASS')\n",
            "execution_result": {"stdout": "CHECK smoke: OK\nVERDICT: PASS\n"},
            "timings": {"conjecture": 1.0, "translate": 1.0, "execute": 0.5,
                        "analysis": 1.0},
            "deliberation": {
                "proposals": [{"provider": "codex_cli"},
                              {"provider": "agy_cli"}],
                "critiques": [{"provider": "codex_cli"},
                              {"provider": "agy_cli"}],
                "portfolio": {
                    "schema_version": "astra-portfolio/0.1",
                    "selected": candidate(
                        "direct_validation",
                        "The bounded invariant identity holds on the frozen "
                        "scope.",
                        "Extend the identity beyond the bounded scope.",
                    ),
                    "alternatives": [
                        candidate(
                            "independent_check",
                            "An independent formulation reproduces the "
                            "bounded invariant identity.",
                            None,
                        )
                    ],
                },
            },
            "providers": {"translator": "stub"},
            "actual_models": {"translator": "offline-stub"},
            "oracle_mode": "local",
        }

    return runner


async def run_canary(
    plan: dict,
    *,
    root: Path,
    out_dir: Path,
    cycle_runner=None,
    run_label: str,
) -> dict:
    campaign_id = new_record_id("campaign")
    started = astra_campaign_start(
        objective=plan["objective"],
        success_definition=plan["success_definition"],
        deliverables=plan["deliverables"],
        allowed_evidence_classes=plan["allowed_evidence_classes"],
        budget=plan["budget"],
        frozen_resources={"research_brief": plan["brief_sha256"]},
        initial_portfolio=plan["seed_portfolio"],
        campaign_id=campaign_id,
        root=root,
    )
    episodes: list[dict] = []
    wall_deadline = time.monotonic() + plan["budget"]["wall_seconds"]
    status = started
    while (
        status["next_action"] == "campaign_step"
        and len(episodes) < plan["budget"]["cycles"]
        and time.monotonic() < wall_deadline
    ):
        stepped = await astra_campaign_step(
            campaign_id, root=root, cycle_runner=cycle_runner
        )
        episodes.append(stepped["step"])
        status = stepped["status"]
        if stepped["step"]["budget_exhausted"]:
            break
    reader = CampaignStore(
        Path(root), campaign_id, source_commit=_resolve_source_commit(None)
    )
    try:
        trajectory_metrics = campaign_trajectory_metrics(reader.replay().state)
    finally:
        reader.close()
    summary = {
        "run_label": run_label,
        "preregistration_fingerprint": verify_preregistration(),
        "plan": plan,
        "campaign_id": campaign_id,
        "started": started,
        "episodes": episodes,
        "final_status": astra_campaign_status(campaign_id, root=root),
        "trajectory_metrics": trajectory_metrics,
        "operability": {
            "episodes_completed": len(episodes),
            "evidence_recorded": sum(
                1 for episode in episodes if episode["evidence_id"]
            ),
            "decisions_recorded": sum(
                len(episode["decisions"]) for episode in episodes
            ),
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{run_label}_{campaign_id}.json"
    out_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    summary["summary_path"] = str(out_path)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default=DEFAULT_CASE)
    parser.add_argument("--max-cycles", type=int, default=3)
    parser.add_argument("--wall-ceiling-minutes", type=int, default=60)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true",
                      help="print the frozen plan (default mode)")
    mode.add_argument("--offline-smoke", action="store_true",
                      help="run the full loop with a canned runner; no models")
    mode.add_argument("--live", action="store_true",
                      help="consume real CLI quota (requires --yes)")
    parser.add_argument("--yes", action="store_true",
                        help="explicit confirmation for --live")
    args = parser.parse_args(argv)

    fingerprint = verify_preregistration()
    plan = build_plan(
        args.case,
        max_cycles=args.max_cycles,
        wall_ceiling_minutes=args.wall_ceiling_minutes,
    )

    if args.offline_smoke:
        summary = asyncio.run(
            run_canary(
                plan,
                root=args.root,
                out_dir=args.out,
                cycle_runner=_offline_stub_runner(plan),
                run_label="offline_smoke",
            )
        )
        print(json.dumps(summary["operability"], indent=2))
        print(f"summary: {summary['summary_path']}")
        return 0

    if args.live:
        if not args.yes:
            print(
                "--live consumes real CLI quota. Re-run with --yes after "
                "reviewing the plan below.",
                file=sys.stderr,
            )
            print(json.dumps(plan, indent=2, ensure_ascii=False))
            return 2
        summary = asyncio.run(
            run_canary(
                plan,
                root=args.root,
                out_dir=args.out,
                cycle_runner=None,  # the real _do_cycle
                run_label="live_canary",
            )
        )
        print(json.dumps(summary["operability"], indent=2))
        print(f"summary: {summary['summary_path']}")
        return 0

    # Default: dry run.
    print(
        json.dumps(
            {"preregistration_fingerprint": fingerprint, "plan": plan},
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
