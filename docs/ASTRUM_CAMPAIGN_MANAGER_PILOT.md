# Reversible ASTRUM campaign-manager pilot

This experiment adds campaign semantics above the existing ASTRUM scheduler.
It does **not** modify `remote/astra_cluster_manager.py`, install a daemon,
contact ASTRUM, or submit remote work.

The manifest contract provides:

- an immutable `campaign_id` plus canonical manifest SHA-256;
- per-campaign `max_concurrency`;
- unique task `idempotency_key` values;
- `afterok` and `afterany` dependencies with cycle rejection;
- an attempt ledger with parent-attempt lineage;
- retries only when the executor reports an operational failure class that the
  immutable manifest preregistered;
- terminal first-attempt treatment of every scientific failure, even when the
  task declares more than one possible attempt.

The executable example is
`docs/ASTRUM_CAMPAIGN_MANAGER_PILOT.json`.  It contains four independent small
tasks and one `afterany` aggregator.  One small task fails once with the
preregistered `transient_transport` class and succeeds on its second attempt.
Another returns a scientific `FAIL`; it is attempted exactly once.  The
aggregator still runs, but the campaign finishes as `completed_with_failures`,
so `afterany` cannot launder a failed scientific gate into campaign success.

Tests use a temporary SQLite database and a fake executor.  The production
scheduler remains the sole authority for ASTRUM CPU, GPU and memory admission.

## Risks before a real adapter

- Concurrency is currently enforced only inside one experimental campaign;
  global admission must continue to be delegated to ASTRUM.
- There is no crash-resume lease protocol yet.  A production adapter needs to
  reconcile persisted attempts with `astra_cluster_job` before resubmitting.
- Operational failure taxonomy must be narrow and immutable.  Scientific
  `FAIL`, nonzero physical gates, and ambiguous verdicts must never be mapped to
  retryable transport classes.
- Idempotency currently has campaign scope.  A production adapter should bind
  it to the submitted code/payload digest and the returned ASTRUM job ID.
- Backoff is implemented for the synchronous pilot; a persistent service would
  need wake-up scheduling rather than sleeping a manager process.

The next reversible step, if approved, is an adapter fake for the existing MCP
contract followed by a four-no-op remote smoke campaign.  It must not replace
or bypass the shared scheduler.
