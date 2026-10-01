"""Generate research corpus v1.2: one proposition per case.

v1.1 (history/v1_1) bundled several propositions in one claim (four Kondo
norms, three planar-wall identities, four static-shell identities, three
unit-lapse identities, two quench statements, the rocket bound plus its
closed form). Both arms of the 2026-10-01 measurement wrote validators that
tested one part and the re-anchored analyst correctly refused to certify the
rest (INCONCLUSIVE). v1.2 states exactly one proposition per case, keeps every
definition inside the case text, and pairs each block of true claims with
seeded-false siblings that alter one thing.

Every case names the key of the reference script that measured its truth
(`metadata.reference`); `--check` compares each case's `expected` with the
deposited outputs in reference/outputs/*_20261001_v12.txt and fails if any
disagree, so a case cannot enter the corpus without a measured truth value.

    python benchmarks/quality/research/build_research_v1_2.py          # write cycle/research_v1_2.json
    python benchmarks/quality/research/build_research_v1_2.py --check  # write and verify against outputs
"""
from __future__ import annotations

import argparse
import glob
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "cycle" / "research_v1_2.json"
REF = "benchmarks/quality/research/reference/"

# ---------------------------------------------------------------------------
# Shared definition blocks (verbatim in every case that uses them)
# ---------------------------------------------------------------------------
KONDO = (
    "Model: an impurity spin-1/2 with operators S = sigma/2 acting on a two-dimensional factor, tensored with two "
    "orbitals n = 0, 1 of spin-1/2 fermions f_{n,sigma} (four modes 0up, 0dn, 1up, 1dn as Jordan-Wigner fermions on a "
    "16-dimensional Fock space; total dimension 32). The orbital-0 spin density is s_0^a = (1/2) sum_{b,c} f_{0b}^dagger "
    "(sigma^a)_{bc} f_{0c}, with b, c over up, dn. Exchange Hamiltonian H_J = J sum_a S^a s_0^a with J a nonzero real "
    "constant. Composite operators, with the operator product written in the order shown and the spinor index b running "
    "over up, dn: B_{n,sigma} = sum_{a,b} S^a (sigma^a)_{sigma b} f_{n b}; C_{n,sigma} = sum_{a,b} (S x s_0)^a "
    "(sigma^a)_{sigma b} f_{n b}, where (S x s_0)^a = epsilon_{ajk} S^j s_0^k with j, k over x, y, z; "
    "F_{1,sigma} = sum_{a,b} s_0^a (sigma^a)_{sigma b} f_{1 b}; number operators n_{0,sigma} = f_{0,sigma}^dagger "
    "f_{0,sigma}, double-occupancy projector P_{2,0} = n_{0up} n_{0dn}, single-occupancy projector P_{1,0} = n_{0up} + "
    "n_{0dn} - 2 P_{2,0}; U_{1,sigma} = B_{1,sigma} P_{1,0}; X_{1,sigma} = U_{1,sigma} + F_{1,sigma}; Y_{1,sigma} = "
    "U_{1,sigma} - F_{1,sigma}. Infinite-temperature metric (A|B) = Tr{A, B^dagger} / 32, with {., .} the "
    "anticommutator. Commutator [X, Y] = XY - YX."
)
KONDO_PROV = "Dev/physics/kondo_eom_minimal_hierarchy_codex (04_tests/verify_two_orbital_algebra.py, 03_equations/KNOWN_EXACT_RESULTS.md)"
KONDO_HOW = " Decide it by building every operator as an explicit 32 x 32 matrix and comparing exactly."
KONDO_CRIT = ["Construct the Jordan-Wigner fermions, the impurity spin and the composite operators as explicit 32 x 32 matrices.", "Compare exactly (trace or entrywise) and report the maximum deviation."]
KONDO_FAIL = ["Omit the fermion factor or change the stated product order.", "Check only one spin component."]

PLANAR = (
    "Coordinates (t, x, y, z). Metric ds^2 = -dt^2 + (dx - b(t,x) dt)^2 + dy^2 + dz^2, i.e. g_tt = -1 + b^2, "
    "g_tx = g_xt = -b, g_xx = g_yy = g_zz = 1, all other components zero, with b = b(t, x) an arbitrary smooth function, "
    "G = c = 1. Eulerian (normal) observer n^mu = (1, b, 0, 0). Energy density rho = G_{mu nu} n^mu n^nu / (8 pi); "
    "transverse pressures p_y = G_yy / (8 pi), p_z = G_zz / (8 pi); b_t = d b / dt, b_x = d b / dx."
)
PLANAR_PROV = "Dev/warp/energy_identities_ledger/outputs/planar_fast.py"
GR_HOW = " Derive the Einstein tensor symbolically for the generic function(s) in the metric and decide."
GR_CRIT = ["Compute the Einstein tensor symbolically for generic metric functions, not for a sample profile.", "State the exact expression obtained and compare it with the claim."]
GR_FAIL = ["Test only a special profile or a single point.", "Change a metric component or the observer."]

SHELL = (
    "Static spherically symmetric metric ds^2 = -N(R)^2 dT^2 + dR^2 / (1 - 2 m(R)/R) + R^2 dOmega^2, i.e. "
    "g_TT = -N^2, g_RR = 1/(1 - 2m/R), g_theta theta = R^2, g_phi phi = R^2 sin^2 theta, with m(R) and N(R) arbitrary "
    "smooth functions and R > 2m, G = c = 1. Mixed components define rho = -G^T_T / (8 pi), p_r = G^R_R / (8 pi), "
    "p_perp = G^theta_theta / (8 pi). 'Vanishing radial pressure' means p_r = 0 holds as an equation on the whole "
    "range of R considered, so it may be differentiated."
)
SHELL_PROV = "Dev/warp/energy_identities_ledger/outputs/shell_analytic.py"

