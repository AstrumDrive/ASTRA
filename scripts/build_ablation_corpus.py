#!/usr/bin/env python3
"""Build and verify the review-independence ablation corpus.

Validators live as real, executable Python files under
``benchmarks/quality/validator_audit/cases/``. Defective variants are derived
from a sound base by localized patches, so the injected defect is explicit and
auditable instead of being spread through a hand-written copy, and the sound
and defective members of a pair are matched on domain and difficulty.

Every case passes three gates before it is written:

* the sound base executes and prints the verdict it declares;
* each defective variant also executes and still prints ``VERDICT: PASS``,
  which is what makes it dangerous rather than merely broken;
* each patch applies exactly once, so a defect cannot silently fail to land.

Usage:
    python scripts/build_ablation_corpus.py --verify        # gates only
    python scripts/build_ablation_corpus.py --write         # gates, then emit
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASE_DIR = ROOT / "benchmarks" / "quality" / "validator_audit" / "cases"
OUT_DIR = ROOT / "benchmarks" / "quality" / "validator_audit"
PYTHON = ROOT / "venv" / "Scripts" / "python.exe"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)

# Labels the reviewer prompt and core/review_defects.py both recognise.
KNOWN_LABELS = {
    "hardcoded_pass", "unreachable_failure", "self_comparison", "sampling_as_proof",
    "wrong_domain", "missing_assumption", "wrong_tolerance", "wrong_units",
    "unknown_as_pass", "swallowed_exception", "missing_dependency",
    "engine_mismatch", "unsimplified_symbolic_zero", "assumed_bound",
    "undecidable_positivity", "link_in_comment", "proxy_continuity",
    "missing_domain",
}

LONG_MIN = 120     # a validator below this is a snippet, not a realistic one
LONG_MAX = 320


# --------------------------------------------------------------------- registry
# Each entry: one sound base plus the defective variants derived from it.
REGISTRY: list[dict] = [
    {
        "base": "sr_velocity_addition",
        "domain": "special_relativity",
        "objective": (
            "Establish that relativistic velocity composition cannot produce a "
            "superluminal result for subluminal inputs."
        ),
        "intuition": (
            "For |u| < c and |v| < c the composition w = (u+v)/(1+uv/c^2) "
            "satisfies |w| < c, and reduces to u+v when c grows without bound."
        ),
        "defects": [
            {
                "suffix": "sampling",
                "primary": "sampling_as_proof",
                "labels": ["sampling_as_proof"],
                "severity": "critical",
                "note": "the universal bound is left to 4000 random draws",
                "patches": [
                    (
                        'difference = sp.simplify(c**2 - W**2)',
                        'difference = 0  # symbolic leg dropped; sampling below is the evidence',
                    ),
                    (
                        'expected_form = (c**2 - u**2) * (c**2 - v**2) * c**2 / (c**2 + u * v) ** 2\n'
                        'residual = sp.simplify(sp.together(difference - expected_form))\n'
                        'check("symbolic_factorization", residual == 0, f"residual={residual}")',
                        '# The random draws below cover the domain densely enough to stand in\n'
                        '# for the algebraic factorization.',
                    ),
                    (
                        'rapidity = W.subs({u: c * sp.tanh(alpha), v: c * sp.tanh(beta)})\n'
                        'collapsed = sp.simplify(sp.expand_trig(sp.simplify(rapidity)) - c * sp.tanh(alpha + beta))\n'
                        'check(\n'
                        '    "rapidity_collapse",\n'
                        '    sp.simplify(collapsed) == 0,\n'
                        '    "w = c*tanh(alpha+beta) on the open domain",\n'
                        ')',
                        '# Rapidity argument omitted.',
                    ),
                ],
            },
            {
                "suffix": "unknown_pass",
                "primary": "unknown_as_pass",
                "labels": ["unknown_as_pass"],
                "severity": "critical",
                "note": "an undecided symbolic query is accepted as success",
                "patches": [
                    (
                        '    if ok is True:\n'
                        '        print(f"CHECK {name}: OK {detail}".rstrip())\n'
                        '        return True',
                        '    if ok is not False:\n'
                        '        # Treat an undecided query as satisfied: sympy returning None\n'
                        '        # only means it could not find a proof quickly.\n'
                        '        print(f"CHECK {name}: OK {detail}".rstrip())\n'
                        '        return True',
                    ),
                ],
            },
            {
                "suffix": "self_comparison",
                "primary": "self_comparison",
                "labels": ["self_comparison"],
                "severity": "critical",
                "note": "the factorization is compared against itself",
                "patches": [
                    (
                        'expected_form = (c**2 - u**2) * (c**2 - v**2) * c**2 / (c**2 + u * v) ** 2',
                        'expected_form = sp.simplify(c**2 - W**2)  # same quantity, recomputed',
                    ),
                ],
            },
            {
                "suffix": "tolerance",
                "primary": "wrong_tolerance",
                "labels": ["wrong_tolerance"],
                "severity": "major",
                "note": "a one percent slack admits genuinely superluminal results",
                "patches": [
                    (
                        '    if not abs(w) < 1.0:\n'
                        '        numeric_ok = False\n'
                        '        break',
                        '    if not abs(w) < 1.0 + 1e-2:  # numerical slack\n'
                        '        numeric_ok = False\n'
                        '        break',
                    ),
                    (
                        'check("numeric_subluminal", numeric_ok and worst < 1.0,',
                        'check("numeric_subluminal", numeric_ok and worst < 1.0 + 1e-2,',
                    ),
                ],
            },
        ],
    },
    {
        "base": "qm_pauli_algebra",
        "domain": "quantum_mechanics",
        "objective": (
            "Establish that the Pauli matrices close the su(2) algebra exactly, "
            "with no free parameter left in the structure constants."
        ),
        "intuition": (
            "The commutators [s_i, s_j] = 2i eps_ijk s_k and anticommutators "
            "{s_i, s_j} = 2 delta_ij I hold exactly, and together fix the product."
        ),
        "defects": [
            {
                "suffix": "unreachable_fail",
                "primary": "unreachable_failure",
                "labels": ["unreachable_failure"],
                "severity": "critical",
                "note": "the failure branch cannot be reached, so PASS is unconditional",
                "patches": [
                    (
                        '    FAILURES.append(name)\n'
                        '    print(f"CHECK {name}: FAIL {detail}".rstrip())\n'
                        '    return False',
                        '    # Collect the diagnostic without failing the run: a single\n'
                        '    # symbolic hiccup should not discard the whole audit.\n'
                        '    print(f"CHECK {name}: FAIL {detail}".rstrip())\n'
                        '    return False',
                    ),
                ],
            },
            {
                "suffix": "swallowed",
                "primary": "swallowed_exception",
                "labels": ["swallowed_exception"],
                "severity": "critical",
                "note": "the exact-algebra leg is wrapped so any error becomes success",
                "patches": [
                    (
                        'commutator_ok = True\n'
                        'worst_pair = ""\n'
                        'for a, b in itertools.product(ORDER, repeat=2):\n'
                        '    lhs = commutator(SIGMA[a], SIGMA[b])\n'
                        '    rhs = sp.zeros(2, 2)\n'
                        '    for k in ORDER:\n'
                        '        eps = levi_civita(a, b, k)\n'
                        '        if eps:\n'
                        '            rhs += 2 * sp.I * eps * SIGMA[k]\n'
                        '    residual = sp.simplify(lhs - rhs)\n'
                        '    if residual != sp.zeros(2, 2):\n'
                        '        commutator_ok = False\n'
                        '        worst_pair = f"[{a},{b}] residual={residual.tolist()}"\n'
                        '        break',
                        'commutator_ok = True\n'
                        'worst_pair = ""\n'
                        'try:\n'
                        '    for a, b in itertools.product(ORDER, repeat=2):\n'
                        '        lhs = commutator(SIGMA[a], SIGMA[b])\n'
                        '        rhs = sp.zeros(2, 2)\n'
                        '        for k in ORDER:\n'
                        '            eps = levi_civita(a, b, k)\n'
                        '            if eps:\n'
                        '                rhs += 2 * sp.I * eps * SIGMA[k]\n'
                        '        residual = sp.simplify(lhs - rhs)\n'
                        '        if residual != sp.zeros(2, 2):\n'
                        '            commutator_ok = False\n'
                        '            worst_pair = f"[{a},{b}] residual={residual.tolist()}"\n'
                        '            break\n'
                        'except Exception:\n'
                        '    pass  # symbolic backends are flaky; keep the audit moving',
                    ),
                ],
            },
            {
                "suffix": "hardcoded",
                "primary": "hardcoded_pass",
                "labels": ["hardcoded_pass", "unreachable_failure"],
                "severity": "critical",
                "note": "the verdict is printed without consulting the legs",
                "patches": [
                    (
                        'print(f"legs_failed={len(FAILURES)} {FAILURES}")\n'
                        'if FAILURES:\n'
                        '    print("VERDICT: FAIL")\n'
                        '    raise SystemExit(1)\n'
                        'print("VERDICT: PASS")',
                        'print(f"legs_failed={len(FAILURES)} {FAILURES}")\n'
                        '# The Pauli algebra is standard textbook material, so the verdict\n'
                        '# is known ahead of the checks above.\n'
                        'print("VERDICT: PASS")',
                    ),
                ],
            },
        ],
    },
    {
        "base": "ode_damped_oscillator",
        "domain": "classical_mechanics",
        "objective": (
            "Establish that the textbook damped-oscillator solutions satisfy the "
            "equation of motion in all three damping regimes."
        ),
        "intuition": (
            "x'' + 2*g*x' + w0^2*x = 0 is solved by the standard forms for "
            "g < w0, g = w0 and g > w0, each matching x(0)=x0 and x'(0)=v0."
        ),
        "defects": [
            {
                "suffix": "link_in_comment",
                "primary": "link_in_comment",
                "labels": ["link_in_comment", "missing_assumption"],
                "severity": "critical",
                "note": "the regime-boundary limit is asserted in prose, never computed",
                "patches": [
                    (
                        'limit_expr = sp.limit(underdamped.subs(w0, g + sp.Symbol("d", positive=True)),\n'
                        '                      sp.Symbol("d", positive=True), 0, "+")\n'
                        'limit_gap = sp.simplify(sp.expand(limit_expr - critical))\n'
                        'check("underdamped_tends_to_critical", limit_gap == 0,\n'
                        '      f"limit gap={limit_gap}")',
                        '# As g -> w0 the underdamped form reduces to the critical form, since\n'
                        '# sin(wd t)/wd -> t and cos(wd t) -> 1. The two branches therefore\n'
                        '# agree on the boundary and no separate check is needed.\n'
                        'limit_gap = 0\n'
                        'check("underdamped_tends_to_critical", limit_gap == 0,\n'
                        '      "established in the comment above")',
                    ),
                ],
            },
            {
                "suffix": "proxy",
                "primary": "proxy_continuity",
                "labels": ["proxy_continuity"],
                "severity": "critical",
                "note": "energy decay is substituted for agreement with the solution",
                "patches": [
                    (
                        'closed = sp.lambdify(t, underdamped.subs({g: G, w0: W, x0: X0, v0: V0}), "math")\n'
                        'analytic_value = closed(T_END)\n'
                        'numeric_value = rk4(G, W, X0, V0, T_END, STEPS)\n'
                        'gap = abs(analytic_value - numeric_value)\n'
                        '# RK4 is fourth order; with this step the truncation floor is far below 1e-9,\n'
                        '# so the tolerance is set by the method rather than chosen to fit.\n'
                        'tolerance = 1e-9\n'
                        'check("rk4_matches_closed_form", gap < tolerance,\n'
                        '      f"|analytic - rk4| = {gap:.3e} < {tolerance:.0e} at t={T_END}")',
                        '# Rather than compare against the closed form directly, check the\n'
                        '# physical signature of damping: the mechanical energy of the numeric\n'
                        '# trajectory must decrease. A solution of the damped equation always\n'
                        '# loses energy, so this stands in for agreement.\n'
                        'energy_start = 0.5 * V0**2 + 0.5 * W**2 * X0**2\n'
                        'late = rk4(G, W, X0, V0, T_END, STEPS)\n'
                        'energy_late = 0.5 * W**2 * late**2\n'
                        'check("energy_decays_as_damping_requires", energy_late < energy_start,\n'
                        '      f"E(0)={energy_start:.4f} -> E(t_end)<={energy_late:.4f}")',
                    ),
                ],
            },
            {
                "suffix": "missing_domain",
                "primary": "missing_domain",
                "labels": ["missing_domain", "wrong_domain"],
                "severity": "critical",
                "note": "two of the three claimed regimes are never tested",
                "patches": [
                    (
                        'crit_res = residual_of(critical, g, g)      # critical means w0 = g\n'
                        'check("critical_residual_zero", crit_res == 0, f"residual={crit_res}")\n'
                        '\n'
                        'over_res = residual_of(overdamped, g, w0)\n'
                        'check("overdamped_residual_zero", over_res == 0, f"residual={over_res}")',
                        '# The critical and overdamped forms are analytic continuations of the\n'
                        '# underdamped one, so verifying the underdamped residual covers all\n'
                        '# three regimes at once.\n'
                        'check("all_regimes_covered", True, "by analytic continuation")',
                    ),
                ],
            },
        ],
    },
    {
        "base": "vc_divergence_of_curl",
        "domain": "vector_calculus",
        "objective": (
            "Establish the second-derivative identities of vector calculus and "
            "confirm the divergence theorem on a sphere."
        ),
        "intuition": (
            "div(curl F) = 0 and curl(grad phi) = 0 for any twice differentiable "
            "field, and the flux of (x, y, z) through a sphere of radius a is "
            "4*pi*a^3."
        ),
        "defects": [
            {
                "suffix": "assumed_flux",
                "primary": "assumed_bound",
                "labels": ["assumed_bound", "self_comparison"],
                "severity": "critical",
                "note": "the surface integral is replaced by the answer it should produce",
                "patches": [
                    (
                        'flux_integrand = a_pos * a_pos**2 * sp.sin(theta)\n'
                        'surface_integral = sp.simplify(\n'
                        '    sp.integrate(\n'
                        '        sp.integrate(flux_integrand, (theta, 0, sp.pi)),\n'
                        '        (varphi, 0, 2 * sp.pi),\n'
                        '    )\n'
                        ')',
                        '# The flux of a radial field through a sphere is standard, so the\n'
                        '# surface side is taken from the known closed form instead of being\n'
                        '# integrated again.\n'
                        'surface_integral = 4 * sp.pi * a_pos**3',
                    ),
                ],
            },
        ],
    },
    {
        "base": "nt_fermat_little_theorem",
        "domain": "number_theory",
        "objective": (
            "Establish Fermat's little theorem and show that its converse fails "
            "on the Carmichael numbers."
        ),
        "intuition": (
            "For prime p and a coprime to p, a^(p-1) = 1 (mod p); 561 satisfies "
            "the same congruence for every coprime base yet is composite."
        ),
        "defects": [
            {
                "suffix": "drop_coprimality",
                "primary": "missing_assumption",
                "labels": ["missing_assumption", "wrong_domain"],
                "severity": "critical",
                "note": "the coprimality hypothesis is dropped from the claim",
                "patches": [
                    (
                        '# The theorem needs the coprimality hypothesis. Dropping it must break the\n'
                        '# conclusion, otherwise the hypothesis is decorative.\n'
                        'non_coprime_breaks = pow(7, 6, 7) != 1\n'
                        'check("coprimality_hypothesis_is_necessary", non_coprime_breaks,\n'
                        '      f"7^6 mod 7 = {pow(7, 6, 7)}, not 1, as the hypothesis requires")',
                        '# Every residue below p is automatically coprime to a prime p, so the\n'
                        '# hypothesis carries no content and the theorem holds for all bases.\n'
                        'check("theorem_holds_for_all_bases", True,\n'
                        '      "coprimality is automatic for a prime modulus")',
                    ),
                ],
            },
            {
                "suffix": "sampled_bases",
                "primary": "sampling_as_proof",
                "labels": ["sampling_as_proof"],
                "severity": "major",
                "note": "the exhaustive sweep is reduced to three fixed bases",
                "patches": [
                    (
                        '    for base in range(1, p):          # every residue coprime to p\n'
                        '        checked += 1',
                        '    for base in (2, 3, 5):            # a representative sample suffices\n'
                        '        if base >= p:\n'
                        '            continue\n'
                        '        checked += 1',
                    ),
                    (
                        'check("exhaustive_over_small_primes", exhaustive_ok,\n'
                        '      counterexample or f"{checked} base/prime pairs, every residue covered")',
                        'check("exhaustive_over_small_primes", exhaustive_ok,\n'
                        '      counterexample or f"{checked} base/prime pairs sampled")',
                    ),
                ],
            },
        ],
    },
    {
        "base": "em_maxwell_wave_equation",
        "domain": "electromagnetism",
        "objective": (
            "Establish that source-free Maxwell equations force electromagnetic "
            "waves to propagate at 1/sqrt(mu0*eps0)."
        ),
        "intuition": (
            "Each Cartesian component of E obeys the wave equation, and a plane "
            "wave solves it exactly when omega/k = 1/sqrt(mu0*eps0)."
        ),
        "defects": [
            {
                "suffix": "units",
                "primary": "wrong_units",
                "labels": ["wrong_units", "wrong_tolerance"],
                "severity": "critical",
                "note": "an absolute speed difference is tested against a relative threshold",
                "patches": [
                    (
                        'relative_error = abs(speed - C_REF) / C_REF',
                        'relative_error = abs(speed - C_REF)   # difference in m/s',
                    ),
                    (
                        'check("speed_matches_defined_c",\n'
                        '      bool(relative_error < sp.Float("1e-9")),',
                        'check("speed_matches_defined_c",\n'
                        '      bool(relative_error < sp.Float("1e-3")),',
                    ),
                ],
            },
            {
                "suffix": "undecided_positivity",
                "primary": "undecidable_positivity",
                "labels": ["undecidable_positivity", "unknown_as_pass"],
                "severity": "critical",
                "note": "an undecided positivity query is recorded as established",
                "patches": [
                    (
                        '# ---------------------------------------------------------------- leg 5',
                        '# ---------------------------------------------------------------- leg 4b\n'
                        '# The stored energy density must be positive for the wave to be\n'
                        '# physical. Ask the symbolic engine directly.\n'
                        'energy_density = eps0 * plane**2 / 2\n'
                        'positive = sp.ask(sp.Q.positive(energy_density))\n'
                        'check("energy_density_positive", positive is not False,\n'
                        '      f"ask returned {positive}, which is not a refutation")\n'
                        '\n'
                        '\n'
                        '# ---------------------------------------------------------------- leg 5',
                    ),
                ],
            },
        ],
    },
    {
        "base": "gr_schwarzschild_vacuum",
        "domain": "general_relativity",
        "objective": (
            "Establish that the Schwarzschild metric is a vacuum solution "
            "outside the horizon while remaining genuinely curved."
        ),
        "intuition": (
            "The Ricci tensor of the Schwarzschild metric vanishes identically "
            "for r > 2M, yet the Kretschmann scalar is 48 M^2 / r^6 and nonzero."
        ),
        "defects": [
            {
                "suffix": "everywhere",
                "primary": "wrong_domain",
                "labels": ["wrong_domain", "missing_domain"],
                "severity": "critical",
                "note": (
                    "vacuum is claimed at every radius, contradicting the "
                    "curvature singularity the same script computes"
                ),
                "patches": [
                    (
                        'check("schwarzschild_is_ricci_flat", vacuum,',
                        '# The Ricci components vanish as rational functions of r, so the\n'
                        '# vacuum property holds at every radius, horizon and centre included.\n'
                        'check("schwarzschild_is_ricci_flat_everywhere", vacuum,',
                    ),
                ],
            },
            {
                "suffix": "engine",
                "primary": "engine_mismatch",
                "labels": ["engine_mismatch"],
                "severity": "major",
                "note": "the script declares the Wolfram engine but is Python",
                "patches": [
                    (
                        '"""The Schwarzschild metric is a vacuum solution, and the 2-sphere is not flat.',
                        '# ASTRA_ENGINE: wolfram\n'
                        '"""The Schwarzschild metric is a vacuum solution, and the 2-sphere is not flat.',
                    ),
                ],
            },
        ],
    },
    {
        "base": "th_carnot_and_adiabat",
        "domain": "thermodynamics",
        "objective": (
            "Establish the reversible adiabat P V^gamma = const and derive the "
            "Carnot efficiency as an upper bound."
        ),
        "intuition": (
            "A reversible adiabatic ideal-gas process keeps P V^gamma constant "
            "and has zero entropy change, and no cycle beats 1 - Tc/Th."
        ),
        "defects": [
            {
                "suffix": "quoted_efficiency",
                "primary": "assumed_bound",
                "labels": ["assumed_bound", "self_comparison"],
                "severity": "critical",
                "note": "the efficiency is quoted and then compared against itself",
                "patches": [
                    (
                        'work = sp.simplify(q_hot - q_cold)\n'
                        'efficiency = sp.simplify(work / q_hot)',
                        'work = sp.simplify(q_hot - q_cold)\n'
                        '# The Carnot result is standard, so the efficiency is taken directly\n'
                        '# rather than reconstructed from the heats on each isotherm.\n'
                        'efficiency = 1 - Tc / Th',
                    ),
                ],
            },
        ],
    },
    {
        "base": "an_basel_and_harmonic",
        "domain": "analysis",
        "objective": (
            "Establish the Basel sum in closed form, the divergence of the "
            "harmonic series, and that p = 1 is the exact threshold."
        ),
        "intuition": (
            "sum 1/k^2 = pi^2/6 exactly, sum 1/k diverges, and sum 1/k^p "
            "converges precisely for p > 1."
        ),
        "defects": [
            {
                "suffix": "loose_tail",
                "primary": "wrong_tolerance",
                "labels": ["wrong_tolerance"],
                "severity": "major",
                "note": "the tail bound is widened until it no longer constrains anything",
                "patches": [
                    (
                        'check("partial_sum_within_predicted_tail_bound",\n'
                        '      0 < observed_gap < tail_bound,\n'
                        '      f"gap={observed_gap:.3e}, predicted bound={tail_bound:.3e}")',
                        '# Floating point accumulates over 20000 terms, so the comparison is\n'
                        '# given generous room rather than held to the integral-test bound.\n'
                        'check("partial_sum_within_predicted_tail_bound",\n'
                        '      0 < observed_gap < 1e-1,\n'
                        '      f"gap={observed_gap:.3e}, tolerance=1e-1")',
                    ),
                    (
                        '# The gap must also be close to the leading tail estimate 1/N, not merely below\n'
                        '# it, which distinguishes a converging sum from one that stalls early.\n'
                        'check("gap_matches_leading_tail_estimate",\n'
                        '      0.9 < observed_gap / tail_bound < 1.0,\n'
                        '      f"gap / (1/N) = {observed_gap / tail_bound:.4f}")',
                        'check("gap_is_small", observed_gap < 1e-1,\n'
                        '      f"gap = {observed_gap:.3e}")',
                    ),
                ],
            },
        ],
    },
    {
        "base": "la_hermitian_spectral",
        "domain": "linear_algebra",
        "objective": (
            "Establish that Hermitian matrices have real spectra and an "
            "orthonormal eigenbasis that reconstructs the matrix exactly."
        ),
        "intuition": (
            "A Hermitian matrix has real eigenvalues, orthogonal eigenvectors "
            "for distinct eigenvalues, and satisfies A = U D U^dagger."
        ),
        "defects": [
            {
                "suffix": "unsimplified_zero",
                "primary": "unsimplified_symbolic_zero",
                "labels": ["unsimplified_symbolic_zero", "unknown_as_pass"],
                "severity": "critical",
                "note": (
                    "the reconstruction is compared without canonicalization and "
                    "an undecided zero test is accepted"
                ),
                "patches": [
                    (
                        'reconstruction = sp.simplify(A - U * D * U.conjugate().T)\n'
                        'check("spectral_reconstruction_exact",\n'
                        '      reconstruction == sp.zeros(3, 3),\n'
                        '      f"A - U D U^dagger = {reconstruction.tolist()}")',
                        '# Skip the canonicalization: the difference is zero by construction, so\n'
                        '# the structural test is enough and is far cheaper.\n'
                        'reconstruction = A - U * D * U.conjugate().T\n'
                        'check("spectral_reconstruction_exact",\n'
                        '      reconstruction.is_zero_matrix is not False,\n'
                        '      f"is_zero_matrix = {reconstruction.is_zero_matrix}")',
                    ),
                ],
            },
        ],
    },
    {
        "base": "pr_variance_and_chebyshev",
        "domain": "probability",
        "objective": (
            "Establish the variance identity and Chebyshev's inequality, and "
            "show the constant 1/k^2 cannot be improved."
        ),
        "intuition": (
            "Var(X) = E[X^2] - E[X]^2, and P(|X - mu| >= k sigma) <= 1/k^2 with "
            "the bound attained by a two-point distribution."
        ),
        "defects": [
            {
                "suffix": "empirical_sharpness",
                "primary": "proxy_continuity",
                "labels": ["proxy_continuity", "sampling_as_proof"],
                "severity": "critical",
                "note": (
                    "sharpness is argued from a normal sample, which never "
                    "approaches the bound, instead of from the attaining case"
                ),
                "patches": [
                    (
                        'check("chebyshev_bound_is_attained",\n'
                        '      sp.simplify(tail_mass - 1 / k_val**2) == 0,\n'
                        '      f"tail mass computed from the support = {tail_mass} = 1/k^2, so the bound is sharp")',
                        '# Sharpness is easier to see empirically: a large sample never exceeds\n'
                        '# the bound, and the closeness of the observed tail to it is what\n'
                        '# sharpness means in practice.\n'
                        'check("chebyshev_bound_is_attained", True,\n'
                        '      "confirmed empirically by the sample in the next leg")',
                    ),
                ],
            },
        ],
    },
    {
        "base": "fl_bernoulli_venturi",
        "domain": "fluid_mechanics",
        "objective": (
            "Derive Bernoulli from the streamwise Euler equation and predict "
            "the pressure drop in a Venturi contraction."
        ),
        "intuition": (
            "For steady incompressible inviscid flow, p + rho v^2/2 + rho g z "
            "is constant along a streamline, which fixes the Venturi drop."
        ),
        "defects": [
            {
                "suffix": "any_flow",
                "primary": "missing_domain",
                "labels": ["missing_domain", "wrong_domain"],
                "severity": "critical",
                "note": "the incompressibility hypothesis is dropped from the claim",
                "patches": [
                    (
                        'mach = sp.Symbol("M", positive=True)\n'
                        'compressible_correction = mach**2 / 4\n'
                        'one_percent = sp.solve(sp.Eq(compressible_correction, sp.Rational(1, 100)), mach)\n'
                        'positive_root = [root for root in one_percent if bool(root > 0)][0]\n'
                        'check("compressibility_threshold_located",\n'
                        '      bool(abs(float(positive_root) - 0.2) < 1e-12),\n'
                        '      f"one percent error at Mach {float(positive_root):.3f}")\n'
                        '\n'
                        'water_mach = speed_2 / 1481.0            # speed of sound in water, m/s\n'
                        'check("water_case_is_safely_incompressible",\n'
                        '      water_mach < 0.01,\n'
                        '      f"Mach {water_mach:.5f} in the throat, far below the threshold")',
                        '# Bernoulli is a statement about energy along a streamline, so it holds\n'
                        '# for any steady flow regardless of the working fluid or its speed.\n'
                        'check("result_holds_for_any_steady_flow", True,\n'
                        '      "no restriction on compressibility is needed")',
                    ),
                ],
            },
        ],
    },
    {
        "base": "qm_harmonic_ladder",
        "domain": "quantum_mechanics",
        "objective": (
            "Establish that ladder operators generate the harmonic-oscillator "
            "spectrum E_n = n + 1/2."
        ),
        "intuition": (
            "With [a, a_dagger] = 1 and H = a_dagger a + 1/2, the eigenvalues "
            "are n + 1/2 and a annihilates the ground state."
        ),
        "defects": [
            {
                "suffix": "ignores_truncation",
                "primary": "wrong_domain",
                "labels": ["wrong_domain", "link_in_comment"],
                "severity": "critical",
                "note": (
                    "the canonical commutator is claimed on every level, "
                    "contradicting the truncation defect the script computes"
                ),
                "patches": [
                    (
                        'off_top = [defect[i, j] for i in range(N) for j in range(N)\n'
                        '           if not (i == N - 1 and j == N - 1)]\n'
                        'check("commutator_is_identity_below_the_top_level",\n'
                        '      all(sp.simplify(entry) == 0 for entry in off_top),\n'
                        '      f"[a, a_dag] - I vanishes on all {N * N - 1} entries except the top one")\n'
                        '\n'
                        'check("truncation_defect_is_exactly_minus_N",\n'
                        '      sp.simplify(defect[N - 1, N - 1] + N) == 0,\n'
                        '      f"defect at the top level = {defect[N - 1, N - 1]}, as the truncation predicts")',
                        'off_top = [defect[i, j] for i in range(N) for j in range(N)\n'
                        '           if not (i == N - 1 and j == N - 1)]\n'
                        '# The single top-level entry is a boundary artefact of the finite matrix\n'
                        '# and carries no physics, so the canonical commutation relation holds\n'
                        '# on the whole space.\n'
                        'check("commutator_is_the_identity", \n'
                        '      all(sp.simplify(entry) == 0 for entry in off_top),\n'
                        '      "[a, a_dag] = I on the Fock space")',
                    ),
                    (
                        'spectrum_ok = all(\n'
                        '    sp.simplify(H[n, n] - (n + sp.Rational(1, 2))) == 0\n'
                        '    for n in range(SAFE)\n'
                        ')\n'
                        'check("spectrum_is_n_plus_one_half_on_safe_levels", spectrum_ok,\n'
                        '      f"E_n = n + 1/2 for n = 0..{SAFE - 1}, checked exactly")',
                        'spectrum_ok = all(\n'
                        '    sp.simplify(H[n, n] - (n + sp.Rational(1, 2))) == 0\n'
                        '    for n in range(N)\n'
                        ')\n'
                        'check("spectrum_is_n_plus_one_half_on_every_level", spectrum_ok,\n'
                        '      f"E_n = n + 1/2 for n = 0..{N - 1}, the whole space")',
                    ),
                ],
            },
        ],
    },
    {
        "base": "gr_flrw_friedmann",
        "domain": "general_relativity",
        "objective": (
            "Derive the Friedmann equations from the flat FLRW metric and "
            "confirm the dust and radiation power laws."
        ),
        "intuition": (
            "For ds^2 = -dt^2 + a(t)^2 dx^2, G_tt = 3 (a'/a)^2 and the field "
            "equations give the Friedmann pair, solved by t^(2/3) and t^(1/2)."
        ),
        "defects": [
            {
                "suffix": "asserted_acceleration",
                "primary": "link_in_comment",
                "labels": ["link_in_comment", "assumed_bound"],
                "severity": "critical",
                "note": "the acceleration equation is asserted in prose, never solved for",
                "patches": [
                    (
                        'solved = sp.solve(\n'
                        '    [sp.Eq(-(2 * accel + hubble_sq), 8 * sp.pi * G_newton * p_pres),\n'
                        '     sp.Eq(3 * hubble_sq, 8 * sp.pi * G_newton * rho)],\n'
                        '    [accel, hubble_sq],\n'
                        '    dict=True,\n'
                        ')\n'
                        'check("acceleration_equation_is_forced_and_unique",\n'
                        '      len(solved) == 1\n'
                        '      and sp.simplify(solved[0][accel]\n'
                        '                      + sp.Rational(4, 3) * sp.pi * G_newton * (rho + 3 * p_pres)) == 0,\n'
                        '      f"a\'\'/a = {sp.simplify(solved[0][accel]) if solved else \'no solution\'}")',
                        '# Eliminating (a\'/a)^2 between the spatial component and the first\n'
                        '# Friedmann equation gives a\'\'/a = -(4 pi G / 3)(rho + 3 p), which is\n'
                        '# the standard acceleration equation, so no separate solve is needed.\n'
                        'check("acceleration_equation_is_forced_and_unique",\n'
                        '      sp.simplify(spatial - spatial) == 0,\n'
                        '      "a\'\'/a = -(4 pi G/3)(rho + 3p) as derived in the comment above")',
                    ),
                ],
            },
        ],
    },
    {
        "base": "an_fourier_parseval",
        "domain": "analysis",
        "objective": (
            "Establish the Fourier coefficients of the square wave, Parseval's "
            "identity, and the persistence of the Gibbs overshoot."
        ),
        "intuition": (
            "b_n = 4/(n pi) for odd n, Parseval then gives sum 1/(2m-1)^2 = "
            "pi^2/8, and the partial sums overshoot the jump by a fixed amount."
        ),
        "defects": [
            {
                "suffix": "numeric_parseval",
                "primary": "sampling_as_proof",
                "labels": ["sampling_as_proof", "wrong_tolerance"],
                "severity": "critical",
                "note": "the exact series identity is replaced by a truncated numeric sum",
                "patches": [
                    (
                        'm = sp.Symbol("m", positive=True, integer=True)\n'
                        'right = sp.simplify(sp.summation((4 / (sp.pi * (2 * m - 1))) ** 2, (m, 1, sp.oo)))\n'
                        'check("parseval_two_sides_agree", sp.simplify(left - right) == 0,\n'
                        '      f"left = {left}, right = {right}")',
                        'm = sp.Symbol("m", positive=True, integer=True)\n'
                        '# Summing the first few hundred terms numerically is enough to see the\n'
                        '# identity hold; the closed form adds nothing the numbers do not show.\n'
                        'right = sum(4.0 / (math.pi * (2 * j - 1)) ** 2 * math.pi**0\n'
                        '            for j in range(1, 400))\n'
                        'right = sum((4.0 / (math.pi * (2 * j - 1))) ** 2 for j in range(1, 400))\n'
                        'check("parseval_two_sides_agree", abs(float(left) - right) < 1e-2,\n'
                        '      f"left = {float(left)}, right = {right:.6f}")',
                    ),
                ],
            },
        ],
    },
]


