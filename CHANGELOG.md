# Changelog

The production line of ASTRA is versioned here and in the `VERSION` file at
the checkout root; `core/astra_identity.py` reads that file, so every window
title, banner and report names the version actually running
(`ASTRA 1.1.0 production @<commit> <date>`). Semantic versioning: the first
number changes with the deliberative cycle or the MCP tool contract, the
second with measured capability, the third with fixes. The development line
in `ASTRA-2.0` keeps its own identity through its acceptance gate and is not
covered by this file. Dates are the day the change reached `main`.

## 1.1.7 (2026-10-09)

Two Kondo cycles stopped at review because floats cannot certify complex
logarithm branches or a uniform remainder bound, and the 9 October
benchmark lost two cases that were decided in all but name (an unstated
convention). This release gives validators certified arithmetic, asks the
user which convention was meant, keeps partial evidence on a timeout, and
opens ASTRUM to per-person accounts. Not yet measured on the research
corpus, hence a patch release.

- Certified ball arithmetic: a Python validator that declares
  `# ASTRA_CERTIFIED: arb` gets a vetted python-flint (Arb) prelude
  (`core/certified/`): certified branch index, certain comparisons, rigorous
  sup bounds on polar sectors, declared analytic tails. Anything the balls
  cannot decide raises Undecided, never PASS or FAIL. Author rule 7,
  reviewer rule 11 (vNext rules renumbered 12-16), analyst ANALYTIC_TAIL
  rule; python-flint in `requirements.txt`, optional in the doctor.
- Convention requests: when a decided cycle leaves the claim INCONCLUSIVE or
  SUBSTITUTED only because a convention, assumption or domain is unstated,
  the analyst names the readings and `input_request` (kind `convention`)
  offers one fresh re-run per reading. `status` and
  `original_claim_verdict` never change.
- Timeout recovery: an execution deadline keeps partial stdout and stderr,
  is CODE_ERROR with the claim INCONCLUSIVE, and is never read as a
  counterexample; repair gets recovery instructions, an unchanged validator
  is not rerun, and every attempt is logged in `execution_history`.
- Complete validator code in the reviewer, correction, repair and analyst
  prompts (the 14,000-24,000-character cuts on the script and the 3,500 on
  repair instructions are removed), completing the full-context work of
  1.1.6.
- ASTRUM per-person access: accounts that reach only the job manager,
  identity taken from the SSH account, cancel-own-jobs, per-person quotas,
  `threads_per_process` for MPI jobs, `ssh astrum info`. One-paste Windows
  setup for collaborators and a Windows onboarding guide; public documents
  carry no installation-specific data.
- Meta Muse Code removed (decision of 2026-10-09: the subscription is
  cancelled; ASTRA uses only the Claude, Codex and agy CLIs). Gone: the
  `muse_cli` provider and its WSL bridge, the `muse-trial` profile and its
  overlay and scripts, the Muse entries of max mode and of the doctor. The
  production manifest no longer lists `muse_cli`, so cycle-cache keys change
  once.
- Tests: suite 731 passed, 5 skipped.

## 1.1.6 (2026-10-05)

A source audit (warp, felt-acceleration revision) found that the validator
author, the reviewer and the repairer were not reading the same
specification: the user's claim was cut at 3,500 characters for the author,
the reviewer saw only the conjecture, and both auditors cut their context at
2,000/5,000 characters. A review of the code for the technical reference
found five smaller defects. The first rerun of that source audit with the
fix closed VALIDATED with the claim supported and full coverage.

- Full claim context: the author receives the user's claim block uncapped;
  the reviewer and the bounded repairer receive exactly the author's input
  (objective, claim block, conjecture), prefixed by the inputs policy, with
  no truncation. Tests: `tests/test_full_claim_context.py`; negative control
  `scripts/check_claim_context_negative_control.py` reintroduces the cuts in
  memory and the tests must fail. The control now isolates its lock root
  and workspace like the suite: run beside a production cycle it used to
  hit the machine-wide cycle slot and return BUSY.
- Conjecture rule 7, fixed single claim: a proposition the user states is
  kept with its quantifiers, definitions and constants; supporting estimates
  are proof obligations; if it cannot be decided in one cycle the answer is
  INCONCLUSIVE with the open obligations, never a silent subclaim.
- The analysis phase is no longer started below its 90 s minimum (defined in
  1.1.1, never checked): the cycle returns PARTIAL with the execution
  evidence in its checkpoint, at the first analysis and in retries.