KINN = (
    "Coordinates (u, r, theta, phi). Nonzero metric components: g_uu = -(1 - 2 m(u)/r - 2 a(u) r cos theta - "
    "a(u)^2 r^2 sin^2 theta), g_ur = g_ru = -1, g_u theta = g_theta u = a(u) r^2 sin theta, g_theta theta = r^2, "
    "g_phi phi = r^2 sin^2 theta; all other components vanish; m(u), a(u) arbitrary smooth, G = c = 1; m' = dm/du."
)
KINN_PROV = "Dev/warp/energy_identities_ledger/outputs/shell_acceleration_dec.py"

UNIT = (
    "Coordinates (t, r, theta, phi). Metric ds^2 = -dt^2 + (dr - beta(r) dt)^2 + r^2 dOmega^2, i.e. g_tt = -1 + "
    "beta^2, g_tr = g_rt = -beta, g_rr = 1, g_theta theta = r^2, g_phi phi = r^2 sin^2 theta, with beta = beta(r) an "
    "arbitrary smooth function, beta' = d beta / dr, G = c = 1. Eulerian observer n^mu = (1, beta, 0, 0); unit radial "
    "vector orthogonal to n: e_r^mu = (0, 1, 0, 0). rho = G_{mu nu} n^mu n^nu / (8 pi), p_r = G_{mu nu} e_r^mu e_r^nu / "
    "(8 pi), flux = -G_{mu nu} n^mu e_r^nu / (8 pi)."
)
UNIT_PROV = "Dev/warp/hollow-core-energy-conditions-reproducibility/derivations/verify_obstruction.py"

QUENCH = (
    "A free scalar field mode of momentum k has frequency omega_i = sqrt(k^2 + m_i^2) before and omega_f = sqrt(k^2 + "
    "m_f^2) after a sudden change of mass m_i -> m_f, with m_i > 0 and m_f > 0. Matching the mode function and its time "
    "derivative across the quench gives the real Bogoliubov coefficients alpha_k = (omega_f + omega_i) / (2 sqrt(omega_i "
    "omega_f)) and beta_k = (omega_f - omega_i) / (2 sqrt(omega_i omega_f)); the occupation is n_k = beta_k^2."
)
QUENCH_D = " Write m_f = m_i + d with d > 0."
QUENCH_PROV = "Dev/physics/quenched-scalar-field-keldysh-wigner-wavelet/output/para_Gabo_2026-09-10/auditoria_fisica (A1, A6)"
QUENCH_CRIT = ["Work symbolically with the exact expressions; numbers only as a check.", "State the exact result and compare it with the claim."]
QUENCH_FAIL = ["Expand omega to first order only.", "Sample a few values of k and extrapolate."]

ROCKET = (
    "Units c = 1. A rocket of instantaneous rest mass m ejects exhaust backward along its line of motion; in the rocket's "
    "instantaneous rest frame the ejected element carries momentum dP and energy dE >= dP (equality for null exhaust), so "
    "the rest mass changes by dm = -dE and the rapidity by d theta = dP / m. Exhaust of constant speed w (0 < w <= 1) has "
    "dE = dP / w. Integrate from rest mass m_0 at rapidity 0 to rest mass m_f at rapidity theta."
)
ROCKET_PROV = "Dev/warp/high_speed_subluminal_warp/outputs/unified_theorem_checks_20260918_local.json (theorem_B)"

HARM = (
    "Let alpha(x, y, z) be smooth on an open set of R^3 with alpha_xx + alpha_yy + alpha_zz = 0 (harmonic). Write "
    "|grad alpha|^2 = alpha_x^2 + alpha_y^2 + alpha_z^2 and |Hess alpha|^2 = sum_{i,j} (alpha_{ij})^2, the sum of the "
    "squares of all second partial derivatives."
)
HARM_PROV = "Dev/warp/high_speed_subluminal_warp/outputs/unified_theorem_checks_20260918_local.json (theorem_D)"

SU2 = (
    "Anti-Hermitian generators as explicit 2 x 2 matrices: T1 = [[0, -i/2], [-i/2, 0]], T2 = [[0, -1/2], [1/2, 0]], "
    "T3 = [[-i/2, 0], [0, i/2]]. Gauge potential components A_theta = w T1, A_phi = w sin(theta) T2 + cos(theta) T3, with "
    "w a real constant. The angular curvature component is F = d A_phi / d theta + (A_theta A_phi - A_phi A_theta)."
)
SU2_PROV = "Dev/physics/spectral-smarr-sun/validate_spectral_smarr.py::check_wuyang_curvature"
SU3 = (
    "Explicit 3 x 3 matrices T3 = -i diag(1, -1, 0) / 2 and T8 = -i diag(1, 1, -2) / (2 sqrt 3), the anti-Hermitian "
    "Cartan generators of su(3). Q = 4 pi (q3 T3 + q8 T8) with q3, q8 real parameters."
)
SU3_PROV = "Dev/physics/spectral-smarr-sun/validate_spectral_smarr.py::check_su3_spectrum"

MOBIUS = (
    "Lattice G(N, W, b) with N = 4, W = 2, b = 1: sites (n, m) with 0 <= n < 4 and 0 <= m < 2; nearest-neighbour bonds "
    "(n, m)-(n, m+1) across the strip and (n, m)-(n+1, m) along it; the longitudinal closure glues (N, m) to (0, W - 1 - m) "
    "(Mobius twist). Hamiltonian H = -t sum over bonds and spins of u_xy c^dagger_{x sigma} c_{y sigma} + h.c., t > 0, "
    "with exactly one hole (7 electrons on 8 sites) and infinite on-site repulsion (no double occupancy). The U(1) link "
    "variables u_xy are flat on every local square and carry total holonomy exp(2 pi i phi) around one longitudinal "
    "winding; a valid gauge puts the phase exp(2 pi i phi) on the four seam bonds (3, m)-(0, W - 1 - m) and 1 elsewhere."
)
MOBIUS_PROV = "Dev/physics/mobius_geometric_spin_transport/MOBIUS_NAGAOKA_THEOREM.md"
MOBIUS_CRIT = ["Build the one-hole Hamiltonian with the stated flux gauge and the fermionic signs of the hole hopping.", "Compute the ground-state energy of every S_z sector and the total spin of the global ground state."]
MOBIUS_FAIL = ["Omit the fermionic sign of the hole hopping.", "Break flatness on the seam squares when placing the flux."]


