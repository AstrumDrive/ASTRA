"""Two machine-wide cycle slots: two cycles run, a third waits (1.1.14)."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.runtime_resources import acquire_cycle_slot


class TwoCycleSlots(unittest.TestCase):
    def test_two_slots_admit_two_cycles_and_refuse_the_third(self):
        with tempfile.TemporaryDirectory() as locks, patch.dict(
            os.environ, {"ASTRA_LOCK_ROOT": locks}, clear=False
        ):
            first, _ = acquire_cycle_slot(Path(locks), 2)
            second, _ = acquire_cycle_slot(Path(locks), 2)
            third, active = acquire_cycle_slot(Path(locks), 2)
            try:
                self.assertIsNotNone(first)
                self.assertIsNotNone(second)
                self.assertIsNone(third)
                self.assertEqual(len(active), 2)
            finally:
                for slot in (first, second):
                    if slot is not None:
                        slot.release()
            again, _ = acquire_cycle_slot(Path(locks), 2)
            self.assertIsNotNone(again)
            again.release()


if __name__ == "__main__":
    unittest.main()
