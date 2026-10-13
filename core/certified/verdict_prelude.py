"""ASTRA verdict helper: decisive legs decide, corroborative legs corroborate.

Loaded by ``# ASTRA_CERTIFIED: verdict`` (pure Python) and, together with the
ball arithmetic, by ``# ASTRA_CERTIFIED: arb``. Motivation (9 October 2026):
three validators the reviewer otherwise accepted, Kondo's integral asymptotic
twice and a synthetic sector bound, were sent back because one
``all(checks.values())`` mixed proof legs with quadrature or sampling, so a
finite-precision sample could print VERDICT: FAIL on an asymptotic claim.

Each leg is recorded with ``leg(name, value, detail, role)``; ``value`` is
True (the leg establishes its part of the claim), False (the leg establishes
that the claim fails: a certified counterexample, an exact mismatch) or None
(the leg could not decide). ``decide()`` then prints the verdict:

* any decisive leg False                      -> VERDICT: FAIL
* else any decisive leg None                  -> no verdict, exit 5 (UNDECIDED)
* else any corroborative leg not True         -> no verdict, exit 6
                                                 (CORROBORATION_MISMATCH)
* else                                        -> VERDICT: PASS

A corroborative leg can therefore never refute, and a disagreement between a
proof and its cross-check is reported as an operational problem to look at,
not as a scientific verdict.
"""
# No `from __future__` import: the preludes are concatenated, and such an
# import is only legal at the top of a file.
import sys as _astra_verdict_sys

ASTRA_VERDICT_VERSION = "verdict-1"

_astra_legs = []
_astra_decided = []


def leg(name: str, value, detail: str = "", role: str = "decisive"):
    """Record and print one leg (CHECK line). Returns ``value``."""
    if role not in ("decisive", "corroborative"):
        raise ValueError("role must be 'decisive' or 'corroborative'")
    if value is not True and value is not False and value is not None:
        raise TypeError(
            f"leg {name!r}: value must be True, False or None, not {type(value).__name__}; "
            "convert explicitly (bool(...) only when the test is exact or certified)"
        )
    if _astra_decided:
        raise RuntimeError("leg() after decide(): record every leg first")
    mark = {True: "OK", False: "FAIL", None: "UNDECIDED"}[value]
    line = f"CHECK {name}: {mark} [{role}]"
    if detail:
        line += f" -- {' '.join(str(detail).split())}"
    print(line, flush=True)
    _astra_legs.append((str(name), role, value))
    return value


def run_leg(name: str, fn, role: str = "decisive"):
    """Run ``fn()``, which returns a value or (value, detail). An exception
    named Undecided (the ball-arithmetic prelude raises it) records None;
    any other exception propagates, as a real error should."""
    try:
        out = fn()
    except Exception as exc:  # noqa: BLE001 - only Undecided is absorbed
        if type(exc).__name__ == "Undecided":
            return leg(name, None, f"undecided: {exc}", role)
        raise
    value, detail = out if isinstance(out, tuple) and len(out) == 2 else (out, "")
    return leg(name, value, detail, role)


def decide() -> str:
    """Print the verdict from the recorded legs (call it once, at the end)."""
    if _astra_decided:
        raise RuntimeError("decide() was already called")
    _astra_decided.append(True)
    decisive = [(n, v) for n, r, v in _astra_legs if r == "decisive"]
    corroborative = [(n, v) for n, r, v in _astra_legs if r == "corroborative"]
    if not decisive:
        raise RuntimeError("decide() needs at least one decisive leg")
    refuted = [n for n, v in decisive if v is False]
    undecided = [n for n, v in decisive if v is None]
    disagree = [n for n, v in corroborative if v is not True]
    if refuted:
        note = f"; corroborative legs not OK: {', '.join(disagree)}" if disagree else ""
        print(f"DECISION: FAIL -- refuted by decisive leg(s): {', '.join(refuted)}{note}", flush=True)
        print("VERDICT: FAIL", flush=True)
        return "FAIL"
    if undecided:
        print(f"DECISION: UNDECIDED -- decisive leg(s) not decided: {', '.join(undecided)}", flush=True)
        _astra_verdict_sys.exit(5)
    if disagree:
        print(
            "DECISION: CORROBORATION_MISMATCH -- every decisive leg holds but "
            f"corroborative leg(s) disagree: {', '.join(disagree)}",
            flush=True,
        )
        _astra_verdict_sys.exit(6)
    print(f"DECISION: PASS -- {len(decisive)} decisive and {len(corroborative)} corroborative leg(s) hold", flush=True)
    print("VERDICT: PASS", flush=True)
    return "PASS"