# ---------------------------------------------------------------------------
# Cases: (id, domain, expected, objective, definitions, claim, how, criteria, failures, reference, provenance, timeout, extra_meta)
# ---------------------------------------------------------------------------
def case(cid, domain, expected, objective, defs, claim, how, crit, fail, ref, prov, timeout=300, **meta):
    return {
        "id": cid, "track": "cycle", "domain": domain, "difficulty": "research", "expected": expected,
        "tags": ["research", "v1.2"],
        "objective": objective,
        "intuition": f"{defs} Claim: {claim}{how}",
        "success_criteria": crit, "failure_modes": fail, "timeout": timeout,
        "metadata": {"provenance": prov, "reference": ref, "corpus": "research_v1_2", **meta},
    }


CASES = [
    # --- Kondo norms (4 true + 2 false) ---------------------------------------
    case("res_kondo_norm_b0_true", "condensed_matter", "VALIDATED",
         "Determine whether (B_{0,sigma}|B_{0,sigma}) = 3/4 for sigma = up and for sigma = dn in the two-orbital Kondo model defined below.",
         KONDO, "(B_{0,sigma}|B_{0,sigma}) = 3/4 for sigma = up and for sigma = dn.", KONDO_HOW, KONDO_CRIT, KONDO_FAIL,
         REF + "kondo_reference.py::kondo_norm_b0_true", KONDO_PROV, split_from="res_kondo_two_orbital_norms_true"),
    case("res_kondo_norm_b0_false", "condensed_matter", "REFUTED",
         "Determine whether (B_{0,sigma}|B_{0,sigma}) = 3/8 for sigma = up and for sigma = dn in the two-orbital Kondo model defined below.",
         KONDO, "(B_{0,sigma}|B_{0,sigma}) = 3/8 for sigma = up and for sigma = dn.", KONDO_HOW, KONDO_CRIT, KONDO_FAIL,
         REF + "kondo_reference.py::kondo_norm_b0_false", KONDO_PROV, seeded_error="the true value is 3/4"),
    case("res_kondo_norm_b1_true", "condensed_matter", "VALIDATED",
         "Determine whether (B_{1,sigma}|B_{1,sigma}) = 3/4 for sigma = up and for sigma = dn in the two-orbital Kondo model defined below.",
         KONDO, "(B_{1,sigma}|B_{1,sigma}) = 3/4 for sigma = up and for sigma = dn.", KONDO_HOW, KONDO_CRIT, KONDO_FAIL,
         REF + "kondo_reference.py::kondo_norm_b1_true", KONDO_PROV, split_from="res_kondo_two_orbital_norms_true"),
    case("res_kondo_norm_c0_true", "condensed_matter", "VALIDATED",
         "Determine whether (C_{0,sigma}|C_{0,sigma}) = 3/8 for sigma = up and for sigma = dn in the two-orbital Kondo model defined below.",
         KONDO, "(C_{0,sigma}|C_{0,sigma}) = 3/8 for sigma = up and for sigma = dn.", KONDO_HOW, KONDO_CRIT, KONDO_FAIL,
         REF + "kondo_reference.py::kondo_norm_c0_true", KONDO_PROV, split_from="res_kondo_two_orbital_norms_true"),
    case("res_kondo_norm_c1_true", "condensed_matter", "VALIDATED",
         "Determine whether (C_{1,sigma}|C_{1,sigma}) = 3/16 for sigma = up and for sigma = dn in the two-orbital Kondo model defined below.",
         KONDO, "(C_{1,sigma}|C_{1,sigma}) = 3/16 for sigma = up and for sigma = dn.", KONDO_HOW, KONDO_CRIT, KONDO_FAIL,
         REF + "kondo_reference.py::kondo_norm_c1_true", KONDO_PROV, split_from="res_kondo_two_orbital_norms_true"),
    case("res_kondo_c1_norm_false", "condensed_matter", "REFUTED",
         "Determine whether (C_{1,sigma}|C_{1,sigma}) = 3/8 for sigma = up and for sigma = dn in the two-orbital Kondo model defined below.",
         KONDO, "(C_{1,sigma}|C_{1,sigma}) = 3/8 for sigma = up and for sigma = dn.", KONDO_HOW, KONDO_CRIT, KONDO_FAIL,
         REF + "kondo_reference.py::kondo_c1_norm_false", KONDO_PROV, seeded_error="the true value is 3/16"),
    # --- Kondo commutators (4 true + 3 false) --------------------------------
    case("res_kondo_b1_commutator_true", "condensed_matter", "VALIDATED",
         "Determine whether [B_{1,sigma}, H_J] = -i J C_{1,sigma} holds exactly for sigma = up and for sigma = dn in the two-orbital Kondo model defined below.",
         KONDO, "[B_{1,sigma}, H_J] = -i J C_{1,sigma} exactly, for sigma = up and for sigma = dn.", KONDO_HOW, KONDO_CRIT, KONDO_FAIL,
         REF + "kondo_reference.py::kondo_b1_commutator_true", KONDO_PROV),
    case("res_kondo_b1_commutator_sign_false", "condensed_matter", "REFUTED",
         "Determine whether [B_{1,sigma}, H_J] = +i J C_{1,sigma} holds exactly for sigma = up and for sigma = dn in the two-orbital Kondo model defined below.",
         KONDO, "[B_{1,sigma}, H_J] = +i J C_{1,sigma} exactly, for sigma = up and for sigma = dn.", KONDO_HOW, KONDO_CRIT, KONDO_FAIL,
         REF + "kondo_reference.py::kondo_b1_commutator_sign_false", KONDO_PROV, seeded_error="the true identity has -i J"),
    case("res_kondo_x1_commutator_true", "condensed_matter", "VALIDATED",
         "Determine whether [X_{1,sigma}, H_J] = 0 holds exactly for sigma = up and for sigma = dn in the two-orbital Kondo model defined below.",
         KONDO, "[X_{1,sigma}, H_J] = 0 exactly, for sigma = up and for sigma = dn.", KONDO_HOW, KONDO_CRIT, KONDO_FAIL,
         REF + "kondo_reference.py::kondo_x1_commutator_true", KONDO_PROV, split_from="res_kondo_exchange_block_true"),
    case("res_kondo_x1_commutator_false", "condensed_matter", "REFUTED",
         "Determine whether [X_{1,sigma}, H_J] = -i J C_{1,sigma} holds exactly for sigma = up and for sigma = dn in the two-orbital Kondo model defined below.",
         KONDO, "[X_{1,sigma}, H_J] = -i J C_{1,sigma} exactly, for sigma = up and for sigma = dn.", KONDO_HOW, KONDO_CRIT, KONDO_FAIL,
         REF + "kondo_reference.py::kondo_x1_commutator_false", KONDO_PROV, seeded_error="X_1 commutes with H_J; -i J C_1 is the commutator of B_1"),
    case("res_kondo_y1_commutator_true", "condensed_matter", "VALIDATED",
         "Determine whether [Y_{1,sigma}, H_J] = -2 i J C_{1,sigma} holds exactly for sigma = up and for sigma = dn in the two-orbital Kondo model defined below.",
         KONDO, "[Y_{1,sigma}, H_J] = -2 i J C_{1,sigma} exactly, for sigma = up and for sigma = dn.", KONDO_HOW, KONDO_CRIT, KONDO_FAIL,
         REF + "kondo_reference.py::kondo_y1_commutator_true", KONDO_PROV, split_from="res_kondo_exchange_block_true"),
    case("res_kondo_y1_commutator_sign_false", "condensed_matter", "REFUTED",
         "Determine whether [Y_{1,sigma}, H_J] = +2 i J C_{1,sigma} holds exactly for sigma = up and for sigma = dn in the two-orbital Kondo model defined below.",
         KONDO, "[Y_{1,sigma}, H_J] = +2 i J C_{1,sigma} exactly, for sigma = up and for sigma = dn.", KONDO_HOW, KONDO_CRIT, KONDO_FAIL,
         REF + "kondo_reference.py::kondo_y1_commutator_sign_false", KONDO_PROV, seeded_error="sign reversed"),
    case("res_kondo_c1_commutator_true", "condensed_matter", "VALIDATED",
         "Determine whether [C_{1,sigma}, H_J] = (i J / 2) Y_{1,sigma} holds exactly for sigma = up and for sigma = dn in the two-orbital Kondo model defined below.",
         KONDO, "[C_{1,sigma}, H_J] = (i J / 2) Y_{1,sigma} exactly, for sigma = up and for sigma = dn.", KONDO_HOW, KONDO_CRIT, KONDO_FAIL,
         REF + "kondo_reference.py::kondo_c1_commutator_true", KONDO_PROV, split_from="res_kondo_exchange_block_true"),
    case("res_kondo_c1_commutator_x1_false", "condensed_matter", "REFUTED",
         "Determine whether [C_{1,sigma}, H_J] = (i J / 2) X_{1,sigma} holds exactly for sigma = up and for sigma = dn in the two-orbital Kondo model defined below.",
         KONDO, "[C_{1,sigma}, H_J] = (i J / 2) X_{1,sigma} exactly, for sigma = up and for sigma = dn.", KONDO_HOW, KONDO_CRIT, KONDO_FAIL,
         REF + "kondo_reference.py::kondo_c1_commutator_x1_false", KONDO_PROV, seeded_error="the true right-hand side is (iJ/2) Y_1"),
    # --- Planar shift wall (3 true + 2 false) ----------------------------------
    case("res_gr_planar_wall_rho_zero_true", "general_relativity", "VALIDATED",
         "Determine whether the Eulerian energy density of the planar shift metric defined below vanishes identically for every smooth b(t, x).",
         PLANAR, "rho = 0 identically for every smooth b(t, x).", GR_HOW, GR_CRIT, GR_FAIL,
         REF + "gr_reference.py::gr_planar_wall_rho_zero_true", PLANAR_PROV, 900, split_from="res_gr_planar_wall_true"),
    case("res_gr_planar_wall_rho_false", "general_relativity", "REFUTED",
         "Determine whether the Eulerian energy density of the planar shift metric defined below equals -(b_x)^2 / (16 pi) for every smooth b(t, x).",
         PLANAR, "rho = -(b_x)^2 / (16 pi) identically.", GR_HOW, GR_CRIT, GR_FAIL,
         REF + "gr_reference.py::gr_planar_wall_rho_false", PLANAR_PROV, 900, seeded_error="rho vanishes identically for a planar wall"),
    case("res_gr_planar_wall_gxx_zero_true", "general_relativity", "VALIDATED",
         "Determine whether the coordinate component G_xx of the Einstein tensor of the planar shift metric defined below vanishes identically for every smooth b(t, x).",
         PLANAR, "G_xx = 0 identically for every smooth b(t, x).", GR_HOW, GR_CRIT, GR_FAIL,
         REF + "gr_reference.py::gr_planar_wall_gxx_zero_true", PLANAR_PROV, 900, split_from="res_gr_planar_wall_true"),
    case("res_gr_planar_wall_transverse_pressure_true", "general_relativity", "VALIDATED",
         "Determine whether the transverse pressures of the planar shift metric defined below satisfy p_y = p_z = -(1/(8 pi)) d/dx (b_t + b b_x) for every smooth b(t, x).",
         PLANAR, "p_y = p_z = -(1/(8 pi)) d/dx (b_t + b b_x) identically.", GR_HOW, GR_CRIT, GR_FAIL,
         REF + "gr_reference.py::gr_planar_wall_transverse_pressure_true", PLANAR_PROV, 900, split_from="res_gr_planar_wall_true"),
    case("res_gr_planar_wall_transverse_pressure_sign_false", "general_relativity", "REFUTED",
         "Determine whether the transverse pressures of the planar shift metric defined below satisfy p_y = p_z = +(1/(8 pi)) d/dx (b_t + b b_x) for every smooth b(t, x).",
         PLANAR, "p_y = p_z = +(1/(8 pi)) d/dx (b_t + b b_x) identically.", GR_HOW, GR_CRIT, GR_FAIL,
         REF + "gr_reference.py::gr_planar_wall_transverse_pressure_sign_false", PLANAR_PROV, 900, seeded_error="sign reversed"),
    # --- Static shell with p_r = 0 (4 true + 2 false) --------------------------
    case("res_gr_static_shell_rho_true", "general_relativity", "VALIDATED",
         "Determine whether rho = m'(R) / (4 pi R^2) for the static spherically symmetric metric defined below, for arbitrary smooth m(R) and N(R).",
         SHELL, "rho = m'(R) / (4 pi R^2) for arbitrary smooth m(R), N(R).", GR_HOW, GR_CRIT, GR_FAIL,
         REF + "gr_reference.py::gr_static_shell_rho_true", SHELL_PROV, 900, split_from="res_gr_static_shell_true"),
    case("res_gr_static_shell_lapse_true", "general_relativity", "VALIDATED",
         "Determine whether, for the static spherically symmetric metric defined below, p_r = 0 holds if and only if N'/N = m / (R (R - 2m)).",
         SHELL, "p_r = 0 if and only if N'/N = m / (R (R - 2m)).", GR_HOW, GR_CRIT, GR_FAIL,
         REF + "gr_reference.py::gr_static_shell_lapse_true", SHELL_PROV, 900, split_from="res_gr_static_shell_true"),
    case("res_gr_static_shell_pperp_true", "general_relativity", "VALIDATED",
         "Determine whether, for the static spherically symmetric metric defined below with vanishing radial pressure, p_perp = rho m / (2 (R - 2m)).",
         SHELL, "with vanishing radial pressure, p_perp = rho m / (2 (R - 2m)).", GR_HOW, GR_CRIT, GR_FAIL,
         REF + "gr_reference.py::gr_static_shell_pperp_true", SHELL_PROV, 900, split_from="res_gr_static_shell_true"),
    case("res_gr_static_shell_pperp_false", "general_relativity", "REFUTED",
         "Determine whether, for the static spherically symmetric metric defined below with vanishing radial pressure, p_perp = rho m / (R - 2m).",
         SHELL, "with vanishing radial pressure, p_perp = rho m / (R - 2m).", GR_HOW, GR_CRIT, GR_FAIL,
         REF + "gr_reference.py::gr_static_shell_pperp_false", SHELL_PROV, 900, seeded_error="the factor 2 in the denominator is missing"),
    case("res_gr_static_shell_dec_true", "general_relativity", "VALIDATED",
         "Determine whether, for the static spherically symmetric metric defined below with vanishing radial pressure and m' > 0, the dominant energy condition p_perp <= rho holds if and only if 2m/R <= 4/5.",
         SHELL, "with vanishing radial pressure and m' > 0 (so rho > 0), p_perp <= rho if and only if 2m/R <= 4/5.", GR_HOW,
         GR_CRIT + ["Derive p_perp / rho in closed form under p_r = 0 and solve p_perp = rho for 2m/R exactly."], GR_FAIL,
         REF + "gr_reference.py::gr_static_shell_dec_true", SHELL_PROV, 900, split_from="res_gr_static_shell_true"),
    case("res_gr_static_shell_dec_false", "general_relativity", "REFUTED",
         "Determine whether, for the static spherically symmetric metric defined below with vanishing radial pressure and m' > 0, the dominant energy condition p_perp <= rho holds if and only if 2m/R <= 2/3.",
         SHELL, "with vanishing radial pressure and m' > 0 (so rho > 0), p_perp <= rho if and only if 2m/R <= 2/3.", GR_HOW,
         GR_CRIT + ["Derive p_perp / rho in closed form under p_r = 0 and solve p_perp = rho for 2m/R exactly."], GR_FAIL,
         REF + "gr_reference.py::gr_static_shell_dec_false", SHELL_PROV, 900, seeded_error="the exact threshold is 2m/R = 4/5"),
    # --- Kinnersley (1 + 1) ----------------------------------------------------
    case("res_gr_kinnersley_true", "general_relativity", "VALIDATED",
         "Determine whether the Einstein tensor of the Kinnersley photon-rocket metric defined below has G_uu = 2 (3 m a cos theta - m') / r^2 and every other component zero, for arbitrary smooth m(u), a(u).",
         KINN, "G_uu = 2 (3 m a cos theta - m') / r^2 and every other component of G_{mu nu} vanishes identically.", GR_HOW, GR_CRIT, GR_FAIL,
         REF + "gr_reference.py::gr_kinnersley_true", KINN_PROV, 900),
    case("res_gr_kinnersley_sign_false", "general_relativity", "REFUTED",
         "Determine whether the Einstein tensor of the Kinnersley photon-rocket metric defined below has G_uu = 2 (m' - 3 m a cos theta) / r^2 for arbitrary smooth m(u), a(u).",
         KINN, "G_uu = 2 (m' - 3 m a cos theta) / r^2.", GR_HOW, GR_CRIT, GR_FAIL,
         REF + "gr_reference.py::gr_kinnersley_sign_false", KINN_PROV, 900, seeded_error="overall sign reversed"),
    # --- Unit-lapse shell (3 true + 2 false) -----------------------------------
    case("res_gr_unit_lapse_rho_true", "general_relativity", "VALIDATED",
         "Determine whether the Eulerian energy density of the unit-lapse metric defined below is rho = beta (2 r beta' + beta) / (8 pi r^2) for every smooth beta(r).",
         UNIT, "rho = beta (2 r beta' + beta) / (8 pi r^2) identically.", GR_HOW, GR_CRIT, GR_FAIL,
         REF + "gr_reference.py::gr_unit_lapse_rho_true", UNIT_PROV, 900, split_from="res_gr_unit_lapse_shell_true"),
    case("res_gr_unit_lapse_rho_false", "general_relativity", "REFUTED",
         "Determine whether the Eulerian energy density of the unit-lapse metric defined below is rho = beta (r beta' + beta) / (8 pi r^2) for every smooth beta(r).",
         UNIT, "rho = beta (r beta' + beta) / (8 pi r^2) identically.", GR_HOW, GR_CRIT, GR_FAIL,
         REF + "gr_reference.py::gr_unit_lapse_rho_false", UNIT_PROV, 900, seeded_error="the true numerator has 2 r beta'"),
    case("res_gr_unit_lapse_pr_true", "general_relativity", "VALIDATED",
         "Determine whether the Eulerian radial pressure of the unit-lapse metric defined below satisfies p_r = -rho identically for every smooth beta(r).",
         UNIT, "p_r + rho = 0 identically.", GR_HOW, GR_CRIT, GR_FAIL,
         REF + "gr_reference.py::gr_unit_lapse_pr_true", UNIT_PROV, 900, split_from="res_gr_unit_lapse_shell_true"),
    case("res_gr_unit_lapse_shell_pr_false", "general_relativity", "REFUTED",
         "Determine whether the Eulerian radial pressure of the unit-lapse metric defined below satisfies p_r = rho identically for every smooth beta(r).",
         UNIT, "p_r = rho identically.", GR_HOW, GR_CRIT, GR_FAIL,
         REF + "gr_reference.py::gr_unit_lapse_shell_pr_false", UNIT_PROV, 900, seeded_error="the identity is p_r = -rho"),
    case("res_gr_unit_lapse_flux_true", "general_relativity", "VALIDATED",
         "Determine whether the Eulerian energy flux of the unit-lapse metric defined below vanishes identically for every smooth beta(r).",
         UNIT, "flux = 0 identically.", GR_HOW, GR_CRIT, GR_FAIL,
         REF + "gr_reference.py::gr_unit_lapse_flux_true", UNIT_PROV, 900, split_from="res_gr_unit_lapse_shell_true"),
    # --- Quench (4 true + 2 false) ---------------------------------------------
    case("res_quench_normalization_true", "quantum_field_theory", "VALIDATED",
         "Determine whether the Bogoliubov coefficients of the sudden mass quench defined below satisfy alpha_k^2 - beta_k^2 = 1 for every real k.",
         QUENCH, "alpha_k^2 - beta_k^2 = 1 for every real k.", " Verify exactly.", QUENCH_CRIT, QUENCH_FAIL,
         REF + "misc_reference.py::quench_normalization_true", QUENCH_PROV, split_from="res_quench_bogoliubov_uv_true"),
    case("res_quench_uv_limit_true", "quantum_field_theory", "VALIDATED",
         "Determine whether the occupation n_k of the sudden mass quench defined below satisfies k^4 n_k -> (m_f^2 - m_i^2)^2 / 16 as k -> infinity.",
         QUENCH, "lim_{k -> infinity} k^4 n_k = (m_f^2 - m_i^2)^2 / 16.", " Compute the exact limit.", QUENCH_CRIT, QUENCH_FAIL,
         REF + "misc_reference.py::quench_uv_limit_true", QUENCH_PROV, split_from="res_quench_bogoliubov_uv_true"),
    case("res_quench_uv_coefficient_false", "quantum_field_theory", "REFUTED",
         "Determine whether the occupation n_k of the sudden mass quench defined below satisfies k^4 n_k -> (m_f^2 - m_i^2)^2 / 8 as k -> infinity.",
         QUENCH, "lim_{k -> infinity} k^4 n_k = (m_f^2 - m_i^2)^2 / 8.", " Compute the exact limit; if false, state the correct coefficient.", QUENCH_CRIT, QUENCH_FAIL,
         REF + "misc_reference.py::quench_uv_coefficient_false", QUENCH_PROV, seeded_error="the exact coefficient is 1/16"),
    case("res_quench_occupation_decreasing_true", "quantum_field_theory", "VALIDATED",
         "Determine whether, for the sudden mass quench defined below with m_f = m_i + d and d > 0, the occupation n_k is strictly decreasing in k on (0, infinity).",
         QUENCH + QUENCH_D, "n_k is strictly decreasing in k on (0, infinity), i.e. d n_k / dk < 0 for every k > 0.",
         " Establish the sign of the derivative analytically for all admissible m_i, d.", QUENCH_CRIT, QUENCH_FAIL,
         REF + "misc_reference.py::quench_occupation_decreasing_true", QUENCH_PROV, split_from="res_quench_occupation_monotone_true"),
    case("res_quench_occupation_limit_true", "quantum_field_theory", "VALIDATED",
         "Determine whether, for the sudden mass quench defined below with m_f = m_i + d and d > 0, the occupation n_k tends to d^2 / (4 m_i (m_i + d)) as k -> 0.",
         QUENCH + QUENCH_D, "lim_{k -> 0} n_k = d^2 / (4 m_i (m_i + d)).", " Compute the exact limit.", QUENCH_CRIT, QUENCH_FAIL,
         REF + "misc_reference.py::quench_occupation_limit_true", QUENCH_PROV, split_from="res_quench_occupation_monotone_true"),
    case("res_quench_occupation_vanishes_at_zero_false", "quantum_field_theory", "REFUTED",
         "Determine whether, for the sudden mass quench defined below with m_f = m_i + d and d > 0, the occupation n_k tends to zero as k -> 0.",
         QUENCH + QUENCH_D, "lim_{k -> 0} n_k = 0.", " Compute the exact limit; if false, state its value.", QUENCH_CRIT, QUENCH_FAIL,
         REF + "misc_reference.py::quench_occupation_vanishes_at_zero_false", QUENCH_PROV, seeded_error="the limit is d^2/(4 m_i (m_i + d)) > 0"),
    # --- Rocket (2 true + 2 false) ---------------------------------------------
    case("res_rocket_bound_true", "special_relativity", "VALIDATED",
         "Determine whether a rocket in special relativity that reaches rapidity theta by ejecting exhaust backward always satisfies m_f / m_0 <= exp(-theta), whatever the exhaust.",
         ROCKET, "m_f / m_0 <= exp(-theta) for every admissible exhaust law.", " Prove it from the differential relations, and exhibit the equality case.",
         ["Derive -dm/m >= d theta and integrate it.", "Name the exhaust that attains equality."], ["Use the non-relativistic rocket equation.", "Confuse rapidity with velocity."],
         REF + "misc_reference.py::rocket_bound_true", ROCKET_PROV, split_from="res_rocket_mass_bound_true"),
    case("res_rocket_mass_bound_reversed_false", "special_relativity", "REFUTED",
         "Determine whether a rocket in special relativity that reaches rapidity theta by ejecting exhaust backward always satisfies m_f / m_0 >= exp(-theta), whatever the exhaust.",
         ROCKET, "m_f / m_0 >= exp(-theta) for every admissible exhaust law.", " Decide it; one admissible exhaust law that violates it refutes it.",
         ["Produce an explicit exhaust law and its mass ratio compared with exp(-theta)."], ["Check only the photon rocket, where equality holds."],
         REF + "misc_reference.py::rocket_mass_bound_reversed_false", ROCKET_PROV, seeded_error="the inequality runs the other way; massive exhaust gives a strictly smaller ratio"),
    case("res_rocket_constant_w_true", "special_relativity", "VALIDATED",
         "Determine whether exhaust ejected at constant speed w (0 < w <= 1) gives m_f / m_0 = exp(-theta / w) for the relativistic rocket defined below.",
         ROCKET, "for exhaust of constant speed w, m_f / m_0 = exp(-theta / w).", " Integrate the differential relations and confirm numerically.",
         ["Integrate dm/m = -d theta / w exactly.", "Confirm the closed form against a direct numerical integration at two values of w."], ["Use dE = dP for massive exhaust.", "Confuse w with the rocket's own velocity."],
         REF + "misc_reference.py::rocket_constant_w_true", ROCKET_PROV, split_from="res_rocket_mass_bound_true"),
    case("res_rocket_constant_w_false", "special_relativity", "REFUTED",
         "Determine whether exhaust ejected at constant speed w (0 < w <= 1) gives m_f / m_0 = exp(-theta w) for the relativistic rocket defined below.",
         ROCKET, "for exhaust of constant speed w, m_f / m_0 = exp(-theta w).", " Integrate the differential relations; if false, give the correct closed form.",
         ["Integrate dm/m = -d theta / w exactly and compare the two closed forms at w = 1/2."], ["Test only w = 1, where both forms agree."],
         REF + "misc_reference.py::rocket_constant_w_false", ROCKET_PROV, seeded_error="the exponent is -theta / w"),
    # --- Harmonic gradient (1 + 1) ---------------------------------------------
    case("res_harmonic_gradient_subharmonic_true", "analysis", "VALIDATED",
         "Determine whether Laplacian(|grad alpha|^2) = 2 |Hess alpha|^2 holds for every harmonic alpha on an open set of R^3.",
         HARM, "Laplacian(|grad alpha|^2) = 2 |Hess alpha|^2 for every harmonic alpha.", " Give a derivation valid for every harmonic alpha and check it on concrete harmonic functions.",
         ["Derive the identity symbolically using only the Laplace equation.", "Check it on at least two concrete harmonic functions."], ["Verify only polynomial examples and stop.", "Forget the term grad alpha . grad(Laplacian alpha)."],
         REF + "misc_reference.py::harmonic_gradient_subharmonic_true", HARM_PROV),
    case("res_harmonic_gradient_factor_false", "analysis", "REFUTED",
         "Determine whether Laplacian(|grad alpha|^2) = |Hess alpha|^2 holds for every harmonic alpha on an open set of R^3.",
         HARM, "Laplacian(|grad alpha|^2) = |Hess alpha|^2 for every harmonic alpha.", " Decide it; if false, give the correct factor and a harmonic alpha that exhibits the discrepancy.",
         ["Exhibit a harmonic function for which the two sides differ, with both sides computed exactly."], ["Pick alpha linear, where both sides vanish."],
         REF + "misc_reference.py::harmonic_gradient_factor_false", HARM_PROV, seeded_error="the correct factor is 2"),
    # --- SU(2) / SU(3) (2 + 2) -------------------------------------------------
    case("res_su2_wu_yang_curvature_true", "gauge_theory", "VALIDATED",
         "Determine whether the angular curvature component F of the SU(2) potential defined below equals (w^2 - 1) sin(theta) T3 for every real w.",
         SU2, "F = (w^2 - 1) sin(theta) T3 for all theta and all real w.", " Verify by explicit matrix computation.",
         ["Compute the derivative and the commutator as explicit matrices and compare entrywise."], ["Use Hermitian generators sigma/2 without the factor -i.", "Evaluate at a single theta."],
         REF + "misc_reference.py::su2_wu_yang_curvature_true", SU2_PROV),
    case("res_su2_wu_yang_curvature_sign_false", "gauge_theory", "REFUTED",
         "Determine whether the angular curvature component F of the SU(2) potential defined below equals (1 - w^2) sin(theta) T3 for every real w.",
         SU2, "F = (1 - w^2) sin(theta) T3 for all theta and all real w.", " Decide by explicit matrix computation; if false, give the correct right-hand side.",
         ["Compute F exactly and compare with both candidate signs."], ["Test w = 1 or w = -1 only, where both sides vanish."],
         REF + "misc_reference.py::su2_wu_yang_curvature_sign_false", SU2_PROV, seeded_error="overall sign reversed"),
    case("res_su3_charge_spectrum_true", "gauge_theory", "VALIDATED",
         "Determine whether the matrix Q defined below has eigenvalues -2 pi i (q3 + q8 / sqrt 3), 2 pi i (q3 - q8 / sqrt 3) and 4 pi i q8 / sqrt 3 for all real q3, q8.",
         SU3, "the eigenvalues of Q are exactly -2 pi i (q3 + q8 / sqrt 3), 2 pi i (q3 - q8 / sqrt 3) and 4 pi i q8 / sqrt 3.", " Verify symbolically for generic q3, q8.",
         ["Compute the eigenvalues symbolically and match each stated expression."], ["Compare numerically at one point only."],
         REF + "misc_reference.py::su3_charge_spectrum_true", SU3_PROV),
    case("res_su3_charge_spectrum_false", "gauge_theory", "REFUTED",
         "Determine whether the matrix Q defined below has eigenvalues -2 pi i (q3 + q8 / sqrt 3), 2 pi i (q3 - q8 / sqrt 3) and 2 pi i q8 / sqrt 3 for all real q3, q8.",
         SU3, "the eigenvalues of Q are exactly -2 pi i (q3 + q8 / sqrt 3), 2 pi i (q3 - q8 / sqrt 3) and 2 pi i q8 / sqrt 3.", " Decide symbolically; if false, give the correct third eigenvalue.",
         ["Compute the eigenvalues symbolically and compare each with the stated expressions."], ["Check only tracelessness, which the false set violates but a wrong set could satisfy."],
         REF + "misc_reference.py::su3_charge_spectrum_false", SU3_PROV, seeded_error="the third eigenvalue is 4 pi i q8 / sqrt 3"),
    # --- Mobius (1 + 1) ---------------------------------------------------------
    case("res_mobius_nagaoka_saturated_true", "condensed_matter", "VALIDATED",
         "Determine whether the ground state of the one-hole infinite-U Hubbard model on the Mobius strip G(4, 2, 1) defined below, with flux phi = 1/2, has total spin S = 7/2.",
         MOBIUS, "for phi = 1/2 the ground state has total spin S = 7/2.", " Decide by exact diagonalization of the 1024-dimensional one-hole space.", MOBIUS_CRIT, MOBIUS_FAIL,
         REF + "mobius_reference.py::mobius_nagaoka_saturated_true", MOBIUS_PROV, 600),
    case("res_mobius_nagaoka_wrong_flux_false", "condensed_matter", "REFUTED",
         "Determine whether the ground state of the one-hole infinite-U Hubbard model on the Mobius strip G(4, 2, 1) defined below, with zero flux, has total spin S = 7/2.",
         MOBIUS, "for phi = 0 (all link variables equal to 1) the ground state has total spin S = 7/2.", " Decide by exact diagonalization of the 1024-dimensional one-hole space; if false, report the actual ground-state spin.", MOBIUS_CRIT, MOBIUS_FAIL,
         REF + "mobius_reference.py::mobius_nagaoka_wrong_flux_false", MOBIUS_PROV, 600, seeded_error="at phi = 0 exact diagonalization gives S = 1/2"),
]


