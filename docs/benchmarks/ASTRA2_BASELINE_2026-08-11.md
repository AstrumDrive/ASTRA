# ASTRA 2.0 deterministic baseline — 2026-08-11

## Scope

This is the pre-implementation baseline for the isolated ASTRA 2.0 checkout.
It contains no ASTRA 2.0 scientific-orchestration changes.

- Source commit: `e4752eada0dc78b52cc88b98753ae144b6e56041`
- Branch: `astra-2.0`
- Python: `3.12.10`
- Environment fingerprint:
  `59f3d679d7790fe9b96eb1886b44cdbe88aa05f60e79dfe2acfae78df7ccfec5`

## Command

```powershell
.\venv\Scripts\python.exe -m pytest -q
```

## Result

```text
136 passed, 6 skipped, 2 subtests passed in 30.47s
```

The skipped tests require optional external benchmark caches such as miniF2F,
AInsteinBench, or SciCode. Their absence is explicit and does not count as a
scientific or operational PASS.

The production checkout contains an untracked
`tests/test_end_to_end_pipeline.py`; it was intentionally not imported because
the ASTRA 2.0 baseline contains only committed production state. That test must
be reviewed and either committed upstream or ported deliberately before G1 can
be closed.

## Interpretation

This result establishes a clean deterministic starting point only. It does not
validate the proposed ASTRA 2.0 campaign architecture, external engines,
ASTRUM, model CLIs, research quality, or comparative uplift.

The handoff-only changes were rechecked on 2026-08-12. The suite again reported
`136 passed, 6 skipped, 2 subtests passed`, in 26.76 seconds.

On the same date, the architecture audit passed without a required failure and
the trajectory runner produced an eight-cell dry-run schedule with protocol
fingerprint
`ef119a1e27e51481483ef1166792bec9442a3147c2e5f5436e3918eb2e079054`.
Neither command contacted a model or established an engine/ASTRUM acceptance
result.
