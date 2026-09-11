#!/usr/bin/env python3
"""Build and verify the review-independence ablation corpus.

Validators live as real, executable Python files under
``benchmarks/quality/validator_audit/cases/``. Defective variants are derived
from a sound base by localized patches, so the injected defect is explicit and
auditable instead of being spread through a hand-written copy, and the sound
and defective members of a pair are matched on domain and difficulty.

Every case passes five gates before it is written:

* the sound base executes and prints the verdict it declares;
* each defective variant also executes and still prints ``VERDICT: PASS``,
  which is what makes it dangerous rather than merely broken;
* each patch applies exactly once, so a defect cannot silently fail to land;
* no sound validator contains a check that cannot fail;
* no sound validator computes a value it never reads.

The last two exist because a sound case carrying a defect is worse than useless:
a reviewer would reject it correctly, the rejection would be scored as a false
alarm, and it would corrupt the specificity estimate the corpus is built to
measure. Both gates were added after an adversarial review found six such cases
among the first fifteen, and each caught further instances immediately.

Usage:
    python scripts/build_ablation_corpus.py --verify        # gates only
    python scripts/build_ablation_corpus.py --write         # gates, then emit
"""
from __future__ import annotations

import argparse
import ast
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
    {
        "base": "qm_uncertainty_saturation",
        "domain": "quantum_mechanics",
        "objective": (
            "Establish that the harmonic-oscillator ground state saturates the "
            "position-momentum uncertainty bound and that excited states do not."
        ),
        "intuition": (
            "With hbar = 1 the n-th eigenstate has dx dp = n + 1/2, so the "
            "Robertson floor of 1/2 is attained only by the ground state."
        ),
        "defects": [
            {
                "suffix": "asserted_excited",
                "primary": "link_in_comment",
                "labels": ["link_in_comment", "assumed_bound"],
                "severity": "critical",
                "note": (
                    "the excited-state spreads are read off the energy in a "
                    "comment instead of being integrated"
                ),
                "patches": [
                    (
                        '    product = sp.simplify(\n'
                        '        sp.sqrt(sp.simplify(mx2 - mx**2)) * sp.sqrt(sp.simplify(mp2 - mp**2))\n'
                        '    )\n'
                        '    excited_products.append(product)',
                        '    # The virial theorem splits E_n = n + 1/2 evenly between the kinetic\n'
                        '    # and potential parts, so the product of the spreads is n + 1/2.\n'
                        '    # Recomputing the integrals only confirms what the energy already fixes.\n'
                        '    product = n + sp.Rational(1, 2)\n'
                        '    excited_products.append(product)',
                    ),
                ],
            },
        ],
    },
    {
        "base": "nt_bezout_and_gcd",
        "domain": "number_theory",
        "objective": (
            "Establish Bezout's identity and characterise the gcd as the least "
            "positive integer combination of the two arguments."
        ),
        "intuition": (
            "The extended Euclidean algorithm returns g, x, y with ax + by = g, "
            "g divides both, every common divisor divides g, and g is minimal."
        ),
        "defects": [
            {
                "suffix": "asserted_minimality",
                "primary": "link_in_comment",
                "labels": ["link_in_comment", "assumed_bound"],
                "severity": "critical",
                "note": "minimality is asserted in prose, the search is deleted",
                "patches": [
                    (
                        'minimal_ok = True\n'
                        'minimal_detail = ""\n'
                        'for a in range(-12, 13):\n'
                        '    for b in range(-12, 13):\n'
                        '        if a == 0 and b == 0:\n'
                        '            continue\n'
                        '        g, _x, _y = extended_euclid(a, b)\n'
                        '        smallest = None\n'
                        '        for x in range(-40, 41):\n'
                        '            for y in range(-40, 41):\n'
                        '                value = a * x + b * y\n'
                        '                if value > 0 and (smallest is None or value < smallest):\n'
                        '                    smallest = value\n'
                        '        if smallest != g:\n'
                        '            minimal_ok = False\n'
                        '            minimal_detail = f"a={a}, b={b}: least positive combination {smallest} != g={g}"\n'
                        '            break\n'
                        '    if not minimal_ok:\n'
                        '        break\n'
                        'check("gcd_is_the_least_positive_combination", minimal_ok,\n'
                        '      minimal_detail or "625 pairs, combination range exhausted for each")',
                        '# The set of integer combinations of a and b is exactly the set of\n'
                        '# multiples of their gcd, so the least positive one is the gcd itself.\n'
                        '# Searching the combinations would only reproduce that fact.\n'
                        'minimal_ok = True\n'
                        'check("gcd_is_the_least_positive_combination", minimal_ok,\n'
                        '      "the combinations are exactly the multiples of g")',
                    ),
                ],
            },
        ],
    },
    {
        "base": "sm_two_level_schottky",
        "domain": "statistical_mechanics",
        "objective": (
            "Establish the two-level partition function, its mean energy, and "
            "that the heat capacity has an interior maximum."
        ),
        "intuition": (
            "Z = 1 + exp(-beta eps) gives <E> = eps/(exp(beta eps) + 1), and the "
            "heat capacity vanishes at both temperature limits, peaking between."
        ),
        "defects": [
            {
                "suffix": "grid_peak",
                "primary": "proxy_continuity",
                "labels": ["proxy_continuity", "sampling_as_proof"],
                "severity": "critical",
                "note": (
                    "the maximum is taken as the largest value on a grid, which "
                    "cannot distinguish a peak from a sampling artefact"
                ),
                "patches": [
                    (
                        'mp.mp.dps = 40\n'
                        'stationary_fn = sp.lambdify(x, stationary, "mpmath")\n'
                        'root = mp.findroot(stationary_fn, mp.mpf("2.4"))\n'
                        'second = sp.lambdify(x, sp.diff(shape, x, 2), "mpmath")(root)\n'
                        '\n'
                        'check("stationary_point_located",\n'
                        '      abs(mp.mpf(stationary_fn(root))) < mp.mpf("1e-30"),\n'
                        '      f"dC/dx = {mp.nstr(abs(stationary_fn(root)), 4)} at x = {mp.nstr(root, 12)}")\n'
                        'check("stationary_point_is_a_maximum", bool(second < 0),\n'
                        '      f"second derivative there = {mp.nstr(second, 6)} < 0")',
                        '# A fine grid locates the peak well enough; solving the stationarity\n'
                        '# condition and checking a second derivative adds nothing the scan\n'
                        '# does not already show.\n'
                        'grid = [mp.mpf(j) / 100 for j in range(1, 601)]\n'
                        'shape_fn = sp.lambdify(x, shape, "mpmath")\n'
                        'root = max(grid, key=shape_fn)\n'
                        'check("stationary_point_located", True,\n'
                        '      f"largest grid value at x = {mp.nstr(root, 12)}")\n'
                        'check("stationary_point_is_a_maximum", True,\n'
                        '      "it is the largest value sampled")',
                    ),
                    (
                        'check("peak_is_at_the_known_schottky_value",\n'
                        '      abs(root - mp.mpf("2.399357280074")) < mp.mpf("1e-9"),\n'
                        '      f"x_peak = {mp.nstr(root, 12)}")',
                        '# The grid spacing is 0.01, so agreement to two decimals is all that\n'
                        '# can be expected and all that is required here.\n'
                        'check("peak_is_at_the_known_schottky_value",\n'
                        '      abs(root - mp.mpf("2.399357280074")) < mp.mpf("1e-2"),\n'
                        '      f"x_peak = {mp.nstr(root, 12)}")',
                    ),
                ],
            },
        ],
    },
    {
        "base": "gr_light_deflection",
        "domain": "general_relativity",
        "objective": (
            "Establish that general relativity deflects starlight by twice the "
            "Newtonian amount, and evaluate it for the Sun."
        ),
        "intuition": (
            "The Schwarzschild null geodesic gives 4 G M / (c^2 b) to first "
            "order, exactly double the Newtonian value, 1.75 arcsec at the Sun."
        ),
        "defects": [
            {
                "suffix": "quoted_solution",
                "primary": "assumed_bound",
                "labels": ["assumed_bound", "link_in_comment"],
                "severity": "critical",
                "note": (
                    "the perturbative solution is declared correct in a comment "
                    "instead of being substituted back into its equation"
                ),
                "patches": [
                    (
                        'first_order_lhs = sp.simplify(sp.diff(u1, phi, 2) + u1)\n'
                        'first_order_rhs = sp.simplify(3 * u0**2)\n'
                        'check("first_order_particular_solution_is_correct",\n'
                        '      sp.simplify(sp.expand_trig(first_order_lhs - first_order_rhs)) == 0,\n'
                        '      f"u1\'\' + u1 = {sp.simplify(first_order_lhs)} = 3 u0^2")',
                        '# u1 = (1 + cos^2 phi)/b^2 is the standard particular solution of\n'
                        '# u1\'\' + u1 = 3 u0^2, given in every textbook treatment of light\n'
                        '# bending, so substituting it back would only restate the reference.\n'
                        'check("first_order_particular_solution_is_correct", True,\n'
                        '      "standard textbook particular solution")',
                    ),
                    (
                        'u_full = u0 + eps * u1\n'
                        'residual = sp.expand(\n'
                        '    sp.diff(u_full, phi, 2) + u_full - 3 * eps * u_full**2\n'
                        ')\n'
                        'first_order_residual = sp.simplify(sp.expand_trig(residual.coeff(eps, 1)))\n'
                        'check("residual_vanishes_at_first_order", first_order_residual == 0,\n'
                        '      f"coefficient of the order parameter = {first_order_residual}")',
                        '# The combination therefore solves the full equation to first order.\n'
                        'check("residual_vanishes_at_first_order", True,\n'
                        '      "follows from the two orders above")',
                    ),
                ],
            },
        ],
    },
    {
        "base": "co_binomial_identities",
        "domain": "combinatorics",
        "objective": (
            "Establish Pascal's rule, the row sums, Vandermonde's convolution "
            "and the hockey stick identity for binomial coefficients."
        ),
        "intuition": (
            "All four identities hold, and each is checked against a Pascal "
            "triangle built by addition alone rather than by factorials."
        ),
        "defects": [
            {
                "suffix": "same_source",
                "primary": "self_comparison",
                "labels": ["self_comparison"],
                "severity": "critical",
                "note": (
                    "the triangle is filled from the library it is supposed to "
                    "corroborate, so the agreement leg compares it with itself"
                ),
                "patches": [
                    (
                        'def build_triangle(rows):\n'
                        '    """Pascal\'s triangle by addition only. No factorials, no library calls."""\n'
                        '    triangle = [[1]]\n'
                        '    for row_index in range(1, rows):\n'
                        '        previous = triangle[-1]\n'
                        '        row = [1]\n'
                        '        for position in range(1, row_index):\n'
                        '            row.append(previous[position - 1] + previous[position])\n'
                        '        row.append(1)\n'
                        '        triangle.append(row)\n'
                        '    return triangle',
                        'def build_triangle(rows):\n'
                        '    """Pascal\'s triangle, filled from the library for speed and clarity."""\n'
                        '    return [\n'
                        '        [int(sp.binomial(row_index, position))\n'
                        '         for position in range(row_index + 1)]\n'
                        '        for row_index in range(rows)\n'
                        '    ]',
                    ),
                ],
            },
        ],
    },
    {
        "base": "dy_logistic_period_doubling",
        "domain": "dynamical_systems",
        "objective": (
            "Establish the fixed points of the logistic map, their stability "
            "window, and the period doubling at r = 3."
        ),
        "intuition": (
            "The nonzero fixed point 1 - 1/r is stable exactly for 1 < r < 3, "
            "and a two-cycle is born as the multiplier passes through -1."
        ),
        "defects": [
            {
                "suffix": "cycle_everywhere",
                "primary": "missing_domain",
                "labels": ["missing_domain", "link_in_comment"],
                "severity": "critical",
                "note": (
                    "the two-cycle is claimed for every r, dropping the "
                    "discriminant condition that makes its roots real"
                ),
                "patches": [
                    (
                        'discriminant = sp.simplify(sp.discriminant(\n'
                        '    sp.Poly(x**2 - (1 + 1 / r) * x + (1 + 1 / r) / r, x)\n'
                        '))\n'
                        'birth = sp.solve(sp.Eq(discriminant, 0), r)\n'
                        'check("two_cycle_is_born_exactly_at_r_three",\n'
                        '      3 in [sp.simplify(value) for value in birth],\n'
                        '      f"discriminant {sp.factor(discriminant)} vanishes at r = {birth}")',
                        '# The quadratic always has two roots, so the two-cycle exists for every\n'
                        '# value of r and there is no threshold to locate.\n'
                        'check("two_cycle_is_born_exactly_at_r_three", True,\n'
                        '      "the quadratic always factors, so the orbit is always present")',
                    ),
                ],
            },
        ],
    },
    {
        "base": "nu_newton_quadratic_convergence",
        "domain": "numerical_analysis",
        "objective": (
            "Establish that Newton's method converges quadratically at a simple "
            "root with the asymptotic constant f''(a)/(2 f'(a))."
        ),
        "intuition": (
            "The Newton error satisfies e_(n+1) = (f''/2f') e_n^2 at a simple "
            "root, and degrades to linear with ratio 1/2 at a double root."
        ),
        "defects": [
            {
                "suffix": "slack_order",
                "primary": "wrong_tolerance",
                "labels": ["wrong_tolerance"],
                "severity": "critical",
                "note": (
                    "the order tolerance is widened until a first-order method "
                    "would also pass, so the leg stops distinguishing rates"
                ),
                "patches": [
                    (
                        'check("measured_order_is_two",\n'
                        '      abs(exponent - 2) < mp.mpf("1e-3"),',
                        '# Floating-point iteration is noisy near the root, so the order estimate\n'
                        '# is given room rather than being held to three decimals.\n'
                        'check("measured_order_is_two",\n'
                        '      abs(exponent - 2) < mp.mpf("1.5"),',
                    ),
                    (
                        'check("measured_constant_matches_the_prediction",\n'
                        '      abs(measured - predicted) < mp.mpf("1e-10"),',
                        'check("measured_constant_matches_the_prediction",\n'
                        '      abs(measured - predicted) < mp.mpf("1e-1"),',
                    ),
                ],
            },
        ],
    },
    {
        "base": "op_lagrange_multipliers",
        "domain": "optimization",
        "objective": (
            "Establish the constrained maximum of x*y on x + y = s and show the "
            "multiplier is the derivative of the optimal value."
        ),
        "intuition": (
            "The maximum is x = y = s/2 with value s^2/4, and the multiplier "
            "equals dF*/ds, which is the envelope theorem."
        ),
        "defects": [
            {
                "suffix": "one_route",
                "primary": "self_comparison",
                "labels": ["self_comparison", "link_in_comment"],
                "severity": "critical",
                "note": (
                    "the second route is replaced by the first one's answer, so "
                    "the cross-check compares a result with itself"
                ),
                "patches": [
                    (
                        'reduced = sp.simplify(objective.subs(y, s - x))\n'
                        'critical = sp.solve(sp.Eq(sp.diff(reduced, x), 0), x)',
                        '# Substitution must land on the same point the multipliers already gave,\n'
                        '# so the critical point is taken from there instead of re-solving.\n'
                        'reduced = sp.simplify(objective.subs(y, s - x))\n'
                        'critical = [solution[x]]',
                    ),
                ],
            },
        ],
    },
    {
        "base": "in_shannon_entropy_maximum",
        "domain": "information_theory",
        "objective": (
            "Establish that Shannon entropy is maximised by the uniform "
            "distribution with maximum log n."
        ),
        "intuition": (
            "H(p) = -sum p log p is bounded by log n, attained only by the "
            "uniform distribution, which follows from Gibbs' inequality."
        ),
        "defects": [
            {
                "suffix": "sampled_bound",
                "primary": "sampling_as_proof",
                "labels": ["sampling_as_proof", "assumed_bound"],
                "severity": "critical",
                "note": (
                    "the Gibbs derivation is dropped and the universal bound is "
                    "left to twenty thousand random draws"
                ),
                "patches": [
                    (
                        'gap = sp.simplify(t - 1 - sp.log(t))\n'
                        'stationary_points = sp.solve(sp.Eq(sp.diff(gap, t), 0), t)\n'
                        'check("log_bound_has_its_only_stationary_point_at_one",\n'
                        '      stationary_points == [1],\n'
                        '      f"d/dt (t - 1 - log t) vanishes at t = {stationary_points}")\n'
                        '\n'
                        'check("that_point_is_a_minimum_of_the_gap",\n'
                        '      bool(sp.diff(gap, t, 2).subs(t, 1) > 0),\n'
                        '      f"second derivative at t = 1 is {sp.diff(gap, t, 2).subs(t, 1)}, positive")\n'
                        '\n'
                        'check("the_gap_vanishes_there_and_only_there",\n'
                        '      sp.simplify(gap.subs(t, 1)) == 0,\n'
                        '      "so log t = t - 1 exactly at t = 1 and log t < t - 1 elsewhere")',
                        '# The bound log t <= t - 1 is elementary and the sampling below covers\n'
                        '# the distribution space densely, so working through its equality case\n'
                        '# adds nothing the numbers do not already show.\n'
                        'check("log_bound_has_its_only_stationary_point_at_one", True,\n'
                        '      "standard elementary inequality")\n'
                        'check("that_point_is_a_minimum_of_the_gap", True,\n'
                        '      "standard elementary inequality")\n'
                        'check("the_gap_vanishes_there_and_only_there", True,\n'
                        '      "standard elementary inequality")',
                    ),
                ],
            },
        ],
    },
    {
        "base": "ch_arrhenius_linearisation",
        "domain": "chemical_kinetics",
        "objective": (
            "Establish that Arrhenius rates are exactly linear in 1/T and that "
            "the ten-degree doubling rule holds only at one activation energy."
        ),
        "intuition": (
            "ln k against 1/T has slope -Ea/R exactly, and k(T+10)/k(T) = 2 "
            "fixes Ea rather than holding generally."
        ),
        "defects": [
            {
                "suffix": "rule_of_thumb",
                "primary": "assumed_bound",
                "labels": ["assumed_bound", "missing_domain"],
                "severity": "critical",
                "note": (
                    "the doubling rule is taken as general instead of being "
                    "solved, and the case where it fails is deleted"
                ),
                "patches": [
                    (
                        'required = sp.solve(sp.Eq(ratio, 2), Ea)\n'
                        'check("doubling_requires_one_specific_activation_energy",\n'
                        '      len(required) == 1,\n'
                        '      f"k(T+10)/k(T) = 2 forces Ea = {sp.simplify(required[0])}")',
                        '# A ten-degree rise roughly doubles reaction rates, which is standard\n'
                        '# laboratory practice, so there is nothing to solve for here.\n'
                        'required = [sp.Rational(52900)]\n'
                        'check("doubling_requires_one_specific_activation_energy", True,\n'
                        '      "the ten-degree rule is general laboratory experience")',
                    ),
                    (
                        'actual_ratio = math.exp(-EA_TRUE / (R_SI * 308)) / math.exp(-EA_TRUE / (R_SI * 298))\n'
                        'check("rule_of_thumb_fails_away_from_that_value",\n'
                        '      abs(actual_ratio - 2) > 0.5,\n'
                        '      f"at Ea = {EA_TRUE:.0f} J/mol a ten-degree rise multiplies the rate by "\n'
                        '      f"{actual_ratio:.3f}, not 2")',
                        '# The rule applies across the usual range of activation energies.\n'
                        'check("rule_of_thumb_fails_away_from_that_value", True,\n'
                        '      "the rule is taken to hold generally")',
                    ),
                ],
            },
        ],
    },
    {
        "base": "sig_nyquist_aliasing",
        "domain": "signal_processing",
        "objective": (
            "Establish the aliasing identities for a sampled cosine and the "
            "recovery of a band-limited tone by sinc interpolation."
        ),
        "intuition": (
            "Frequencies separated by the sampling rate, and reflections about "
            "it, give identical samples; below Nyquist distinct tones separate."
        ),
        "defects": [
            {
                "suffix": "fixed_tolerance",
                "primary": "wrong_tolerance",
                "labels": ["wrong_tolerance", "proxy_continuity"],
                "severity": "critical",
                "note": (
                    "the convergence demonstration is replaced by a single "
                    "tolerance loose enough to hide a failure of reconstruction"
                ),
                "patches": [
                    (
                        'small = centre_error(1024)\n'
                        'large = max(errors)\n'
                        'check("sinc_interpolation_reproduces_a_band_limited_tone",\n'
                        '      large < small and large < 1e-5,\n'
                        '      f"error falls from {small:.3e} at 1024 samples to {large:.3e} at {COUNT}, "\n'
                        '      "so the residual is window truncation and not a failure of the theorem")',
                        '# One window is enough; interpolation error is small and comparing two\n'
                        '# window sizes only costs time.\n'
                        'large = max(errors)\n'
                        'check("sinc_interpolation_reproduces_a_band_limited_tone",\n'
                        '      large < 1e-1,\n'
                        '      f"reconstruction error {large:.3e}, within tolerance")',
                    ),
                ],
            },
        ],
    },
    {
        "base": "me_euler_buckling",
        "domain": "structural_mechanics",
        "objective": (
            "Establish the Euler buckling spectrum for a pinned column and "
            "derive the clamped-clamped factor from its boundary conditions."
        ),
        "intuition": (
            "Non-trivial shapes exist only at P = n^2 pi^2 EI / L^2, and "
            "clamping both ends raises the critical load by four."
        ),
        "defects": [
            {
                "suffix": "effective_length",
                "primary": "assumed_bound",
                "labels": ["assumed_bound", "self_comparison"],
                "severity": "critical",
                "note": (
                    "the clamped factor is recovered by squaring an assumed "
                    "effective length instead of solving the boundary problem"
                ),
                "patches": [
                    (
                        'conditions = [\n'
                        '    clamped.subs(x, 0),\n'
                        '    sp.diff(clamped, x).subs(x, 0),\n'
                        '    clamped.subs(x, L),\n'
                        '    sp.diff(clamped, x).subs(x, L),\n'
                        ']\n'
                        'coefficient_matrix = sp.Matrix([\n'
                        '    [sp.expand(condition).coeff(coefficient) for coefficient in (C1, C2, C3, C4)]\n'
                        '    for condition in conditions\n'
                        '])\n'
                        'determinant = sp.simplify(sp.trigsimp(coefficient_matrix.det()))\n'
                        'check("clamped_boundary_determinant_is_the_eigenvalue_condition",\n'
                        '      sp.simplify(determinant\n'
                        '                  - kk * (L * kk * sp.sin(L * kk) + 2 * sp.cos(L * kk) - 2)) == 0,\n'
                        '      f"det = {sp.factor(determinant)}, whose zeros are the buckling loads")',
                        '# The clamped column has effective length L/2, which is standard, so the\n'
                        '# determinant does not need to be assembled: the factor follows from\n'
                        '# squaring the effective length.\n'
                        'determinant = kk * (L * kk * sp.sin(L * kk) + 2 * sp.cos(L * kk) - 2)\n'
                        'check("clamped_boundary_determinant_is_the_eigenvalue_condition", True,\n'
                        '      "effective length L/2, as tabulated")',
                    ),
                ],
            },
        ],
    },
    {
        "base": "ep_sir_threshold",
        "domain": "epidemiology",
        "objective": (
            "Establish the SIR epidemic threshold, the location of the peak, "
            "and the final-size relation."
        ),
        "intuition": (
            "Infections grow only when R0 S(0)/N exceeds one, the peak sits at "
            "S = gN/b, and the final susceptible fraction solves a "
            "transcendental equation."
        ),
        "defects": [
            {
                "suffix": "simulated_threshold",
                "primary": "proxy_continuity",
                "labels": ["proxy_continuity", "sampling_as_proof"],
                "severity": "critical",
                "note": (
                    "the threshold and the peak are read off one simulation "
                    "instead of being solved, so the conditions are never derived"
                ),
                "patches": [
                    (
                        'condition = sp.solve(sp.Eq(b * S0 / N - g, 0), S0)\n'
                        'check("growth_changes_sign_at_S_equals_gN_over_b",\n'
                        '      len(condition) == 1 and sp.simplify(condition[0] - g * N / b) == 0,\n'
                        '      f"I\'(0) = 0 at S_0 = {condition[0] if condition else \'none\'}")',
                        '# The threshold is visible in the simulations below, where one run grows\n'
                        '# and the other does not, so solving for the crossing adds nothing.\n'
                        'condition = [g * N / b]\n'
                        'check("growth_changes_sign_at_S_equals_gN_over_b", True,\n'
                        '      "confirmed by the two simulations further down")',
                    ),
                    (
                        'peak = sp.solve(sp.Eq(dI, 0), S)\n'
                        'non_trivial = [value for value in peak if sp.simplify(value) != 0]\n'
                        'check("peak_condition_solves_to_a_single_susceptible_level",\n'
                        '      len(non_trivial) == 1,\n'
                        '      f"I\' = 0 at S = {non_trivial}")',
                        '# The simulation records where the peak occurred, which is the same\n'
                        '# information the algebra would produce.\n'
                        'non_trivial = [g * N / b]\n'
                        'check("peak_condition_solves_to_a_single_susceptible_level", True,\n'
                        '      "taken from the recorded peak of the simulation")',
                    ),
                ],
            },
        ],
    },
    {
        "base": "cm_kepler_orbit",
        "domain": "classical_mechanics",
        "objective": (
            "Derive the Kepler orbit from the Lagrangian and show that closure "
            "belongs to the inverse square law rather than to the integrator."
        ),
        "intuition": (
            "The angle is cyclic, so r^2 thetadot is constant; in u = 1/r the "
            "radial equation is a linear oscillator whose period gives Kepler's "
            "third law, and a 1/r^3 term shifts the frequency and opens the orbit."
        ),
        "defects": [
            {
                "suffix": "period_from_the_formula",
                "primary": "self_comparison",
                "labels": ["self_comparison", "unreachable_failure"],
                "severity": "critical",
                "note": (
                    "the period said to be measured by integration is assigned "
                    "from the analytic prediction, so the numeric leg compares "
                    "Kepler's third law with itself"
                ),
                "patches": [
                    (
                        'measured_period, measured_angle = integrate(0.0, ONE_TURN_STEPS)',
                        '# The conic is exact, so the period it predicts is cleaner than the\n'
                        '# integrated one; the integration is kept for the periapsis angle.\n'
                        'measured_period = predicted_period\n'
                        '_integrated_period, measured_angle = integrate(0.0, ONE_TURN_STEPS)',
                    ),
                ],
            },
            {
                "suffix": "retyped_radial_equation",
                "primary": "link_in_comment",
                "labels": ["link_in_comment", "missing_assumption"],
                "severity": "major",
                "note": (
                    "the orbit equation is transformed from a retyped copy of the "
                    "radial equation instead of from the one the Lagrangian "
                    "produced, so the whole first leg is decorative and a wrong "
                    "potential upstream would never reach any later check"
                ),
                "patches": [
                    (
                        '# The equation transformed here is the one leg 1 DERIVED, not a retyped\n'
                        '# copy of it. Substituting the three atoms is what carries the Lagrangian\n'
                        '# into this leg, so a wrong potential upstream shows up as a wrong orbit\n'
                        '# equation here instead of being quietly re-entered correctly.\n'
                        'radial_law = sp.simplify(radial_el)\n'
                        'residual = sp.simplify(radial_law.subs([\n'
                        '    (sp.Derivative(r_t, t, 2), radial_acceleration),\n'
                        '    (sp.Derivative(theta_t, t), angular_speed),\n'
                        '    (r_t, radius),\n'
                        ']))',
                        '# The radial equation derived in leg 1, written out in u.\n'
                        'residual = sp.simplify(\n'
                        '    radial_acceleration - radius * angular_speed ** 2 + GM / radius ** 2\n'
                        ')',
                    ),
                ],
            },
        ],
    },
    {
        "base": "st_cramer_rao_bound",
        "domain": "statistics",
        "objective": (
            "Show that the sample mean attains the Cramer-Rao bound and that a "
            "biased estimator can sit below it without contradicting the theorem."
        ),
        "intuition": (
            "The score equation solves to the sample mean, the information is "
            "n/sigma^2 by both definitions, and the bound constrains unbiased "
            "estimators only, which is the hypothesis usually left unsaid."
        ),
        "defects": [
            {
                "suffix": "unbiasedness_assumed",
                "primary": "missing_assumption",
                "labels": ["missing_assumption", "missing_domain"],
                "severity": "critical",
                "note": (
                    "unbiasedness is declared to hold for any average of the "
                    "observations, which is false and is exactly what the last "
                    "leg contradicts, and the check that would have caught it is "
                    "replaced by a constant"
                ),
                "patches": [
                    (
                        'estimator_pair = (draws[0] + draws[1]) / 2\n'
                        'check("the_two_observation_average_is_also_unbiased",\n'
                        '      sp.simplify(expectation(estimator_pair) - mu) == 0,\n'
                        '      f"E[mu_pair] = {sp.simplify(expectation(estimator_pair))}")',
                        '# Any average of the observations is unbiased, so the bound applies to\n'
                        '# all of them and the expectation need not be recomputed each time.\n'
                        'estimator_pair = (draws[0] + draws[1]) / 2\n'
                        'check("the_two_observation_average_is_also_unbiased", True,\n'
                        '      "an average of observations is unbiased by construction")',
                    ),
                ],
            },
            {
                "suffix": "targets_from_the_simulation",
                "primary": "self_comparison",
                "labels": ["self_comparison", "unreachable_failure"],
                "severity": "critical",
                "note": (
                    "the exact variances the simulation is compared against are "
                    "read off that same simulation, so both agreement checks "
                    "compare a number with itself and the symbolic results are "
                    "never tested against anything"
                ),
                "patches": [
                    (
                        'exact_mean_variance = as_float(variance_mean.subs({sigma: SIGMA_TRUE}))\n'
                        'exact_pair_variance = as_float(variance_pair.subs({sigma: SIGMA_TRUE}))',
                        '# Taking the targets from the simulation itself avoids any mismatch of\n'
                        '# parameterisation between the symbolic variance and the simulated one.\n'
                        '_, exact_mean_variance = moments(means)\n'
                        '_, exact_pair_variance = moments(pairs)',
                    ),
                ],
            },
        ],
    },
    {
        "base": "ot_fresnel_brewster",
        "domain": "optics",
        "objective": (
            "Derive the Fresnel coefficients from the boundary conditions and "
            "show that energy balances only with the obliquity factor."
        ),
        "intuition": (
            "Continuity of the tangential fields fixes the amplitudes, the "
            "p-amplitude vanishes at tan(theta) = n2/n1, and the transmitted "
            "power carries n2 cos(theta_t) / (n1 cos(theta_i))."
        ),
        "defects": [
            {
                "suffix": "cosines_dropped",
                "primary": "wrong_units",
                "labels": ["wrong_units", "sampling_as_proof"],
                "severity": "critical",
                "note": (
                    "the obliquity factor keeps the index ratio but loses the "
                    "cosines, which is exactly right at normal incidence and "
                    "wrong everywhere else, and the energy checks are evaluated "
                    "only at normal incidence where the error cannot show"
                ),
                "patches": [
                    (
                        'obliquity = n2 * cos_t / (n1 * cos_i)\n'
                        'energy_s = sp.simplify(r_s ** 2 + obliquity * t_s ** 2)\n'
                        'check("the_s_polarisation_conserves_energy_with_the_obliquity_factor",\n'
                        '      sp.simplify(energy_s - 1) == 0,\n'
                        '      f"R_s + T_s = {energy_s}")\n'
                        '\n'
                        'energy_p = sp.simplify(r_p ** 2 + obliquity * t_p ** 2)\n'
                        'check("the_p_polarisation_conserves_energy_with_the_obliquity_factor",\n'
                        '      sp.simplify(energy_p - 1) == 0,\n'
                        '      f"R_p + T_p = {energy_p}")',
                        '# The cosines cancel between the incident and transmitted sides, leaving\n'
                        '# only the index ratio, and the balance is confirmed numerically.\n'
                        'obliquity = n2 / n1\n'
                        'NORMAL = {n1: 1, n2: sp.Rational(3, 2), cos_i: 1, cos_t: 1}\n'
                        'energy_s = sp.simplify(r_s ** 2 + obliquity * t_s ** 2)\n'
                        'check("the_s_polarisation_conserves_energy_with_the_obliquity_factor",\n'
                        '      abs(float(energy_s.subs(NORMAL)) - 1) < 1e-12,\n'
                        '      f"R_s + T_s = {float(energy_s.subs(NORMAL)):.12f}")\n'
                        '\n'
                        'energy_p = sp.simplify(r_p ** 2 + obliquity * t_p ** 2)\n'
                        'check("the_p_polarisation_conserves_energy_with_the_obliquity_factor",\n'
                        '      abs(float(energy_p.subs(NORMAL)) - 1) < 1e-12,\n'
                        '      f"R_p + T_p = {float(energy_p.subs(NORMAL)):.12f}")',
                    ),
                ],
            },
            {
                "suffix": "brewster_quoted",
                "primary": "self_comparison",
                "labels": ["self_comparison", "hardcoded_pass"],
                "severity": "critical",
                "note": (
                    "the Brewster root is written in by hand instead of solved "
                    "from the amplitude, so the numerator is computed and never "
                    "used and both checks compare the quoted formula with itself"
                ),
                "patches": [
                    (
                        'roots = sp.solve(sp.Eq(p_numerator, 0), tangent)',
                        '# The Brewster condition is standard and the numerator above reproduces\n'
                        '# it, so the root is taken directly rather than solved for again.\n'
                        'roots = [n2 / n1]',
                    ),
                ],
            },
        ],
    },
    {
        "base": "ct_lyapunov_stability",
        "domain": "control_theory",
        "objective": (
            "Tie linear stability, the Routh-Hurwitz conditions and the Lyapunov "
            "equation together, and show the Lyapunov construction failing "
            "quietly on an unstable system."
        ),
        "intuition": (
            "A stable A gives a unique positive definite P; an unstable A gives a "
            "unique indefinite one without complaint; and eigenvalues summing to "
            "zero leave the equation with no solution at all."
        ),
        "defects": [
            {
                "suffix": "undecided_counts_as_definite",
                "primary": "unknown_as_pass",
                "labels": ["unknown_as_pass", "undecidable_positivity"],
                "severity": "critical",
                "note": (
                    "the definiteness test accepts an undecided sign as a pass, "
                    "so a P whose minors sympy cannot resolve would be certified "
                    "as a Lyapunov function; the case still passes because this "
                    "particular P is decidable"
                ),
                "patches": [
                    (
                        'check("that_solution_is_positive_definite",\n'
                        '      leading.is_positive is True and determinant.is_positive is True,\n'
                        '      f"leading minor {leading}, determinant {determinant}, both positive")',
                        '# is_positive returns None when the sign cannot be settled, and a None\n'
                        '# there means nothing has been found against the matrix.\n'
                        'check("that_solution_is_positive_definite",\n'
                        '      leading.is_positive is not False\n'
                        '      and determinant.is_positive is not False,\n'
                        '      f"leading minor {leading}, determinant {determinant}, nothing "\n'
                        '      "found against either")',
                    ),
                ],
            },
            {
                "suffix": "residual_waved_through",
                "primary": "wrong_tolerance",
                "labels": ["wrong_tolerance", "link_in_comment"],
                "severity": "major",
                "note": (
                    "the model that predicts the residual of the decay rate is "
                    "dropped for a band twenty times larger and a comment saying "
                    "the residual is understood, so the contamination is asserted "
                    "rather than measured and the second window is never used"
                ),
                "patches": [
                    (
                        'check("the_residual_is_the_faster_mode_rather_than_numerical_noise",\n'
                        '      abs(late_gap / mode_contamination(7000, 9000) - 1) < 1e-3,\n'
                        '      f"gap {late_gap:.6e} against the predicted contamination "\n'
                        '      f"{mode_contamination(7000, 9000):.6e}, agreeing to "\n'
                        '      f"{abs(late_gap / mode_contamination(7000, 9000) - 1):.2e}")\n'
                        '\n'
                        'early_gap = 2 * slowest - decay_rate(2000, 4000)\n'
                        'shrinkage = early_gap / late_gap\n'
                        'predicted_shrinkage = mode_contamination(2000, 4000) / mode_contamination(7000, 9000)\n'
                        'check("moving_the_window_later_shrinks_the_residual_as_predicted",\n'
                        '      abs(shrinkage / predicted_shrinkage - 1) < 0.05,\n'
                        '      f"the gap falls by a factor {shrinkage:.1f} between the windows and the "\n'
                        '      f"model asks for {predicted_shrinkage:.1f}")',
                        '# The residual is the faster mode, which is well understood, so a band of\n'
                        '# one percent is generous enough and the comparison against the model\n'
                        '# adds nothing.\n'
                        'check("the_residual_is_the_faster_mode_rather_than_numerical_noise",\n'
                        '      abs(late_gap) < 1e-2,\n'
                        '      f"gap {late_gap:.6e}, inside the expected band")\n'
                        'check("moving_the_window_later_shrinks_the_residual_as_predicted", True,\n'
                        '      "a later window is closer, as the mode structure requires")',
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


def dead_assignments(source: str) -> list[str]:
    """Module-level names a sound validator computes and never reads again.

    Two of the six blockers found in the 2026-09-11 review had exactly this
    signature. In one the characteristic polynomial of the matrix under test was
    computed and never used, so the leg that claimed to analyse it was in fact
    analysing a hand-written expression and certified a matrix with complex
    eigenvalues. In the other the continuity law was assigned and never read,
    leaving a predicate that mentioned neither density nor pressure. A quantity
    worth computing in a validator is worth using; if it is not used, whatever
    the leg checks is not what the name says it checks.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:              # pragma: no cover - build-time guard
        return [f"cannot parse: {exc}"]
    assigned: dict[str, int] = {}
    for node in tree.body:                  # module level only
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned.setdefault(target.id, node.lineno)
    loaded = {
        node.id for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    return [
        f"line {line}: '{name}' is computed and never read"
        for name, line in sorted(assigned.items(), key=lambda item: item[1])
        if name not in loaded and not name.startswith("_")
    ]


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

        dead = dead_assignments(source)
        if dead:
            problems.append(
                f"{base}: sound validator computes values it never uses: "
                + "; ".join(dead)
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
