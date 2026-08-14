# ASTRA 2.0 acceptance gate

## Status

**DEVELOPMENT ONLY — NOT APPROVED FOR PRODUCTION USE**

This repository is the isolated ASTRA 2.0 development line. The current
production checkout remains `C:\Users\Nelson\Dev\ASTRA`.

The clone was created from production commit
`e4752eada0dc78b52cc88b98753ae144b6e56041`. Uncommitted files from the
production checkout were intentionally not copied.

## Isolation contract

- Development path: `C:\Users\Nelson\Dev\ASTRA-2.0`
- Development branch: `astra-2.0`
- Production MCP registration: unchanged
- Production desktop launcher/service: unchanged
- Development environment: must be created inside this checkout
- Secrets and machine credentials: must remain outside Git and must not be
  copied from the production checkout
- Production and company Git push URLs: disabled until explicit acceptance

ASTRA 2.0 may be executed only for development, tests, frozen benchmarks, and
auditable validation runs until Nelson explicitly approves promotion.

## Mandatory acceptance gates

Every gate must have a reproducible command, dated result bundle, source commit,
environment fingerprint, and an unambiguous PASS/FAIL/INCONCLUSIVE status.

### G0 — Repository and environment isolation

- [x] Separate checkout and branch
- [x] Production MCP and launchers unchanged
- [x] No production `.env`, credentials, virtual environment, or workspace copied
- [x] Push to production remotes disabled
- [x] Dedicated Python 3.12 environment created and fingerprinted

Environment fingerprint established on 2026-08-11:

- Python: `3.12.10`
- Platform: `Windows-11-10.0.26200-SP0`
- Packages: `95`
- `pip freeze` SHA-256:
  `59f3d679d7790fe9b96eb1886b44cdbe88aa05f60e79dfe2acfae78df7ccfec5`

### G1 — Deterministic regression suite

- [x] Complete committed `pytest` suite passes with only documented intentional skips
- [x] Architecture-contract tests pass
- [x] Validator-preflight and repair regressions pass
- [ ] End-to-end pipeline tests pass
- [x] No unexplained warning, hang, orphan process, or leaked temporary artifact

Baseline result: `136 passed, 6 skipped, 2 subtests passed in 30.47s`.
The six skips require optional frozen external caches. See
`docs/benchmarks/ASTRA2_BASELINE_2026-08-11.md`.

### G2 — Engine and oracle validation

- [x] Local doctor/preflight passes
- [x] Required local engines pass their smoke tests
- [ ] ASTRUM remote engine inventory is recorded
- [ ] Cross-oracle claim verdicts agree for the frozen client-validation suite
- [ ] Scheduler attribution, concurrency limits, timeouts, and cancellation pass

Non-promotional diagnostic on 2026-08-12: the architecture audit passed all
required configuration checks and discovered local Z3 plus WSL routes for
SageMath, Maxima, and Cadabra. It reported local Lean and the remote route as
unconfigured. Discovery is not an engine smoke test, so no G2 item was marked
complete on that basis.

Closed on 2026-08-13, both items evidence-backed by local execution and no
model quota (`docs/evidence/ASTRA2_G2_LOCAL_ENGINES_20260813.md`):

- `scripts/astra_doctor.py` reports PASS with every required check green.
- `scripts/run_engine_smokes.py` runs one real artifact per engine through
  ASTRA's local router and gets 6/6: python, z3, sage, maxima, cadabra, and
  lean4 kernel-checked against the pinned Mathlib v4.30.0 with a clean
  `#print axioms`. Each artifact fails on a wrong answer, not merely on a
  missing import.

The local Lean route became testable only after the Windows PowerShell
encoding defect was fixed on 2026-08-12: `∀` reached the reviewer as `???`.
Note that the doctor's `OPTIONAL_MISSING` lines for maxima/sage/cadabra2 refer
to native Windows executables — those engines run under WSL and pass — and
that the native Lean 4.32.2 it discovers is NOT the ASTRA oracle, which is
pinned to 4.30.0 under WSL.

The three remaining items require contacting ASTRUM, which needs explicit
authorization under `HANDOFF.md` §9.

### G3 — Scientific quality benchmarks

- [ ] Frozen deterministic quality suite passes
- [ ] Client-validation suite passes with complete evidence manifests
- [ ] External public benchmark subset passes under its frozen protocol
- [ ] No regression in false acceptance, false blocking, or operational/scientific
      status separation

### G4 — ASTRA 2.0 research-trajectory evaluation

- [ ] Protocol and holdout fingerprints are frozen before model runs
- [ ] One-cell end-to-end canary completes
- [ ] Matched comparison against current ASTRA and `full-linear` completes
- [ ] Required ablations complete: no graph, no heterogeneous perspectives,
      no execution feedback, and no adversarial campaign
- [ ] At least two blinded expert ratings are complete for every admitted cell
- [ ] Scientific quality, autonomy, reliability, wall time, and model-call cost
      are reported separately rather than collapsed into one score

### G5 — Safety, portability, and reproducibility

- [ ] Fresh Windows installation reproduces the accepted results
- [ ] ASTRUM remote execution reproduces the accepted remote cases
- [ ] macOS installation and MCP smoke test pass on a collaborator machine
- [ ] Documentation, migration, rollback, and recovery procedures are verified
- [ ] Secret scan and generated-artifact audit pass

### G6 — Promotion decision

- [ ] Release candidate commit is immutable and tagged locally
- [ ] Acceptance report identifies every residual limitation
- [ ] Nelson explicitly approves production promotion
- [ ] Only after approval: enable the intended Git push URL
- [ ] Only after approval: update MCP, launcher, service, and ASTRUM deployment
- [ ] Run a post-promotion smoke test and retain the previous production rollback

## Promotion rule

A failing or inconclusive mandatory gate blocks promotion. A benchmark result
does not need to be superior on every dimension, but ASTRA 2.0 must preserve
scientific validity and show a useful, evidence-backed tradeoff in research
quality, autonomy, reliability, control, or cost.

Passing unit tests alone is not sufficient. A successful one-cell canary proves
operability only; it does not establish comparative research value.
