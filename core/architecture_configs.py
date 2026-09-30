"""Shared ASTRA architecture configurations for fair ablation studies."""
from __future__ import annotations

import os
from typing import Any


ARCHITECTURE_ROLES: dict[str, dict[str, Any]] = {
    "full": {
        "proposers": ["codex_cli", "agy_cli"],
        "synthesizer": "codex_cli",
        "author": "claude_cli",
        "reviewer": "codex_cli",
        "repairer": "claude_cli",
    },
    # Time-bounded local trial. Muse is an additional independent proposer and
    # critic only; the production validator and analysis roles do not change.
    "muse-trial": {
        "proposers": ["codex_cli", "agy_cli", "muse_cli"],
        "synthesizer": "codex_cli",
        "author": "claude_cli",
        "reviewer": "codex_cli",
        "repairer": "claude_cli",
        "navigator": "agy_cli",
    },
    # Opt-in codex quota relief. Identical to ``full`` except the SYNTHESIZER
    # moves off the (weekly-limited) codex account to agy, whose quota is a
    # separate pool. The anti-cheat REVIEWER gate and the ANALYST verdict stay
    # on codex, and codex remains a proposer -- so the science-critical roles
    # are unchanged; only the conjecture-merge step is reassigned.
    "quota-relief": {
        "proposers": ["codex_cli", "agy_cli"],
        "synthesizer": "agy_cli",
        "author": "claude_cli",
        "reviewer": "codex_cli",
        "repairer": "claude_cli",
    },
    "codex-only": {
        "proposers": ["codex_cli", "codex_cli"],
        "synthesizer": "codex_cli",
        "author": "codex_cli",
        "reviewer": "codex_cli",
        "repairer": "codex_cli",
    },
    # Matched control for the diversity experiment. It differs from ``full``
    # only in proposal 2: a second Codex replaces AGY/Gemini. All downstream
    # roles and the number/order of calls stay identical.
    "homogeneous-proposers": {
        "proposers": ["codex_cli", "codex_cli"],
        "synthesizer": "codex_cli",
        "author": "claude_cli",
        "reviewer": "codex_cli",
        "repairer": "claude_cli",
    },
    "claude-only": {
        "proposers": ["claude_cli", "claude_cli"],
        "synthesizer": "claude_cli",
        "author": "claude_cli",
        "reviewer": "claude_cli",
        "repairer": "claude_cli",
    },
    "agy-only": {
        "proposers": ["agy_cli", "agy_cli"],
        "synthesizer": "agy_cli",
        "author": "agy_cli",
        "reviewer": "agy_cli",
        "repairer": "agy_cli",
    },
    "no-review": {
        "proposers": ["codex_cli", "agy_cli"],
        "synthesizer": "codex_cli",
        "author": "claude_cli",
        "reviewer": "codex_cli",
        "repairer": "claude_cli",
    },
    "no-ensemble": {
        "proposers": ["codex_cli"],
        "synthesizer": "codex_cli",
        "author": "claude_cli",
        "reviewer": "codex_cli",
        "repairer": "claude_cli",
    },
    # Baseline arm of the efficiency audit (docs/evidence/ASTRA_EFFICIENCY_AUDIT
    # _20260930.md, recommendation 2): what a researcher gets from ONE model
    # asked once. One proposal, the same model writes the validator and reads
    # the oracle output, no independent reviewer, no deterministic guard, no
    # repair loop, no retry, no navigation. Only the oracle execution stays,
    # because a model alone can also run code. Unlike the other single-agent
    # entries it does NOT double the proposal call: the point is the unaided
    # baseline, not a call-count-matched control.
    "single-model": {
        "proposers": ["codex_cli"],
        "synthesizer": "codex_cli",
        "author": "codex_cli",
        "reviewer": "codex_cli",
        "repairer": "codex_cli",
    },
}

SINGLE_MODEL_ENVIRONMENT = {
    "ASTRA_CODE_REVIEW": "0",
    "ASTRA_VALIDATOR_REPAIR_VNEXT": "0",
    "ASTRA_VERDICT_GUARD": "0",
    "ASTRA_MAX_RETRIES": "0",
    "ASTRA_REVIEW_STUCK_DETECTOR": "0",
    "ASTRA_NAVIGATE_AFTER_CYCLE": "0",
}


def architecture_roles(name: str) -> dict[str, Any]:
    """Return a defensive copy of the named public-comparison role map."""
    key = name.strip().lower()
    if key not in ARCHITECTURE_ROLES:
        raise ValueError(f"Unknown architecture configuration: {name}")
    roles = ARCHITECTURE_ROLES[key]
    return {
        **roles,
        "proposers": list(roles["proposers"]),
    }


def architecture_environment(
    name: str,
    *,
    base: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build an isolated environment with a phase topology matching ``name``.

    Single-agent baselines intentionally receive two independent proposal calls.
    This preserves the proposal/synthesis topology and model-call count used by
    the compact full architecture; only the identity of the agent changes.
    """
    key = name.strip().lower()
    roles = architecture_roles(key)
    env = dict(base if base is not None else os.environ)
    # Phase-specific model lists from the production role map can belong to a
    # different provider (for example, Claude models for the translator). They
    # must not leak into a single-agent ablation after its provider is changed.
    for phase in (
        "CONJECTURE",
        "TRANSLATOR",
        "REVIEWER",
        "ANALYST",
        "NAVIGATOR",
        "SYNTH",
    ):
        # Keep explicit empty values in the child environment. Removing the
        # keys would let load_dotenv() restore production phase-model lists.
        env[f"ASTRA_{phase}_MODEL"] = ""
        env[f"ASTRA_{phase}_MODELS"] = ""
    env.update(
        {
            "ASTRA_CONJECTURE_PROVIDER": ",".join(roles["proposers"]),
            "ASTRA_TRANSLATOR_PROVIDER": roles["author"],
            "ASTRA_REVIEWER_PROVIDER": roles["reviewer"],
            "ASTRA_ANALYST_PROVIDER": roles["reviewer"],
            "ASTRA_NAVIGATOR_PROVIDER": roles.get(
                "navigator", roles["proposers"][-1]
            ),
            "ASTRA_SYNTH_PROVIDER": roles["synthesizer"],
            "ASTRA_CYCLE_CACHE": "0",
        }
    )
    if key == "no-review":
        env["ASTRA_CODE_REVIEW"] = "0"
    elif key == "single-model":
        env.update(SINGLE_MODEL_ENVIRONMENT)
    else:
        env.pop("ASTRA_CODE_REVIEW", None)
    return env
