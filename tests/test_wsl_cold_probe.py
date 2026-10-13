"""A cold WSL boot is not an absent engine (1.1.11, from ASTRA 2.0 8f2d0c1)."""
import subprocess
import unittest
from unittest.mock import patch

from core import engine_router


class ColdWslProbe(unittest.TestCase):
    def test_engine_probes_wait_for_a_cold_boot(self):
        seen = []

        def fake_run(*args, **kwargs):
            seen.append(kwargs.get("timeout"))
            return subprocess.CompletedProcess(args[0], 0, "/usr/bin/sage\n", "")

        with patch.object(engine_router.subprocess, "run", side_effect=fake_run):
            self.assertTrue(engine_router._wsl_which("sage"))
            engine_router._wsl_test("-x", "/usr/bin/sage")
        self.assertEqual(seen, [60, 60])


if __name__ == "__main__":
    unittest.main()
