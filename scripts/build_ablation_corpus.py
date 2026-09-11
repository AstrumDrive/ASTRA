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
