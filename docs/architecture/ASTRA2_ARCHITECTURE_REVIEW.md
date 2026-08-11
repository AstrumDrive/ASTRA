# ASTRA 2.0 architecture review

Status: design decision, not yet implemented  
Date: 2026-08-11  
Production impact: none

## Executive decision

ASTRA 2.0 should not begin as a generic Monte Carlo tree-search system. It
should begin as an evidence-guided research campaign controller built around
the existing atomic ASTRA cycle.

The production cycle already performs the expensive and valuable sequence:

1. independent Codex and AGY proposals;
2. cross-critique and Codex synthesis;
3. Claude validator authoring;
4. independent Codex code review;
5. deterministic execution through a selected oracle;
6. evidence audit and AGY navigation.

ASTRA 2.0 should preserve that verified worker and change how its proposals,
branches, evidence, and later cycles are represented and selected.

## Adversarial review of the first proposal

The first ASTRA 2.0 proposal had the correct direction but was too broad in six
places.

### 1. Too many first-class node types

Making objectives, claims, methods, evidence, dependencies, reviews, artifacts,
and decisions all independent graph entities from the first release would
increase schema and migration cost before demonstrating scientific uplift.

Decision: persist six operational records only—Campaign, Branch, Episode,
Claim, Evidence, and Decision. Method, provenance, review, and artifact data are
typed fields or linked manifests. A richer graph may be derived later.

### 2. A fixed four-branch portfolio was arbitrary

The useful number of branches depends on the objective, evidence cost, model
quota, and how different the proposals really are.

Decision: use progressive widening with two to four admissible branches, but
open only one primary branch initially. Promote another branch only after
negative/inconclusive evidence, method redundancy, evidence saturation, or a
high-value independent alternative.

### 3. A generic scalar-reward MCTS is epistemically unsafe

The existing prototype back-propagates one numeric reward. Scientific truth,
research usefulness, stability, novelty, and execution cost are not one scalar,
and a numerical failure can mean a false claim, an unstable representation, or
an invalid validator.

Decision: use hard admissibility gates followed by a visible priority vector.
Do not learn or collapse the vector in the initial release.

### 4. A full adversarial campaign on every episode wastes quota

Repeated reviewer-of-review calls are valuable for candidate final results but
can dominate cheap exploratory cycles.

Decision: keep the current pre-oracle code review for every executed validator.
Add a post-evidence adversarial campaign only when a result could close a
deliverable, enter a manuscript/client report, contradict an established
claim, or receive a high evidence grade.

### 5. Rigid model roles can become brittle

Codex, AGY, and Claude have useful primary roles, but provider availability and
the nature of a claim vary. Hard-coding one provider as universally best for a
phase makes the architecture fragile and weakens ablations.

Decision: retain the current primary roles while expressing them as a
capability policy with explicit fallbacks and actual-model telemetry.

### 6. The first proposal understated what ASTRA already has

ASTRA already stores independent proposals, critique, validator hashes, oracle
output, separate operational/scientific statuses, navigation, and a post-hoc
research graph. Reimplementing those facilities would create two sources of
truth.

Decision: promote existing cycle artifacts into live campaign state. Do not
duplicate the executor, validator router, model backend, or benchmark schemas.

## Minimal live data model

### Campaign

- immutable objective and success definition;
- deliverables and frozen resources;
- allowed evidence classes;
- wall-time, cycle, model-call, execution, and human-intervention budgets;
- status and aggregate goal coverage;
- protocol and source-commit fingerprints.

### Branch

- stable id and parent branch/episode;
- research direction and normalized method family;
- exact reason it differs from sibling branches;
- assumptions added or removed;
- proposed falsification/evidence plan;
- state: PROPOSED, ADMISSIBLE, ACTIVE, SUSPENDED, REFUTED, MERGED, EXHAUSTED,
  or CLOSED;
- priority vector and complete decision history.

### Episode

- one bounded invocation of the existing ASTRA atomic cycle;
- branch, direction, providers, actual models, budgets, timings, checkpoint;
- atomic, operational, oracle, and coverage statuses;
- references to claims and evidence.

### Claim

- normalized statement;
- claim type: universal, existential/counterexample, equivalence/derivation,
  numerical prediction, algorithmic guarantee, or scoped empirical claim;
- domain, quantifiers, assumptions, tolerance and units;
- support/refutation status and unresolved obligations.

### Evidence

- engine/oracle and artifact manifest;
- source and stdout hashes;
- scope and exact claim ids tested;
- outcome and failure class;
- evidence grade;
- independence links to other evidence;
- stability, precision, convergence, or formal-kernel metadata when applicable.

### Decision

- action: select, continue, split, promote, suspend, merge, close, or request
  human review;
- machine recommendation and deterministic policy result;
- reasons, budget snapshot, and alternatives considered.

The graph is a derived projection over these append-only records. The event log
is the audit source of truth.

## Five status axes that must remain separate

1. `operation_status`: did the phase or tool complete?
2. `claim_status`: supported, refuted, inconclusive, or not tested?
3. `evidence_grade`: what kind and strength of evidence exists?
4. `branch_status`: should this research direction continue?
5. `goal_coverage`: how much of the campaign objective is resolved?

A Python traceback cannot refute a scientific claim. Numerical instability
cannot by itself refute an exact expression. A correct bounded counterexample
can refute a universal claim even though the validator intentionally prints a
scientific FAIL. ASTRA already implements part of this separation; 2.0 extends
it to branch and campaign decisions.

## Evidence policy by claim type

