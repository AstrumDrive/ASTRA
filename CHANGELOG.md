# Changelog

The production line of ASTRA is versioned here and in the `VERSION` file at
the checkout root; `core/astra_identity.py` reads that file, so every window
title, banner and report names the version actually running
(`ASTRA 1.1.0 production @<commit> <date>`). Semantic versioning: the first
number changes with the deliberative cycle or the MCP tool contract, the
second with measured capability, the third with fixes. The development line
in `ASTRA-2.0` keeps its own identity through its acceptance gate and is not
covered by this file. Dates are the day the change reached `main`.

## 1.1.0 (2026-10-02)

Measured on 50 research claims from live projects: 47 decided correctly, no
false acceptance of 21 false claims, no false refutation of 29 true ones
(`docs/evidence/RESEARCH_CLAIMS_COMPARISON_20260930.md`).

- Verdict re-anchored to the user's claim: `original_claim_verdict`
  (SUPPORTED, REFUTED, INCONCLUSIVE, SUBSTITUTED) travels beside `status`
  and is never collapsed into it; an unparseable analyst reply is asked once
  more and never certifies the claim by default.
- The validator author now receives the user's own claim text, with every
  convention, metric component, operator order and generator it names
  (`build_translation_input`); until then only the proposer and the analyst
  saw it.
- The analyst no longer files a clean refutation as CODE_ERROR: a FAIL from a
  correct script is evidence, float display of an exact value is not a
  defect, and the two verdict axes must agree (one consistency re-ask); a
  repairer that finds no defect no longer kills the cycle.
- Production profile `no-ensemble` (one Codex proposer, Claude Opus author,
  Codex reviewer and analyst, navigation off) with its own contract id;
  `single-model` baseline arm for comparisons.
- Session preflight: a cycle stops before the conjecture when a subscription
  CLI is logged out; the doctor checks CLI versions and sessions.
- Research corpus `benchmarks/quality/research` (v1.2, 50 one-proposition
  cases with measured ground truth and reference scripts); benchmark labels
  REVIEW_REJECTED and BUDGET_EXHAUSTED; cycle budget widened for heavy
  oracle runs.
- Identity: windows and banners name the line, the commit and the profile.
- Model ladders: Codex `gpt-6-luna,gpt-6-astra`, Claude `claude-opus-5-5,sonnet`,
  agy `gemini-3.1-pro-high,...`; doctor requires Codex >= 0.157 and Claude
  Code >= 2.1.280.

## 1.0 (2026-07-22)

First public release of the production line: conjecture, translation,
independent review, oracle execution and analysis over subscription CLIs,
MCP server with 15 tools, local and cluster oracles, deterministic verdict
guard, cycle cache, NON_DECIDABLE with input requests, bounded review loop
with stuck detector. Architecture described in `docs/architecture/`.
