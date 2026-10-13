"""The dimensional check wired into the deterministic verdict guard.

`core/dimensional_analysis.py` made the check callable; this is where it
becomes part of the cycle. It rides the mechanism that already exists for
exactly this purpose: `assess_verdict` is ASTRA's zero-LLM, zero-quota
auditor of whether a printed PASS is credible, and `astra_tool._apply_guard`
lets that auditor override the analyst. A declared equation whose two sides
carry different dimensions cannot be true or false, so a PASS resting on it
is not credible, and the existing WEAK_PASS degradation is the right
consequence -- not a hard failure.

Two design choices are pinned here because both could be silently reversed
by a later edit that looks like a tightening:

* the check is OPT-IN. A validator that declares nothing is audited on
  nothing. Requiring the declaration would turn the silence of every
  non-dimensional validator into suspicion -- false positives on the
  majority to catch a minority.
* only an identity that was EVALUATED and failed marks the verdict suspect.
  One that could not be resolved is recorded as unverifiable and costs
  nothing, because unresolvable units are usually legitimate prose. Measured
  against pint 0.25.3 on 2026-08-30: 'ratio', 'none', 'per second' and
  'arbitrary units' do not parse though scientists write them, while 'N/A'
  parses as newton/ampere and 'a.u.' as [time]*[mass]. Penalising the
  unresolvable would degrade correct validators and still miss the dangerous
  placeholders, which parse.

Production (1.1.11) puts the guard behind ASTRA_DIMENSIONAL_GUARD, default
"record"; these tests exercise the enforcing mode 2.0 shipped, and
test_dimensional_guard_modes.py pins the switch.
"""
import os
import unittest
from unittest.mock import patch

from astra_tool import _apply_guard

_ENFORCE = patch.dict(os.environ, {"ASTRA_DIMENSIONAL_GUARD": "1"})


def setUpModule():
    _ENFORCE.start()


def tearDownModule():
    _ENFORCE.stop()
from core.verdict_guard import assess_verdict, audit_dimensions

PASSING_STDOUT = "CHECK sym: OK\nCHECK num: OK\nCHECK lim: OK\nVERDICT: PASS"
PASSING_EXEC = {"stdout": PASSING_STDOUT, "verdict": "PASS"}

SOUND_SCRIPT = """
# ASTRA_UNITS: rho=kg/m**3, v=m/s, L=m, mu=Pa*s
# ASTRA_DIMENSION: rho*v*L/mu == dimensionless
def check():
    if 1 != 1:
        print("VERDICT: FAIL")
    assert 1 == 1
    print("VERDICT: PASS")
check()
"""

# The failure mode reynolds_dimensionless.json documents in its own case
# file: kinematic viscosity kept in the dynamic-viscosity formula.
KINEMATIC_SCRIPT = SOUND_SCRIPT.replace("mu=Pa*s", "mu=m**2/s")

UNDECLARED_SCRIPT = """
def check():
    if 1 != 1:
        print("VERDICT: FAIL")
    assert 1 == 1
    print("VERDICT: PASS")
check()
"""


class AuditDimensions(unittest.TestCase):
    def test_a_sound_declaration_checks_clean(self):
        result = audit_dimensions(SOUND_SCRIPT)
        self.assertTrue(result["declared"])
        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["inconsistent"], [])
        self.assertEqual(result["unverifiable"], [])

    def test_the_cases_own_failure_mode_is_caught(self):
        result = audit_dimensions(KINEMATIC_SCRIPT)
        self.assertEqual(len(result["inconsistent"]), 1)
        self.assertIn("no es adimensional", result["inconsistent"][0])

    def test_no_declaration_means_no_audit(self):
        result = audit_dimensions(UNDECLARED_SCRIPT)
        self.assertFalse(result["declared"])
        self.assertEqual(result["checked"], 0)
        self.assertEqual(result["inconsistent"], [])

    def test_units_spread_over_several_lines_are_merged(self):
        script = (
            "# ASTRA_UNITS: F=N, m=kg\n"
            "# ASTRA_UNITS: a=m/s**2\n"
            "# ASTRA_DIMENSION: F == m*a\n"
        )
        result = audit_dimensions(script)
        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["inconsistent"], [])

    def test_two_sided_identity_mismatch_is_inconsistent(self):
        script = (
            "# ASTRA_UNITS: F=N, m=kg, a=m/s**2\n"
            "# ASTRA_DIMENSION: F == m*a**2\n"
        )
        result = audit_dimensions(script)
        self.assertEqual(len(result["inconsistent"]), 1)

    def test_adding_incompatible_dimensions_is_inconsistent(self):
        # The physical type error: Force = Mass + Acceleration.
        script = (
            "# ASTRA_UNITS: F=N, m=kg, a=m/s**2\n"
            "# ASTRA_DIMENSION: F == m + a\n"
        )
        self.assertEqual(len(audit_dimensions(script)["inconsistent"]), 1)

    def test_unresolvable_units_are_unverifiable_not_inconsistent(self):
        script = (
            "# ASTRA_UNITS: x=ratio, y=none\n"
            "# ASTRA_DIMENSION: x == y\n"
        )
        result = audit_dimensions(script)
        self.assertEqual(result["inconsistent"], [])
        self.assertEqual(len(result["unverifiable"]), 1)

    def test_a_malformed_identity_is_unverifiable(self):
        script = "# ASTRA_UNITS: v=m/s\n# ASTRA_DIMENSION: v is dimensionless\n"
        result = audit_dimensions(script)
        self.assertEqual(result["inconsistent"], [])
        self.assertEqual(len(result["unverifiable"]), 1)


