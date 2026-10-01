# ASTRA Quality Benchmark v1

- Run: `quality_20261001_125525`
- Created: 2026-10-01T12:55:25.176497-03:00
- Tier: `standard`
- Configurations: no-ensemble
- Oracles: local
- Recorded runs: 27

## Headline metrics

| Metric | Value |
|---|---:|
| Scientific strict accuracy | 0.7407 |
| Scientific balanced accuracy | 0.7446 |
| False acceptance rate | 0.0 |
| Operational failure rate | 0.1111 |
| Validator defect recall | None |
| Critical defect recall | None |
| Execution verdict accuracy | None |
| Cross-run/oracle agreement | None |
| Latency p50 / p95 (s) | 418.204 / 1056.47 |

## Runs

| Case | Track | Config | Oracle | Expected | Observed | Correct | Seconds |
|---|---|---|---|---|---|---:|---:|
| `res_harmonic_gradient_factor_false` | cycle | no-ensemble | local | REFUTED | REFUTED | yes | 140.078 |
| `res_harmonic_gradient_subharmonic_true` | cycle | no-ensemble | local | VALIDATED | VALIDATED | yes | 418.204 |
| `res_kondo_b1_commutator_sign_false` | cycle | no-ensemble | local | REFUTED | REFUTED | yes | 235.578 |
| `res_kondo_b1_commutator_true` | cycle | no-ensemble | local | VALIDATED | VALIDATED | yes | 439.406 |
| `res_kondo_c1_commutator_x1_false` | cycle | no-ensemble | local | REFUTED | REFUTED | yes | 286.578 |
| `res_kondo_c1_norm_false` | cycle | no-ensemble | local | REFUTED | REFUTED | yes | 371.047 |
| `res_kondo_exchange_block_true` | cycle | no-ensemble | local | VALIDATED | VALIDATED | yes | 267.531 |
| `res_kondo_two_orbital_norms_true` | cycle | no-ensemble | local | VALIDATED | INCONCLUSIVE | no | 214.235 |
| `res_mobius_nagaoka_saturated_true` | cycle | no-ensemble | local | VALIDATED | VALIDATED | yes | 1083.109 |
| `res_mobius_nagaoka_wrong_flux_false` | cycle | no-ensemble | local | REFUTED | REVIEW_REJECTED | no | 994.312 |
| `res_su2_wu_yang_curvature_sign_false` | cycle | no-ensemble | local | REFUTED | REFUTED | yes | 174.297 |
| `res_su2_wu_yang_curvature_true` | cycle | no-ensemble | local | VALIDATED | VALIDATED | yes | 209.703 |
| `res_su3_charge_spectrum_true` | cycle | no-ensemble | local | VALIDATED | VALIDATED | yes | 146.797 |
| `res_gr_kinnersley_sign_false` | cycle | no-ensemble | local | REFUTED | REFUTED | yes | 566.969 |
| `res_gr_kinnersley_true` | cycle | no-ensemble | local | VALIDATED | VALIDATED | yes | 248.219 |
| `res_gr_planar_wall_rho_false` | cycle | no-ensemble | local | REFUTED | REFUTED | yes | 419.719 |
| `res_gr_planar_wall_true` | cycle | no-ensemble | local | VALIDATED | INCONCLUSIVE | no | 411.609 |
| `res_gr_static_shell_dec_false` | cycle | no-ensemble | local | REFUTED | API_ERROR | no | 1743.031 |
| `res_gr_static_shell_true` | cycle | no-ensemble | local | VALIDATED | REVIEW_REJECTED | no | 694.781 |
| `res_gr_unit_lapse_shell_pr_false` | cycle | no-ensemble | local | REFUTED | REFUTED | yes | 597.36 |
| `res_gr_unit_lapse_shell_true` | cycle | no-ensemble | local | VALIDATED | VALIDATED | yes | 487.687 |
| `res_quench_bogoliubov_uv_true` | cycle | no-ensemble | local | VALIDATED | INCONCLUSIVE | no | 347.328 |
| `res_quench_occupation_monotone_true` | cycle | no-ensemble | local | VALIDATED | INCONCLUSIVE | no | 722.219 |
| `res_quench_occupation_vanishes_at_zero_false` | cycle | no-ensemble | local | REFUTED | REFUTED | yes | 458.969 |
| `res_quench_uv_coefficient_false` | cycle | no-ensemble | local | REFUTED | REFUTED | yes | 237.515 |
| `res_rocket_mass_bound_reversed_false` | cycle | no-ensemble | local | REFUTED | REFUTED | yes | 873.297 |
| `res_rocket_mass_bound_true` | cycle | no-ensemble | local | VALIDATED | VALIDATED | yes | 677.484 |

The JSON report beside this file contains per-phase timings, reviewer labels,
oracle evidence, model resolution, and sanitized error details.
