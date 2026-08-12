# ASTRA 2.0 first-slice implementation contract

Status: frozen for the first implementation slice

Date: 2026-08-12

Scope: pure domain records, deterministic policy, local persistence, and tests

This contract removes ambiguities before code is written. Changes to it require
an explicit design update and corresponding tests; they must not be introduced
implicitly while connecting model, MCP, GUI, or remote code.

## 1. General record contract

The initial schema identifier is `astra-campaign/0.1`. Every persisted record
must include:

- `schema_version`;
- a stable type-prefixed id;
- `campaign_id` except for the Campaign itself;
- timezone-aware RFC 3339 UTC timestamps;
- `source_commit`;
- typed references to related records;
- no machine-specific absolute path in portable scientific content.

Unknown schema versions fail closed. JSON serialization must be stable under a
load/dump round-trip. Hashes use canonical UTF-8 JSON with sorted keys and
compact separators.

## 2. Initial records

### Campaign

Required content: objective, success definition, mandatory deliverables, frozen
resource hashes, allowed evidence classes, budgets, status, and goal coverage.

Allowed status transitions:

```text
DRAFT → ACTIVE
ACTIVE → PAUSED | COMPLETED | EXHAUSTED | CANCELLED
PAUSED → ACTIVE | CANCELLED
```

Terminal states are immutable.

### Branch

Required content: parent branch/episode, direction, normalized method family,
material difference from siblings, assumption delta, cheapest discriminating
evidence plan, priority vector, budget, and decision history.

Allowed status transitions:

```text
PROPOSED → ADMISSIBLE | REJECTED
ADMISSIBLE → ACTIVE | SUSPENDED
ACTIVE → SUSPENDED | REFUTED | MERGED | EXHAUSTED | CLOSED
SUSPENDED → ACTIVE | REFUTED | MERGED | EXHAUSTED | CLOSED
```

Only one branch may be ACTIVE in the first slice. Terminal branch states are
immutable.

### Episode

One bounded use of an atomic worker. It records inputs, branch, providers,
actual models, budgets, timings, checkpoint, artifacts, and the five separate
status axes. The initial implementation stores Episodes but does not invoke
`astra_cycle`.

### Claim

Required content: exact statement, claim type, domain, quantifiers,
assumptions, tolerance, units, scope, and unresolved obligations.

Claim identity must not be a text hash alone. Its fingerprint covers a
canonical structured tuple of statement, domain, quantifiers, assumptions,
tolerance, units, and scope.

Initial claim types:

- `UNIVERSAL`;
- `EXISTENTIAL_OR_COUNTEREXAMPLE`;
- `EQUIVALENCE_OR_DERIVATION`;
- `NUMERICAL_PREDICTION`;
- `ALGORITHMIC_GUARANTEE`;
- `SCOPED_EMPIRICAL`.

### Evidence

Evidence kind and strength remain separate; they must not be collapsed into an
ordinal truth score.

Initial kinds: `COUNTEREXAMPLE`, `NUMERICAL`, `SYMBOLIC`, `FORMAL`,
`EMPIRICAL`, `LITERATURE`, and `HUMAN_REVIEW`.

Initial strengths: `PRELIMINARY`, `SCOPED`, `CORROBORATED`, and `CERTIFIED`.

Every Evidence record states exactly which Claim ids it tests, its scope,
engine/oracle, artifact hashes, independence links, and outcome. Relevant
precision, convergence, stability, kernel, source, or replication metadata is
mandatory for the corresponding kind.

Failure classes are distinct from scientific refutation:

- `SCIENTIFIC_REFUTATION`;
- `INVALID_VALIDATOR`;
- `OPERATIONAL_ERROR`;
- `NUMERICAL_INSTABILITY`;
- `FORMALIZATION_FAILURE`;
- `INCONCLUSIVE`.

### Decision

Initial actions: `SELECT`, `CONTINUE`, `SPLIT`, `PROMOTE`, `SUSPEND`, `MERGE`,
`CLOSE`, and `REQUEST_HUMAN_REVIEW`.

Every Decision stores the deterministic policy result, any model
recommendation separately, alternatives considered, reasons, and the complete
budget snapshot. A model recommendation cannot override a failed hard gate.

## 3. Five status axes

The implementation must not synthesize these into one status:

1. operation status;
2. claim status;
3. evidence kind/strength;
4. branch status;
5. campaign goal coverage.

## 4. Event envelope and replay

Every line of `events.jsonl` is one envelope:

```json
{
  "schema_version": "astra-campaign-event/0.1",
  "event_id": "evt_<stable-id>",
  "campaign_id": "cmp_<stable-id>",
  "sequence": 1,
  "event_type": "CAMPAIGN_CREATED",
  "occurred_at": "2026-08-12T00:00:00Z",
  "source_commit": "<git-sha>",
  "actor": "system|human|codex|agy|claude|oracle",
  "payload": {},
  "previous_event_sha256": null,
  "event_sha256": "<canonical-envelope-hash>"
}
```

Rules:

- sequences start at 1 and are contiguous;
- every event after the first links to the previous canonical hash;
- duplicate `event_id` plus identical hash is an idempotent no-op;
- duplicate id with different content fails closed;
- replay validates schema, sequence, ids, transitions, references, and hash
  chain before returning state;
- an incomplete final line is reported as `TRUNCATED_TAIL`: replay may expose
  the valid prefix for recovery, but the store is not healthy and must not
  append again until the tail is explicitly repaired or archived;
- corruption before the final line always fails closed.

The first slice is single-writer. A second simultaneous writer must be rejected;
multi-writer semantics are out of scope.

## 5. Checkpoints

A checkpoint contains the last applied sequence/hash and a complete derived
state. It is written to a sibling temporary file, flushed and `fsync`'d, then
published with `os.replace`. Loading validates it against the ledger; the
ledger remains the authority.

## 6. Hard gates and budgets

A branch is inadmissible if any condition fails:

- relevance to an unresolved deliverable;
- explicit falsifiable or formally bounded claim;
- explicit domain, assumptions, and quantifiers;
- feasible evidence plan;
- no exhausted duplicate claim/method;
- sufficient remaining budget.

Budget dimensions are recorded independently: cycles, model calls, wall time,
execution time, human interventions, and remote jobs. The first slice validates
and accounts synthetic budget events but performs no external work.

## 7. Files expected in this slice

Names are fixed unless a testable conflict with the existing code is found:

```text
core/campaign_models.py
core/campaign_store.py
core/campaign_policy.py
tests/test_campaign_models.py
tests/test_campaign_store.py
tests/test_campaign_policy.py
```

The modules may reuse `ResearchProgram` and established status helpers. They
must not duplicate the executor, engine router, CLI backend, validator repair,
or benchmark runner.

## 8. Out of scope

- model calls and prompt changes;
- `astra_cycle` integration;
- MCP tools;
- GUI;
- ASTRUM;
- generic MCTS or learned rewards;
- research-quality claims;
- production deployment.

## 9. Acceptance tests for the slice

- stable JSON round-trip for every record;
- invalid ids, timestamps, references, states, and transitions fail closed;
- claim fingerprints change when semantic scope changes;
- event append/replay is deterministic and idempotent;
- hash-chain mutation is detected;
- truncated-tail recovery is explicit and blocks writes;
- checkpoint publication and recovery survive simulated interruption;
- single-writer constraint is enforced;
- campaign budgets and active-branch invariant are enforced;
- full inherited regression suite plus new tests passes without model, network,
  MCP, or remote execution.
