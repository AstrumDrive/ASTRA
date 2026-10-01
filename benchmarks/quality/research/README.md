# Research corpus v1 (2026-09-30)

Twenty-seven `cycle` cases taken from Nelson's active research projects, not
from textbook exercises: Kondo two-orbital hierarchy (6), general relativity
energy identities and hollow-core shells (8), sudden mass quench of a free
scalar (4), relativistic rocket bound (2), harmonic-gradient identity (2),
SU(2)/SU(3) gauge checks (3) and the Mobius-strip Nagaoka theorem (2).
Fourteen claims are true (`expected: VALIDATED`) and thirteen carry a seeded
error (`expected: REFUTED`, the error named in `metadata.seeded_error`).

Every claim's truth value was measured independently before it entered the
corpus, by the scripts in `reference/` (SymPy Einstein tensors from scratch,
32-dimensional Jordan-Wigner matrices, sparse exact diagonalization). Their
deposited outputs are in `reference/outputs/`; a case is kept only when the
printed value of its `metadata.reference` id matches its `expected` field.
`metadata.provenance` points at the project file the claim came from.

Run (both arms, local oracle, re-anchored scoring):

```powershell
.\venv\Scripts\python.exe scripts\run_quality_benchmarks.py --case-root benchmarks\quality\research --no-legacy --tier standard --tracks cycle --oracle local --cycle-timeout 3000 --config single-model
.\venv\Scripts\python.exe scripts\run_quality_benchmarks.py --case-root benchmarks\quality\research --no-legacy --tier standard --tracks cycle --oracle local --cycle-timeout 3000 --config no-ensemble
```

Heavy cases carry their own oracle `timeout` (900 s for the symbolic Einstein
tensors, 600 s for the diagonalization); the runner widens the cycle budget to
`timeout + 900` s for them. Natario-bound claims were left out on purpose: the
paper is under review.

## v1.1 (2026-10-01)

The first measurement (`docs/evidence/RESEARCH_CLAIMS_COMPARISON_20260930.md`)
found two wording defects, both fixed in place and marked in
`metadata.revised`:

- `res_gr_static_shell_true` asserted the DEC equivalence under `m' >= 0`.
  At a radius with `m' = 0` both rho and p_perp vanish, so the DEC holds for
  any `2m/R < 1` and the equivalence fails; both arms refuted the v1 wording
  correctly. The claim now requires `m' > 0`
  (`reference/gr_reference.py` prints the loophole as
  `gr_static_shell_v1_wording_false_at_m_prime_zero: TRUE`), and the seeded
  sibling follows.
- The six Kondo cases reused `b`, `c` as both cross-product and spinor
  indices; the production reviewer rejected a validator over it. The
  cross-product indices are now `j`, `k`.

Results measured on the v1 wording stay valid for every other case. The
production arm was re-run on v1.1 the same day, after the validator-author
fix (section 5 of the evidence document): 20 / 27, no false acceptance and
no false refutation; the four remaining INCONCLUSIVE verdicts are all
multi-part claims, which v1.2 will split into one proposition per case.