def measured_truth() -> dict[str, str]:
    truth: dict[str, str] = {}
    for path in glob.glob(str(HERE / "reference" / "outputs" / "*_20261001_v12.txt")):
        for m in re.finditer(r"^(\w+): (TRUE|FALSE)$", Path(path).read_text(encoding="utf-8", errors="replace"), re.M):
            truth[m.group(1)] = m.group(2)
    return truth


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify every expected verdict against the deposited reference outputs")
    args = ap.parse_args()
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids)), "duplicate ids"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(CASES, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    n_true = sum(c["expected"] == "VALIDATED" for c in CASES)
    print(f"wrote {OUT.relative_to(HERE.parent.parent.parent)}: {len(CASES)} cases, {n_true} true, {len(CASES) - n_true} seeded false")
    if args.check:
        truth = measured_truth()
        bad = []
        for c in CASES:
            key = c["metadata"]["reference"].split("::")[1]
            want = "TRUE" if c["expected"] == "VALIDATED" else "FALSE"
            if truth.get(key) != want:
                bad.append((c["id"], key, truth.get(key), want))
        if bad:
            print("MISMATCH (case, reference key, measured, wanted):")
            for row in bad:
                print("  ", row)
            return 1
        print(f"check: all {len(CASES)} expected verdicts match the measured reference outputs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
