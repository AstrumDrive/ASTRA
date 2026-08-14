"""G2 engine smoke tests: execute one real artifact per configured engine.

The architecture audit discovers routes and configuration; it never runs
anything, so a PASS there says the engine is reachable, not that it works.
`ASTRA2_ACCEPTANCE.md` G2 asks for the second thing, and this script provides
it: each artifact goes through ASTRA's actual local router and must print its
own `VERDICT: PASS`, so a silent misconfiguration cannot masquerade as
success.

Every artifact is small but non-trivial - a wrong answer fails rather than a
missing import - and each one ends in an executable verdict rather than a
truthy Python expression. Consumes no model quota.

  python scripts/run_engine_smokes.py
  python scripts/run_engine_smokes.py --only lean4 --timeout 600
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from core.engine_router import available_cas  # noqa: E402
from core.executor import execute_python_code  # noqa: E402

OUT_DIR = ROOT / "workspace" / "engine_smokes"

# Each artifact proves the engine computed something, not merely that it
# started: the checks would fail on a wrong result, not only on a crash.
ARTIFACTS: dict[str, str] = {
    "python": (
        "import sympy as sp\n"
        "x = sp.symbols('x', real=True)\n"
        "residual = sp.simplify(sp.expand((x + 1) ** 2) - (x**2 + 2*x + 1))\n"
        "ok = residual == 0\n"
        "print('CHECK expand_identity:', 'OK' if ok else 'FAIL')\n"
        "print('VERDICT: PASS' if ok else 'VERDICT: FAIL')\n"
    ),
    "z3": (
        "from z3 import Reals, Solver, And, Not, sat, unsat\n"
        "x, y = Reals('x y')\n"
        "s = Solver()\n"
        "# AM-GM for positive reals must have no counterexample.\n"
        "s.add(And(x > 0, y > 0, Not(x + y >= 2 * (x * y) ** 0.5)))\n"
        "result = s.check()\n"
        "ok = result == unsat\n"
        "print('CHECK am_gm_no_counterexample:', result)\n"
        "print('VERDICT: PASS' if ok else 'VERDICT: FAIL')\n"
    ),
    "sage": (
        "# ASTRA_ENGINE: sage\n"
        "R.<t> = QQ[]\n"
        "factored = factor(t^4 - 1)\n"
        "ok = (len(list(factored)) == 3) and (expand(factored.value()) == t^4 - 1)\n"
        "print('CHECK factor_t4_minus_1:', factored)\n"
        "print('VERDICT: PASS' if ok else 'VERDICT: FAIL')\n"
    ),
    # The engine marker is a hash comment; the router strips it before writing
    # the file, so Maxima never sees it. A C-style marker is NOT recognised and
    # the artifact would silently run as Python.
    "maxima": (
        "# ASTRA_ENGINE: maxima\n"
        "res: ratsimp(integrate(2*x, x, 0, 3) - 9);\n"
        "if res = 0 then print(\"CHECK definite_integral: OK\")"
        " else print(\"CHECK definite_integral: FAIL\");\n"
        "if res = 0 then print(\"VERDICT: PASS\")"
        " else print(\"VERDICT: FAIL\");\n"
    ),
    # Contracting an antisymmetric tensor with a symmetric one must canonicalise
    # to exactly zero: unambiguous output, and a wrong answer is not zero.
    "cadabra": (
        "# ASTRA_ENGINE: cadabra\n"
        "{a,b,c,d}::Indices.\n"
        "A_{a b}::AntiSymmetric.\n"
        "S_{a b}::Symmetric.\n"
        "ex := A_{a b} S^{a b};\n"
        "canonicalise(ex)\n"
        "ok = (str(ex).strip() == '0')\n"
        "print('CHECK antisymmetric_symmetric_contraction:', ex)\n"
        "print('VERDICT: PASS' if ok else 'VERDICT: FAIL')\n"
    ),
    # Kernel-checked against the pinned Mathlib. Unicode on purpose: a Lean
    # artifact is exactly where the Windows PowerShell encoding defect showed
    # up, so the smoke keeps the binders that would have been destroyed.
    "lean4": (
        "# ASTRA_ENGINE: lean4\n"
        "import Mathlib\n"
        "\n"
        "theorem astra_smoke_add_comm : ∀ n m : Nat, n + m = m + n :=\n"
        "  Nat.add_comm\n"
        "\n"
        "example (x y : ℝ) : (x + y) ^ 2 = x ^ 2 + 2 * x * y + y ^ 2 := by\n"
        "  ring\n"
        "\n"
        "example (x : ℝ) : 0 ≤ x ^ 2 := by\n"
        "  positivity\n"
        "\n"
        "#print axioms astra_smoke_add_comm\n"
    ),
}

# Lean has no print protocol: a clean elaboration plus an axiom line that
# names only the standard axioms is the verdict.
LEAN_EXPECTED = ("astra_smoke_add_comm", "propext", "Classical.choice", "Quot.sound")


def lean_ok(result: dict) -> tuple[bool, str]:
    if result.get("exit_code") != 0:
        return False, "lean exited nonzero"
    stdout = (result.get("stdout") or "") + (result.get("stderr") or "")
    if "error" in stdout.lower():
        return False, "lean reported an error"
    if "astra_smoke_add_comm" not in stdout:
        return False, "no axiom report for the theorem"
    if "sorryAx" in stdout:
        return False, "proof depends on sorry"
    return True, "kernel-checked, axioms clean"


async def run_one(name: str, source: str, timeout: int) -> dict:
    started = time.monotonic()
    result = await execute_python_code(source, timeout=timeout)
    elapsed = round(time.monotonic() - started, 2)
    stdout = result.get("stdout") or ""
    if name == "lean4":
        ok, note = lean_ok(result)
    else:
        ok = "VERDICT: PASS" in stdout and result.get("exit_code") == 0
        note = "verdict PASS" if ok else "no PASS verdict"
    return {
        "engine": name,
        "ok": ok,
        "note": note,
        "seconds": elapsed,
        "exit_code": result.get("exit_code"),
        "stdout_tail": stdout[-600:],
        "stderr_tail": (result.get("stderr") or "")[-600:],
    }


async def main_async(args) -> int:
    selected = (
        [name.strip() for name in args.only.split(",") if name.strip()]
        if args.only
        else list(ARTIFACTS)
    )
    unknown = [name for name in selected if name not in ARTIFACTS]
    if unknown:
        print(f"Unknown engine(s): {unknown}. Known: {list(ARTIFACTS)}")
        return 2

    print("configured CAS routes:", json.dumps(available_cas(), ensure_ascii=False))
    print()
    results = []
    for name in selected:
        print(f"[running] {name} ...", flush=True)
        outcome = await run_one(name, ARTIFACTS[name], args.timeout)
        results.append(outcome)
        flag = "PASS" if outcome["ok"] else "FAIL"
        print(f"[{flag}] {name:8s} {outcome['seconds']:7.1f}s  {outcome['note']}")
        if not outcome["ok"]:
            tail = (outcome["stderr_tail"] or outcome["stdout_tail"] or "").strip()
            if tail:
                print(f"         {tail.splitlines()[-1][:200]}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": "astra-engine-smoke/0.1",
        "results": results,
        "passed": sum(1 for r in results if r["ok"]),
        "total": len(results),
    }
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = OUT_DIR / f"engine_smoke_{stamp}.json"
    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print()
    print(f"{report['passed']}/{report['total']} engines passed")
    print(f"report: {path}")
    return 0 if report["passed"] == report["total"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", default="", help="comma-separated engine names")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args(argv)
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
