# RFC: One ASTRA service — unified MCP, layered capabilities, explicit policy

- **Status:** Draft / Proposed (awaiting Nelson's review — no code changes proposed to start)
- **Date:** 2026-08-22
- **Author:** drafted with Claude, for Nelson
- **Affects:** production `ASTRA` and development `ASTRA-2.0` checkouts, both MCP registrations
- **Related:** `docs/architecture/ASTRA2_ARCHITECTURE_REVIEW.md`, `ASTRA2_ACCEPTANCE.md`,
  `HANDOFF.md` §9/§11/§12, `docs/architecture/ASTRA2_SEPARATION_AND_PREPROD.md`

## 1. Summary

ASTRA 1.0 (atomic cycles + Research Loop), ASTRA 2.0 (persistent campaigns), and
ASTRUM (remote compute) are not three systems. They are **one engine, two
orchestration strategies, and one remote node**, currently split across two
divergent checkouts and two MCP servers. This RFC proposes collapsing them into
**one codebase and one MCP binary whose capabilities are selected by a named
profile**, with the previously-implicit policies (execution, concurrency,
acceptance, evidence, quota, and the manuscript-authoring/editorial policy —
§10) made explicit and centralized. The same service therefore covers the whole
research lifecycle, from conjecture and evidence to a publication-ready
manuscript. It does **not** propose weakening the acceptance boundary that keeps
the production verifier safe; that boundary becomes a runtime profile instead of
a separate checkout.

## 2. Context and problem

Today there are two servers:

| | Server name | Checkout | Tool surface |
|---|---|---|---|
| Production | `astra` | `C:\Users\Nelson\Dev\ASTRA` | atomic/cycle/cluster/status/probe |
| Campaigns | `astra_dev` | `C:\Users\Nelson\Dev\ASTRA-2.0` | the same **+** `astra_campaign_*` |

`ASTRA-2.0` was cloned from production and adds a campaign layer on top of the
**same** atomic `astra_cycle` worker. The overlap is not incidental — it is
structural:

- **2.0 is production + a gated layer.** `mcp_server/server.py` is 511 lines in
  production vs 796 in 2.0; the delta is the `astra_campaign_*` tools (already
  gated by `ASTRA_CAMPAIGN_TOOLS` / `_campaign_tools_enabled()`) plus the async
  wrapping.
- **The quota lock already spans both.** `core/runtime_resources.py` takes a
  **machine-wide** single-cycle slot precisely because concurrent cycles in the
  two checkouts share the same model-subscription accounts. Two processes are
  already coordinated as one system through a lock on disk.
- **The server name is already parameterized for promotion.** 2.0 reads
  `ASTRA_MCP_SERVER_NAME` "for exactly that promotion"; the germ of a single
  profile-selected binary already exists in the code.

### The cost is real and currently unpaid

The split imposes a manual-sync tax that is being paid right now:

- The **concurrency fix** (async dispatch, 2026-08-21) and the **hot-path
  git-hang fix** (2026-08-22) landed **only in 2.0**. Production still has every
  tool as synchronous `def` (same freeze) and still shells out to
  `git rev-parse HEAD` in `client_validation.py:182` and
  `external_benchmarks.py:266` (same potential wedge).
- Earlier fixes (PowerShell non-ASCII prompt corruption; the machine-wide lock)
  were documented as "found in 2.0, then ported to production by hand."

Every infrastructure fix has to be written once and remembered twice. That is
the defect this RFC removes.

## 3. Goals and non-goals

**Goals**

1. One codebase; an infrastructure fix lands **once**.
2. One MCP binary; the client connects to one server, not two.
3. Capabilities selected by an explicit, named **profile**, not by which
   checkout happened to spawn.
4. The policy areas (below) written down and centralized.
5. The acceptance boundary preserved exactly, as configuration.
6. One home for the *output* side too — the editorial policy and the
   AI-signature check that turn accepted evidence into a publication-ready,
   author-voiced manuscript (§10).

**Non-goals**

- Not changing the science: the atomic cycle, the five status axes, the evidence
  policy, and the campaign algorithm are unchanged.
- Not promoting ASTRA 2.0 to production. Campaigns stay **off** in the production
  profile until gates G3–G6 pass.
- Not a UI rewrite, not new engines, not an ASTRUM redesign.

## 4. Hard constraint — the acceptance boundary must not collapse

`ASTRA2_ACCEPTANCE.md` marks 2.0 `DEVELOPMENT_ONLY`, `promotion_blocked: true`,
with G3–G6 `PENDING`. HANDOFF §9 forbids registering 2.0 in the production MCP
or working on 2.0 tasks inside the production checkout. This isolation is
load-bearing: it lets long-horizon experimental campaigns run without risking
the verifier Nelson depends on for real papers.

**Unification must therefore be by profile, never by copying 2.0 over
production.** Production's code is the base; campaigns are an additive module
that the production profile leaves disabled. Unify the *codebase and
architecture* now (low risk, removes drift); keep campaigns *gated off in the
production profile* until acceptance.

## 5. Proposed architecture — one service, four layers

```
┌─────────────────────────────────────────────────────────────┐
│ Interface layer:  ONE MCP binary                             │
│   always:  execute, cycle, cycle_submit, submit, job,        │
│            capacity, cluster_*, status, engines, probe       │
│   gated:   campaign_start/step/step_submit/status/stop/...   │
│            manuscript review/edit + AI-signature check        │
│            (each enabled only when the profile allows it)    │
├─────────────────────────────────────────────────────────────┤
│ Orchestration layer:  strategies + authoring on one worker  │
│   • Research Loop        (1.0)  depth-first chaining         │
│   • Campaign controller  (2.0)  ledger, branches, budgets   │
│   • Authoring/editorial         manuscript ← evidence (§10)  │
├─────────────────────────────────────────────────────────────┤
│ Engine / worker layer:  the atomic astra_cycle              │
│   conjecture → critique → translate → review → oracle →      │
│   analyze;  local engines (CAS, Lean) + oracle routing      │
├─────────────────────────────────────────────────────────────┤
│ Resource / policy layer:  one quota lock, one budget model, │
│   one ASTRUM client, one transport-concurrency policy       │
└─────────────────────────────────────────────────────────────┘
```

The key idea: **Research Loop and the campaign controller are two orchestration
strategies over the same atomic worker, not two systems.** ASTRUM sits under the
resource layer as one shared client, reachable from either strategy.

## 6. Profiles (capabilities as configuration)

A profile is a named bundle of capability flags, resolved at startup. The
mechanism already exists in fragments (`ASTRA_CAMPAIGN_TOOLS`,
`ASTRA_MCP_SERVER_NAME`, `ASTRA_LOCK_ROOT`, `ASTRA_MAX_CONCURRENT_CYCLES`); this
RFC makes it one explicit table instead of scattered env vars.

| Profile | Campaign tools | Engines | Oracle | Intended use |
|---|---|---|---|---|
| `production` | **off** | accepted set only | local + ASTRUM | daily verified work; the tool Nelson relies on |
| `campaign` | **on** | full | local + ASTRUM | long-horizon campaigns, once G3–G6 pass |
| `dev` | on | full | local (+ASTRUM opt-in) | development, tests, offline smoke |

Authoring is a **composable capability**, not a fourth exclusive profile:
`ASTRA_AUTHORING_TOOLS` (analogous to the existing `ASTRA_CAMPAIGN_TOOLS`) turns
the editorial/AI-signature tools on or off independently, so it can ride on any
science profile — or run alone when the task is purely manuscript work.

Until acceptance, `production` and `campaign` map to the two servers we have
today — but from **one codebase**, so the divergence stops immediately even
before the registrations merge.

## 7. Tool surface

| Tool(s) | Layer | Profiles |
|---|---|---|
| `astra_execute`, `astra_client_validate` | engine | all |
| `astra_cycle`, `astra_cycle_submit` | engine/orchestration | all |
| `astra_submit`, `astra_job` | engine (async jobs) | all |
| `astra_cluster_*`, `astra_capacity`, `astra_engines`, `astra_status` | resource/ASTRUM | all |
| `astra_probe` | resource (read-only) | all |
| `astra_campaign_*` (incl. `astra_campaign_step_submit`) | orchestration | `campaign`, `dev` only |
| `astra_manuscript_review` / `astra_manuscript_edit` (proposed) | orchestration (authoring) | `ASTRA_AUTHORING_TOOLS` |
| `detector_*` (AI-signature; from `detector-ia`) | orchestration (authoring) | `ASTRA_AUTHORING_TOOLS` |

## 8. Policy layers made explicit ("políticas claras y organizadas")

The point of unification is not one process; it is one place per policy.

| Policy | Question it answers | Where it lives today | Under this RFC |
|---|---|---|---|
| **Execution** | local engine vs ASTRUM oracle | scattered per-tool defaults | one router, per-profile defaults |
| **Concurrency — transport** | may unrelated tool calls overlap? | fixed in 2.0 only (async dispatch) | one implementation, all tools |
| **Concurrency — scientific** | how many deliberative cycles at once? | machine-wide lock (`runtime_resources`) | unchanged, documented as distinct from transport |
| **Acceptance / promotion** | what may each profile touch? | checkout isolation + HANDOFF prose | the profile table (§6), enforced in code |
| **Evidence / provenance** | HEAD stamping, allowed engines, hashing | `git_head.py` (HEAD, now shared) + per-caller | one provenance module, one engine allow-list per profile |
| **Resource / quota** | budgets, worker counts, lock root | env vars in `runtime_resources` | same env vars, surfaced through the profile |
| **Editorial / manuscript** | is the prose rigorous, clear, self-contained, in the author's voice, free of internal-process leakage? | `PUBLICATION_POLICY.md` (frozen) + tacit editing | `docs/policy/EDITORIAL_POLICY_ES.md`, which operationalizes and defers to `PUBLICATION_POLICY.md` (§10) |
| **AI-signature** | does the finished prose read as author-voiced, not machine-generated? | separate `detector-ia` MCP | `detector-ia` exposed as an authoring-capability check (§10) |

`core/git_head.py` (this week) is the pattern in miniature: three callers with
private copies of one fragile routine, consolidated into a single hardened
implementation with a clear contract. This RFC scales that principle up.

## 9. ASTRUM's place

ASTRUM is a remote **node**, not a version. It is reached through
`astra_cluster_*` and the remote engines, and both orchestration strategies use
it today. Unification changes nothing about ASTRUM except that it is configured
and rate-limited in **one** resource layer instead of two — removing the risk of
two servers issuing conflicting remote work under one quota.

## 10. Authoring, editorial and AI-signature capability

Unification gives the service an **output side** that mirrors its compute side.
The science pipeline ends at accepted, reproducible evidence; the authoring
capability turns that evidence into a publication-ready manuscript, in English
or Spanish, under one explicit policy. It is built from three complementary
loops.

**1 — Evidence and acceptance (already in the RFC).** The campaign/cycle layers
plus `PUBLICATION_POLICY.md` guarantee the science is real, reproducible, and
extracted as a standalone artefact with a DOI.

**2 — Editorial policy.** `docs/policy/EDITORIAL_POLICY_ES.md` (Nelson's
canonical text) defines a senior-scientific-editor role for writing, review,
self-review and drafting: global structure first, then argument logic, section
and paragraph organization, text–equation–figure coherence, claim strength,
narrative, style, and only last grammar. It fixes the invariants the service
must always honour — N. Bolívar with both affiliations; co-authors never
invented, reordered or re-affiliated without authorization; equations, numbers,
figures and references never altered silently (flagged with
`[Scientific consistency check]`, `[Author decision required]`, etc.); the exact
acknowledgment string; author voice preserved; no over-claiming beyond the
evidence.

  Crucially, its §8 (no references to internal audit / validation campaign /
  pipeline / pass-fail / certification) is the **same rule** as the frozen
  `PUBLICATION_POLICY.md` §1, seen from the writing side. The editorial policy
  *operationalizes* the frozen policy and defers to it on that point; they are
  linked, not duplicated. This closes a real loop: ASTRA campaigns produce
  evidence carrying internal audit/verdict vocabulary (VALIDATED/REFUTED/…), and
  this policy is the output filter that keeps that vocabulary out of the paper —
  the editorial complement of the evidence/acceptance policy.

**3 — AI-signature check.** The existing `detector-ia` (a local detector of
AI-assisted writing) is exposed as an authoring-capability check. It is the
*empirical counterpart* of the editorial policy's §10/§45: the policy can only
*ask* that the prose keep the author's voice and not read as "una respuesta
generada mecánicamente"; the detector *measures* it. Editorial review and the
detector form a tight loop — edit toward the policy, measure the signature,
iterate — rather than either standing alone.

Integration follows the same unification argument as the science servers:
`detector-ia` is a separate MCP today, exactly as `astra`/`astra_dev` are;
folding its `detector_*` tools behind `ASTRA_AUTHORING_TOOLS` removes one more
divergent surface. Manuscript review/edit itself is delivered as (a) the
versioned policy file, injected into the authoring role's instructions when the
capability is on, and (b) optional `astra_manuscript_*` tools (proposed) for a
structured review → edit → signature-check pass. Bilingual by construction: the
policy keeps each manuscript in its original language unless asked otherwise.

## 11. Migration plan (phased, gated)

1. **Stop the drift (low risk).** Make `ASTRA-2.0` track production as its base
   and carry campaigns as an additive module, so an infra fix lands once. As the
   immediate, independently-valuable first step, **port this week's two fixes to
   production** (async dispatch; HEAD-without-subprocess).
2. **Introduce the profile abstraction.** Replace the scattered flags with one
   `ASTRA_PROFILE` resolving to the §6 table; keep the existing env vars as
   overrides. No behavior change yet — `production` = today's `astra`,
   `campaign` = today's `astra_dev`.
3. **Single binary, two registrations.** One `mcp_server/server.py` selects its
   tool surface from the profile. Register it twice (as `astra` and `astra_dev`)
   with different `ASTRA_PROFILE`, still from one codebase.
4. **Acceptance gate.** Campaigns remain off in `production` until G3–G6 pass
   (`ASTRA2_ACCEPTANCE.md`).
5. **Collapse the registration (post-acceptance).** One registered MCP with
   profile-selected capabilities; retire `astra_dev` as a separate entry.

Phases 1–3 are reversible and do not touch the science; phase 5 is the only one
that requires acceptance to be complete.

## 12. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Merging 2.0 into production leaks unaccepted behavior | Base is production; campaigns additive and gated; never copy 2.0 over prod |
| One server for real + experimental work widens blast radius | Async dispatch (done) isolates calls; profile gates campaigns; acceptance gates prove safety before they co-reside |
| Profile misconfiguration silently enables campaigns in prod | Fail-closed default (`production`); startup logs the resolved profile; a test asserts `production` exposes no `astra_campaign_*` |
| A shared ASTRUM client lets experiments starve production quota | One resource layer with per-profile budget ceilings |
| Big-bang refactor breaks the working verifier | Phased, reversible; each phase keeps the full suite green (currently 519 tests) |

## 13. Alternatives considered

- **Keep two servers (status quo).** Rejected: the manual-sync tax is real and
  already causing production to lag on fixes (§2).
- **Merge into one process now, campaigns always on.** Rejected: violates the
  acceptance boundary; an experimental bug could reach the production verifier.
- **Monorepo, two separate binaries.** Partial win (one codebase) but keeps two
  tool surfaces and two registrations to reason about; the profile model
  subsumes it at lower cost.

## 14. Open decisions for Nelson

1. **Base of record:** production as base with campaigns additive (recommended),
   or 2.0 as base with a production profile? (Recommended: production, to respect
   acceptance.)
2. **Language of these design docs** going forward (this RFC is English to match
   the folder; happy to keep a Spanish copy).
3. **How far to go now:** phases 1–2 only (stop drift + profile abstraction), or
   through phase 3 (single binary, two registrations)?
4. **Naming:** keep `astra` / `astra_dev` as the two registrations through
   phase 4, or rename earlier?
5. **Authoring scope (§10):** adopt the editorial policy as a document now and
   wire `detector-ia` behind `ASTRA_AUTHORING_TOOLS` in the same service, or keep
   `detector-ia` a separate MCP and adopt only the policy file? And do the
   `astra_manuscript_*` tools belong in this service, or in the existing
   `tesis-ia` authoring toolchain?

## 15. Rollback

Each phase is a separate commit on `astra-2.0` and is revertible. The production
checkout is not modified until phase 1's fix-port, which is itself a small,
reviewable patch gated on Nelson's explicit authorization (HANDOFF §9). No
remote push and no MCP re-registration happen without that authorization.