- `production_manifest` gives the `no-ensemble` profile its own role map,
  the one the contract audit expects (it fell back to `full`).
- Codex reasoning effort defaults to `xhigh` on Windows and POSIX when
  `ASTRA_CODEX_REASONING` is unset, matching the contract.
- The reviewer's vNext rules are numbered 11-15 (two rules were numbered
  10); stale comments about a 5,000-character window and a "venv 3.9" core
  are corrected.
- Tests: `tests/test_release_1_1_6.py`; suite 650 passed, 2 skipped.

## 1.1.5 (2026-10-05)

The name keeps its expansion, Autonomous Symbolic Theorem Reasoning
Architecture, and gains the tagline the team asked for: *recursive
inference in cycles*. It names what the cycle already does: inside every
cycle a failed review, a crashed validator or a missing input is fed back as
the input of the next step; in autonomous mode each verdict seeds the next
cycle's hypothesis.

- README, both architecture whitepapers (title page, recompiled PDFs in
  `output/pdf/`) and the process banner carry the expansion and the tagline.
- No behaviour change.

## 1.1.4 (2026-10-02)

Every job runner opened an empty Windows Terminal window, titled with the
venv's `python.exe`, for the whole length of its job. The runners started
with `DETACHED_PROCESS` through the venv's `python.exe`, a launcher whose
child is the real interpreter; a detached launcher has no console, so its
child got a new, visible one. Closing that window killed the runner without
a traceback while its cycle went on. This is what stopped five runners at
once at 15:18 on 2026-10-02.

- The runners of `astra_submit`, `astra_cycle_submit` and the MCP campaign
  step, and the research-trajectory benchmark launcher, start with
  `CREATE_NO_WINDOW` and their own process group (breakaway from the
  caller's job is still tried first). They own a console without a window,
  so there is nothing on screen to close.
- The campaign-step change lives in `mcp_server/server.py` and takes effect
  when an MCP client restarts its server; the other launches change at once.

## 1.1.3 (2026-10-02)

Five persistent-cycle runners were terminated together, with no traceback
(cause not determined), while their cycles went on to finish; three of them
supported the user's claim. Only the runner copies a cycle's result into
`job.json`, so `astra_job` reported all five as `killed`.

- When a cycle's runner is dead, `astra_job` reads the result line the
  cycle printed to `stdout.log`. The job reads `done`, with
  `state_source: stdout.log`, `exit_code: null` (not observable) and the
  full result. The runner's own unpublished state in `job.json.tmp` still
  takes precedence. Nothing is written to the job directory.
- A cycle that outlives its runner reads `running` with
  `runner_alive: false` instead of `killed`, for at most `max_seconds`
  plus 120 s (beyond that a live process id is taken as reused).
- The runner and `astra_job` compute the summary fields with the same code
  (`core/cycle_job_result.py`).

## 1.1.2 (2026-10-02)

A `grep` poll had a job's `job.json` open when the persistent-cycle runner
renamed its heartbeat over it; Windows denied the `os.replace`, the runner
died, and `astra_job` reported the job as `killed` while the cycle went on
to finish VALIDATED with its result only in `stdout.log`.

- The cycle, job and campaign-step runners retry the rename (10 attempts,
  50-200 ms apart). A heartbeat that still fails is logged to `runner.err`
  and the runner carries on; the final save retries for about 10 s
  (`core/atomic_write.py`). The cycle checkpoint retries its rename too.
- When a dead runner's final save could not be published, `astra_job`
  reports the newer state it left in `job.json.tmp`, marked
  `state_source: job.json.tmp`. It never opens the `.tmp` while the runner
  is alive.

## 1.1.1 (2026-10-02)

A cycle launched from Codex with `timeout=900` spent three review rounds on
a normalization the user's text had stated and died before the oracle ran.

- The independent reviewer treats the "USER'S CLAIM AND DEFINITIONS" and
  FROZEN INPUTS blocks as part of the specification: a validator may rely on
  anything stated there without the conjecture restating it.
- A review round, a bounded repair or an analysis is not started when the
  remaining budget would give it less than a realistic call (120 s, 90 s,
  90 s); the cycle returns PARTIAL with its last real source instead of
  launching a call that the budget kills.
- The MCP docstring and AGENTS.md tell agents to keep `timeout` at its
  default and to use `astra_cycle_submit` for long audits.

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