class GuardIntegration(unittest.TestCase):
    def test_sound_declaration_leaves_the_verdict_alone(self):
        guard = assess_verdict(SOUND_SCRIPT, PASSING_EXEC)
        self.assertFalse(guard["verdict_suspect"])

    def test_inconsistent_declaration_makes_the_verdict_suspect(self):
        guard = assess_verdict(KINEMATIC_SCRIPT, PASSING_EXEC)
        self.assertTrue(guard["verdict_suspect"])
        self.assertTrue(
            any("inconsistencia dimensional" in r for r in guard["reasons"])
        )

    def test_unverifiable_units_do_not_make_it_suspect(self):
        script = (
            "# ASTRA_UNITS: x=ratio\n"
            "# ASTRA_DIMENSION: x == dimensionless\n" + UNDECLARED_SCRIPT
        )
        guard = assess_verdict(script, PASSING_EXEC)
        self.assertFalse(guard["verdict_suspect"])
        self.assertEqual(len(guard["dimensions"]["unverifiable"]), 1)

    def test_a_failing_run_is_not_audited(self):
        # The module's existing contract: FAIL and NONE are honest outcomes
        # with nothing to audit. A dimensional slip in a script that already
        # reports FAIL must not add noise.
        guard = assess_verdict(
            KINEMATIC_SCRIPT, {"stdout": "VERDICT: FAIL", "verdict": "FAIL"}
        )
        self.assertFalse(guard["verdict_suspect"])

    def test_non_python_scripts_are_still_audited(self):
        # Sage and Maxima use `#` for comments too, and their scripts do not
        # parse as Python -- the AST audit returns early on them, so the
        # dimensional guard has to run before that point or they lose it.
        sage = (
            "# ASTRA_ENGINE: sage\n"
            "# ASTRA_UNITS: rho=kg/m**3, v=m/s, L=m, mu=m**2/s\n"
            "# ASTRA_DIMENSION: rho*v*L/mu == dimensionless\n"
            "var('x y')  # not valid Python\n"
            "print('VERDICT: PASS')\n"
        )
        guard = assess_verdict(sage, PASSING_EXEC)
        self.assertTrue(guard["verdict_suspect"])
        self.assertTrue(
            any("inconsistencia dimensional" in r for r in guard["reasons"])
        )


class PipelineEffect(unittest.TestCase):
    """What the cycle actually does with the finding."""

    def test_validated_degrades_to_weak_pass(self):
        exec_result = {
            **PASSING_EXEC,
            "guard": assess_verdict(KINEMATIC_SCRIPT, PASSING_EXEC),
        }
        analysis = _apply_guard(
            {"status": "VALIDATED", "reasoning": "all legs agree"}, exec_result
        )
        self.assertEqual(analysis["status"], "WEAK_PASS")
        self.assertIn("dimensional", analysis["reasoning"])

    def test_a_sound_script_is_not_degraded(self):
        exec_result = {
            **PASSING_EXEC,
            "guard": assess_verdict(SOUND_SCRIPT, PASSING_EXEC),
        }
        analysis = _apply_guard(
            {"status": "VALIDATED", "reasoning": "all legs agree"}, exec_result
        )
        self.assertEqual(analysis["status"], "VALIDATED")

    def test_an_undeclared_script_is_not_degraded(self):
        # The opt-in promise, at the level the user actually feels it.
        exec_result = {
            **PASSING_EXEC,
            "guard": assess_verdict(UNDECLARED_SCRIPT, PASSING_EXEC),
        }
        analysis = _apply_guard(
            {"status": "VALIDATED", "reasoning": "all legs agree"}, exec_result
        )
        self.assertEqual(analysis["status"], "VALIDATED")


if __name__ == "__main__":
    unittest.main()