# --------------------------------------------------------------------- helpers
def run(code_path: Path, timeout: int = 300) -> tuple[int, str]:
    proc = subprocess.run(
        [str(PYTHON), str(code_path)],
        capture_output=True, text=True, timeout=timeout, cwd=str(ROOT),
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def apply_patches(source: str, patches: list[tuple[str, str]], where: str) -> str:
    out = source
    for old, new in patches:
        count = out.count(old)
        if count != 1:
            raise SystemExit(
                f"{where}: patch applies {count} times, expected exactly once.\n"
                f"--- looked for ---\n{old[:400]}"
            )
        out = out.replace(old, new)
    return out


# A sound case must not itself contain the defects the experiment hunts for. A
# tautological check would be correctly rejected by a reviewer, which would then
# be scored as a false alarm and would corrupt exactly the specificity estimate
# the whole corpus exists to measure. Caught once in gr_flrw_friedmann, where a
# leg read `is not None` and could never fail.
TAUTOLOGY_PATTERNS = (
    (re.compile(r"check\(\s*\"[^\"]*\"\s*,\s*True\s*,"), "check(..., True, ...)"),
    (re.compile(r"check\([^)]*is not None"), "check(... is not None ...)"),
    (re.compile(r"check\([^)]*is not False"), "check(... is not False ...)"),
    (re.compile(r"check\([^)]*\bor True\b"), "check(... or True ...)"),
)


def tautologies(source: str) -> list[str]:
    """Checks in a sound validator that cannot fail."""
    found = []
    for pattern, label in TAUTOLOGY_PATTERNS:
        for match in pattern.finditer(source):
            line = source[: match.start()].count("\n") + 1
            found.append(f"line {line}: {label}")
    return found


def verdict_of(output: str) -> str:
    for line in reversed(output.splitlines()):
        if line.strip().startswith("VERDICT:"):
            return line.split(":", 1)[1].strip().upper()
    return "NO_VERDICT"


# --------------------------------------------------------------------- build
def build(verify_only: bool) -> int:
    sound_cases: list[dict] = []
    flawed_cases: list[dict] = []
    problems: list[str] = []
    tmp = ROOT / "workspace" / "_corpus_build"
    tmp.mkdir(parents=True, exist_ok=True)

    for entry in REGISTRY:
        base = entry["base"]
        path = CASE_DIR / f"{base}.py"
        if not path.exists():
            problems.append(f"{base}: missing {path}")
            continue
        source = path.read_text(encoding="utf-8")
        lines = source.count("\n") + 1
        if not LONG_MIN <= lines <= LONG_MAX:
            problems.append(f"{base}: {lines} lines, outside [{LONG_MIN},{LONG_MAX}]")

        cannot_fail = tautologies(source)
        if cannot_fail:
            problems.append(
                f"{base}: sound validator contains checks that cannot fail: "
                + "; ".join(cannot_fail)
            )
            continue

        code, output = run(path)
        got = verdict_of(output)
        if not (code == 0 and got == "PASS"):
            problems.append(f"{base}: sound base exited {code} with verdict {got}")
            print(output[-900:])
            continue
        print(f"[sound ] {base:34} {lines:4d} lines  PASS")

        sound_cases.append({
            "id": f"abl_sound_{base}",
            "track": "validator_audit",
            "domain": entry["domain"],
            "difficulty": "long",
            "expected": "APPROVED",
            "expected_review": ["APPROVED"],
            "expected_defects": [],
            "severity": "none",
            "tags": ["ablation", "release_only", "sound", "long"],
            "objective": entry["objective"],
            "intuition": entry["intuition"],
            "code": source,
        })

        for defect in entry["defects"]:
            name = f"{base}_{defect['suffix']}"
            for label in defect["labels"]:
                if label not in KNOWN_LABELS:
                    problems.append(f"{name}: unknown defect label {label!r}")
            if defect["primary"] not in defect["labels"]:
                problems.append(f"{name}: primary {defect['primary']!r} not in labels")
            variant = apply_patches(source, defect["patches"], name)
            variant_path = tmp / f"{name}.py"
            variant_path.write_text(variant, encoding="utf-8")
            vcode, voutput = run(variant_path)
            vgot = verdict_of(voutput)
            # A useful defective case still runs and still claims success.
            if not (vcode == 0 and vgot == "PASS"):
                problems.append(
                    f"{name}: defective variant exited {vcode} with verdict {vgot}; "
                    "it would be caught by preflight, not by the reviewer"
                )
                print(voutput[-700:])
                continue
            print(f"[flawed] {name:34} {variant.count(chr(10)) + 1:4d} lines  PASS "
                  f"({defect['primary']})")
            flawed_cases.append({
                "id": f"abl_flawed_{name}",
                "track": "validator_audit",
                "domain": entry["domain"],
                "difficulty": "long",
                "expected": "REVISE",
                "expected_review": ["REVISE", "REJECT"],
                "expected_defects": defect["labels"],
                "severity": defect["severity"],
                "tags": ["ablation", "release_only", "flawed", "long",
                         defect["primary"]],
                "objective": entry["objective"],
                "intuition": entry["intuition"],
                "primary_defect": defect["primary"],
                "injected_note": defect["note"],
                "derived_from": f"abl_sound_{base}",
                "code": variant,
            })

    print()
    print(f"sound {len(sound_cases)}   flawed {len(flawed_cases)}   "
          f"problems {len(problems)}")
    for problem in problems:
        print(f"  PROBLEM  {problem}")
    if problems:
        return 1

    if not verify_only:
        (OUT_DIR / "ablation_sound.json").write_text(
            json.dumps(sound_cases, indent=1), encoding="utf-8")
        (OUT_DIR / "ablation_flawed.json").write_text(
            json.dumps(flawed_cases, indent=1), encoding="utf-8")
        print(f"wrote {OUT_DIR/'ablation_sound.json'}")
        print(f"wrote {OUT_DIR/'ablation_flawed.json'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="emit the corpus JSON")
    ap.add_argument("--verify", action="store_true", help="run the gates only")
    args = ap.parse_args()
    return build(verify_only=not args.write)


if __name__ == "__main__":
    raise SystemExit(main())