| Claim type | Minimum credible evidence | Typical escalation |
|---|---|---|
| Universal theorem | Exact argument or explicit bounded scope | CAS/SMT, then Lean for selected obligations |
| Existential/refutation | One exact, admissible witness or counterexample | Minimality and independent reconstruction |
| Equivalence/derivation | Conditions plus exact residual/equality | Independent CAS and high-precision evaluation |
| Numerical prediction | Reproducibility, uncertainty, convergence, stability | Independent implementation/oracle |
| Algorithmic guarantee | Proof obligations plus executable sanity cases | Formalization of decisive lemmas |
| Scoped empirical claim | Frozen data/protocol and statistical uncertainty | Replication and holdout |

Numerical evidence may falsify or expose instability in a symbolic branch, but
it does not silently upgrade itself into a universal proof.

## Revised campaign algorithm

1. Freeze the research brief, budgets, resources, and protocol hash.
2. Run the existing parallel Codex/AGY proposal and critique phase.
3. Require the synthesis response to return a structured portfolio rather than
   erasing minority proposals:
   - selected atomic claim;
   - two to four admissible alternatives when they are materially different;
   - method family, assumption delta, and cheapest discriminating evidence for
     every candidate.
4. Execute only the selected claim through the existing translation, review,
   oracle, audit, and navigation stages.
5. Classify feedback as scientific refutation, invalid validator, operational
   error, numerical instability, formalization failure, or credible evidence.
6. Append the episode and evidence manifests to the campaign ledger.
7. Let models recommend the next action, but enforce deterministic constraints:
   - never promote a branch with a missing domain/quantifier contract;
   - never treat sampling as proof of a universal claim;
   - never treat operational failure as refutation;
   - never exceed the campaign or branch budget;
   - never declare the goal resolved while mandatory deliverables remain.
8. Continue the active branch when evidence is informative and the next
   obligation is clear. Activate an alternative only when it adds information,
   not merely more text.
9. Trigger the expanded adversarial campaign only at a scientific milestone.
10. End with complete result, structured partial progress, exhausted search,
    budget exhaustion, or an explicit human decision.

This design reuses the proposals ASTRA already pays for. It does not require an
additional branch-generation model round in the first implementation.

## Priority policy

### Hard gates

- relevant to an unresolved deliverable;
- falsifiable or formally scoped;
- explicit domain, assumptions, and quantifiers;
- feasible evidence plan;
- no duplicate method/claim already exhausted;
- remaining budget is sufficient.

### Visible priority vector

- expected information gain;
- current evidence strength;
- methodological independence;
- goal advancement;
- estimated execution and model cost;
- instability and hallucination risk.

The controller initially uses deterministic lexicographic/Pareto rules. The
Navigator supplies estimates and rationale, but cannot override hard gates.
Bayesian optimization remains available inside expensive continuous numerical
branches; it is not a truth score for proof branches.

## Model capability policy

- Codex primary: conjecture analysis, synthesis, proof/validator review, final
  scientific adjudication.
- AGY primary: alternative directions, cross-domain search, navigation,
  literature candidates, and adversarial challenge.
- Claude primary: new executable code, formal translation, bounded repair, and
  artifact refactoring.
- Deterministic engines: independent evidence, never rhetorical participants.

The strongest configured model is reserved for milestone verification,
cross-method reconciliation, or a branch whose expected value justifies the
cost. Every record stores the model that actually answered, including fallback.

## Concurrency policy

Parallelize only work that is scientifically independent and does not confound
subscription quotas:

- initial independent proposals and critiques;
- independent validator legs;
- parameter sweeps, seeds, formal jobs, and heavy oracle work;
- separate benchmark cases when quota controls permit.

Keep dependent authoring, review, execution, evidence audit, and navigation
ordered inside one episode. ASTRUM should accelerate evidence, not manufacture
apparent agentic depth through uncontrolled branch multiplication.

## Persistence and compatibility

Initial storage should remain simple and auditable:

```text
workspace/campaigns/<campaign_id>/
  campaign.json
  events.jsonl
  branches/<branch_id>.json
  episodes/<episode_id>.json
  evidence/<evidence_id>/manifest.json
  artifacts/
  checkpoint.json
```

Writes must be append-only or atomic-replace checkpoints. SQLite or a remote
database is deferred until concurrent campaign writers demonstrate a real need.

The existing `astra_cycle` remains the atomic worker. New development-only
interfaces may later be added as `astra_campaign_start`,
`astra_campaign_step`, `astra_campaign_status`, and `astra_campaign_stop`, but
they must not be registered in the production MCP before acceptance.

## Minimal vertical slice

The first implementation is intentionally narrower than the full vision:

1. campaign/branch/episode/evidence schemas and append-only ledger;
2. structured portfolio output from the existing ensemble synthesis;
3. live promotion of minority proposals to branch records;
4. one active branch with progressive widening;
5. deterministic branch gates and failure taxonomy;
6. current atomic cycle as the executor;
7. checkpoints and resume;
8. one frozen research-trajectory case against current ASTRA and `full-linear`.

Explicitly deferred:

- generic MCTS;
- learned branch rewards;
- hundreds of branches;
- universal autoformalization;
- automatic publication or novelty claims;
- UI rewrite;
- production MCP or ASTRUM deployment.

## Falsifiable success criterion

Under a matched model-call, wall-time, execution, and human-intervention budget,
the vertical slice must improve at least one preregistered trajectory outcome
(credible-evidence yield, recovery after negative evidence, blinded research
quality, or cost to useful partial progress) while preserving false-acceptance,
operational/scientific separation, and reproducibility.

If it only creates more branches, more prose, or more cycles without stronger
evidence or expert-rated progress, the architecture has failed and should not
replace the current loop.

