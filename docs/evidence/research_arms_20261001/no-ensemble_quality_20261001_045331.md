# ASTRA Quality Benchmark v1

- Run: `quality_20261001_045331`
- Created: 2026-10-01T04:53:31.350371-03:00
- Tier: `standard`
- Configurations: no-ensemble
- Oracles: local
- Recorded runs: 27

## Headline metrics

| Metric | Value |
|---|---:|
| Scientific strict accuracy | 0.5926 |
| Scientific balanced accuracy | 0.6017 |
| False acceptance rate | 0.0 |
| Operational failure rate | 0.1481 |
| Validator defect recall | None |
| Critical defect recall | None |
| Execution verdict accuracy | None |
| Cross-run/oracle agreement | None |
| Latency p50 / p95 (s) | 360.328 / 1121.714 |

## Runs

| Case | Track | Config | Oracle | Expected | Observed | Correct | Seconds |
|---|---|---|---|---|---|---:|---:|
| `res_harmonic_gradient_factor_false` | cycle | no-ensemble | local | REFUTED | REFUTED | yes | 165.75 |
| `res_harmonic_gradient_subharmonic_true` | cycle | no-ensemble | local | VALIDATED | VALIDATED | yes | 272.578 |
| `res_kondo_b1_commutator_sign_false` | cycle | no-ensemble | local | REFUTED | REFUTED | yes | 304.235 |
| `res_kondo_b1_commutator_true` | cycle | no-ensemble | local | VALIDATED | NON_DECIDABLE | no | 215.922 |
| `res_kondo_c1_commutator_x1_false` | cycle | no-ensemble | local | REFUTED | API_ERROR | no | 360.328 |
| `res_kondo_c1_norm_false` | cycle | no-ensemble | local | REFUTED | API_ERROR | no | 488.39 |
| `res_kondo_exchange_block_true` | cycle | no-ensemble | local | VALIDATED | NON_DECIDABLE | no | 326.735 |
| `res_kondo_two_orbital_norms_true` | cycle | no-ensemble | local | VALIDATED | NON_DECIDABLE | no | 366.015 |
| `res_mobius_nagaoka_saturated_true` | cycle | no-ensemble | local | VALIDATED | VALIDATED | yes | 894.672 |
| `res_mobius_nagaoka_wrong_flux_false` | cycle | no-ensemble | local | REFUTED | REFUTED | yes | 1198.266 |
| `res_su2_wu_yang_curvature_sign_false` | cycle | no-ensemble | local | REFUTED | REFUTED | yes | 191.406 |
| `res_su2_wu_yang_curvature_true` | cycle | no-ensemble | local | VALIDATED | API_ERROR | no | 480.313 |
| `res_su3_charge_spectrum_true` | cycle | no-ensemble | local | VALIDATED | VALIDATED | yes | 137.625 |
| `res_gr_kinnersley_sign_false` | cycle | no-ensemble | local | REFUTED | REFUTED | yes | 348.171 |
| `res_gr_kinnersley_true` | cycle | no-ensemble | local | VALIDATED | VALIDATED | yes | 328.906 |
| `res_gr_planar_wall_rho_false` | cycle | no-ensemble | local | REFUTED | REFUTED | yes | 220.453 |
| `res_gr_planar_wall_true` | cycle | no-ensemble | local | VALIDATED | INCONCLUSIVE | no | 598.672 |
| `res_gr_static_shell_dec_false` | cycle | no-ensemble | local | REFUTED | REFUTED | yes | 536.75 |
| `res_gr_static_shell_true` | cycle | no-ensemble | local | VALIDATED | REFUTED | no | 366.734 |
| `res_gr_unit_lapse_shell_pr_false` | cycle | no-ensemble | local | REFUTED | REFUTED | yes | 290.078 |
| `res_gr_unit_lapse_shell_true` | cycle | no-ensemble | local | VALIDATED | API_ERROR | no | 1423.766 |
| `res_quench_bogoliubov_uv_true` | cycle | no-ensemble | local | VALIDATED | INCONCLUSIVE | no | 173.891 |
| `res_quench_occupation_monotone_true` | cycle | no-ensemble | local | VALIDATED | INCONCLUSIVE | no | 568.484 |
| `res_quench_occupation_vanishes_at_zero_false` | cycle | no-ensemble | local | REFUTED | REFUTED | yes | 943.094 |
| `res_quench_uv_coefficient_false` | cycle | no-ensemble | local | REFUTED | REFUTED | yes | 288.312 |
| `res_rocket_mass_bound_reversed_false` | cycle | no-ensemble | local | REFUTED | REFUTED | yes | 395.063 |
| `res_rocket_mass_bound_true` | cycle | no-ensemble | local | VALIDATED | VALIDATED | yes | 513.203 |

The JSON report beside this file contains per-phase timings, reviewer labels,
oracle evidence, model resolution, and sanitized error details.
