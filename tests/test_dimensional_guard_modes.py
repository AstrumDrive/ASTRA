"""ASTRA_DIMENSIONAL_GUARD: record by default, enforce on request, off on request."""
import os
import unittest
from unittest.mock import patch

from core.verdict_guard import assess_verdict

INCONSISTENT = (
    "# ASTRA_UNITS: m=kg, a=m/s**2\n"
    "# ASTRA_DIMENSION: m == a\n"
    "x = 1\n"
    "ok = x == 1\n"
    "print('CHECK one: OK' if ok else 'CHECK one: FAIL')\n"
    "print('VERDICT: PASS' if ok else 'VERDICT: FAIL')\n"
)
RUN = {"stdout": "CHECK one: OK\nVERDICT: PASS\n", "stderr": "", "exit_code": 0}


def _assess(mode):
    env = {} if mode is None else {"ASTRA_DIMENSIONAL_GUARD": mode}
    with patch.dict(os.environ, env, clear=False):
        if mode is None:
            os.environ.pop("ASTRA_DIMENSIONAL_GUARD", None)
        return assess_verdict(INCONSISTENT, RUN)


class DimensionalGuardModes(unittest.TestCase):
    def test_default_records_without_touching_the_verdict(self):
        out = _assess(None)
        self.assertEqual(out["dimensions"]["mode"], "record")
        self.assertTrue(out["dimensions"]["inconsistent"])
        self.assertFalse(any("dimensional" in r for r in out.get("reasons", [])))

    def test_enforce_makes_the_pass_suspect(self):
        out = _assess("1")
        self.assertTrue(out["verdict_suspect"])
        self.assertTrue(any("dimensional" in r for r in out["reasons"]))

    def test_off_skips_the_audit(self):
        self.assertNotIn("dimensions", _assess("0"))


if __name__ == "__main__":
    unittest.main()
