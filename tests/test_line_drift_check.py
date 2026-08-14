"""The drift check must separate behavior from prose, or it will be ignored.

A reworded docstring after a port is not drift. If the report flags it, the
reader learns to skim past the report, and the next real production-only fix
goes unnoticed - which is the failure this tool exists to prevent.
"""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_checker():
    spec = importlib.util.spec_from_file_location(
        "check_line_drift", ROOT / "scripts" / "check_line_drift.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BehaviorDigestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.checker = load_checker()

    def digest(self, source: str):
        return self.checker.behavior_digest(source.encode("utf-8"))

    def test_comment_changes_do_not_count_as_behavior(self):
        a = "def f(x):\n    # add one\n    return x + 1\n"
        b = "def f(x):\n    # increment by one, ported 2026-08-13\n    return x + 1\n"
        self.assertEqual(self.digest(a), self.digest(b))

    def test_docstring_rewording_does_not_count_as_behavior(self):
        a = 'def f(x):\n    """Add one."""\n    return x + 1\n'
        b = 'def f(x):\n    """Increment the argument by one.\n\n    Ported.\n    """\n    return x + 1\n'
        self.assertEqual(self.digest(a), self.digest(b))

    def test_module_and_class_docstrings_are_stripped_too(self):
        a = '"""Module A."""\n\n\nclass C:\n    """Class A."""\n\n    x = 1\n'
        b = '"""Module B, reworded."""\n\n\nclass C:\n    """Class B."""\n\n    x = 1\n'
        self.assertEqual(self.digest(a), self.digest(b))

    def test_a_docstring_only_body_survives_stripping(self):
        # Removing the docstring must not produce an empty body.
        self.assertIsNotNone(self.digest('def f():\n    """Only a docstring."""\n'))

    def test_real_code_changes_are_still_detected(self):
        a = "def f(x):\n    return x + 1\n"
        b = "def f(x):\n    return x + 2\n"
        self.assertNotEqual(self.digest(a), self.digest(b))

    def test_a_changed_string_literal_is_behavior_not_prose(self):
        a = 'MODE = "local"\n'
        b = 'MODE = "remote"\n'
        self.assertNotEqual(self.digest(a), self.digest(b))

    def test_unparseable_input_degrades_to_none(self):
        self.assertIsNone(self.digest("def broken(:\n"))
        self.assertIsNone(self.checker.behavior_digest(b"\xff\xfe not utf-8"))

    def test_line_endings_never_affect_the_byte_digest(self):
        crlf = b'x = 1\r\ny = 2\r\n'
        lf = b'x = 1\ny = 2\n'
        self.assertEqual(
            self.checker.normalized_digest(crlf),
            self.checker.normalized_digest(lf),
        )


if __name__ == "__main__":
    unittest.main()
