"""Passing validators complete naturally (1.1.11, from ASTRA 2.0 a345fa4)."""
import unittest

from agents.translator import FORMAL_TRANSLATOR_VNEXT_ADDENDUM


class SuccessPathExit(unittest.TestCase):
    def test_the_author_contract_forbids_sys_exit_on_pass(self):
        self.assertIn("7. On the SUCCESS path", FORMAL_TRANSLATOR_VNEXT_ADDENDUM)
        self.assertIn("Never call `sys.exit(0)`", FORMAL_TRANSLATOR_VNEXT_ADDENDUM)
        self.assertIn("exits with code 3 per clause 6", FORMAL_TRANSLATOR_VNEXT_ADDENDUM)


if __name__ == "__main__":
    unittest.main()
