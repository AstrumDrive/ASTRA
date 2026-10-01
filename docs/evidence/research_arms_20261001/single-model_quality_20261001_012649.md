# ASTRA Quality Benchmark v1

- Run: `quality_20261001_012649`
- Created: 2026-10-01T01:26:49.084315-03:00
- Tier: `standard`
- Configurations: single-model
- Oracles: local
- Recorded runs: 27

## Headline metrics

| Metric | Value |
|---|---:|
| Scientific strict accuracy | 0.4444 |
| Scientific balanced accuracy | 0.4506 |
| False acceptance rate | 0.0 |
| Operational failure rate | 0.3704 |
| Validator defect recall | None |
| Critical defect recall | None |
| Execution verdict accuracy | None |
| Cross-run/oracle agreement | None |
| Latency p50 / p95 (s) | 253.984 / 429.024 |

## Runs

| Case | Track | Config | Oracle | Expected | Observed | Correct | Seconds |
|---|---|---|---|---|---|---:|---:|
| `res_harmonic_gradient_factor_false` | cycle | single-model | local | REFUTED | REFUTED | yes | 127.015 |
| `res_harmonic_gradient_subharmonic_true` | cycle | single-model | local | VALIDATED | VALIDATED | yes | 173.5 |
| `res_kondo_b1_commutator_sign_false` | cycle | single-model | local | REFUTED | REFUTED | yes | 180.469 |
| `res_kondo_b1_commutator_true` | cycle | single-model | local | VALIDATED | CODE_ERROR | no | 267.969 |
| `res_kondo_c1_commutator_x1_false` | cycle | single-model | local | REFUTED | CODE_ERROR | no | 186.297 |
| `res_kondo_c1_norm_false` | cycle | single-model | local | REFUTED | CODE_ERROR | no | 376.265 |
| `res_kondo_exchange_block_true` | cycle | single-model | local | VALIDATED | CODE_ERROR | no | 246.313 |
| `res_kondo_two_orbital_norms_true` | cycle | single-model | local | VALIDATED | REFUTED | no | 235.656 |
| `res_mobius_nagaoka_saturated_true` | cycle | single-model | local | VALIDATED | CODE_ERROR | no | 503.469 |
| `res_mobius_nagaoka_wrong_flux_false` | cycle | single-model | local | REFUTED | CODE_ERROR | no | 439.89 |
| `res_su2_wu_yang_curvature_sign_false` | cycle | single-model | local | REFUTED | REFUTED | yes | 173.25 |
| `res_su2_wu_yang_curvature_true` | cycle | single-model | local | VALIDATED | VALIDATED | yes | 117.609 |
| `res_su3_charge_spectrum_true` | cycle | single-model | local | VALIDATED | CODE_ERROR | no | 195.829 |
| `res_gr_kinnersley_sign_false` | cycle | single-model | local | REFUTED | CODE_ERROR | no | 403.671 |
| `res_gr_kinnersley_true` | cycle | single-model | local | VALIDATED | CODE_ERROR | no | 281.704 |
| `res_gr_planar_wall_rho_false` | cycle | single-model | local | REFUTED | REFUTED | yes | 253.984 |
| `res_gr_planar_wall_true` | cycle | single-model | local | VALIDATED | VALIDATED | yes | 277.875 |
| `res_gr_static_shell_dec_false` | cycle | single-model | local | REFUTED | REFUTED | yes | 270.562 |
| `res_gr_static_shell_true` | cycle | single-model | local | VALIDATED | REFUTED | no | 314.688 |
| `res_gr_unit_lapse_shell_pr_false` | cycle | single-model | local | REFUTED | REFUTED | yes | 293.625 |
| `res_gr_unit_lapse_shell_true` | cycle | single-model | local | VALIDATED | VALIDATED | yes | 219.141 |
| `res_quench_bogoliubov_uv_true` | cycle | single-model | local | VALIDATED | INCONCLUSIVE | no | 145.187 |
| `res_quench_occupation_monotone_true` | cycle | single-model | local | VALIDATED | INCONCLUSIVE | no | 389.156 |
| `res_quench_occupation_vanishes_at_zero_false` | cycle | single-model | local | REFUTED | REFUTED | yes | 149.532 |
| `res_quench_uv_coefficient_false` | cycle | single-model | local | REFUTED | REFUTED | yes | 121.937 |
| `res_rocket_mass_bound_reversed_false` | cycle | single-model | local | REFUTED | CODE_ERROR | no | 287.594 |
| `res_rocket_mass_bound_true` | cycle | single-model | local | VALIDATED | SUBSTITUTED | no | 358.562 |

The JSON report beside this file contains per-phase timings, reviewer labels,
oracle evidence, model resolution, and sanitized error details.
