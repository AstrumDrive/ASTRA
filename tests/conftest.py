"""Test-session isolation for machine-wide resources.

The deliberative-cycle slot became machine-wide on 2026-08-13 so the 2.0 line
and production cannot deliberate against the same subscription at once. That
is right for real runs and wrong for tests: a handful of cycle tests patch the
model client and never touch a model, yet they still acquire the slot, so they
failed with BUSY the moment production started a genuine cycle on this
machine. A suite whose result depends on unrelated activity is not measuring
what it claims to.

Pointing ASTRA_LOCK_ROOT at a per-session temporary directory keeps the tests
hermetic while leaving the production semantics intact. The lock behaviour
itself is still covered, by test_cycle_lock_root.py, which sets its own roots
explicitly.
"""
from __future__ import annotations

import os
import tempfile

import pytest


@pytest.fixture(scope="session", autouse=True)
def isolated_cycle_lock_root():
    """Give the whole test session its own cycle-lock directory."""
    previous = os.environ.get("ASTRA_LOCK_ROOT")
    with tempfile.TemporaryDirectory(prefix="astra_test_locks_") as tmp:
        os.environ["ASTRA_LOCK_ROOT"] = tmp
        try:
            yield tmp
        finally:
            if previous is None:
                os.environ.pop("ASTRA_LOCK_ROOT", None)
            else:
                os.environ["ASTRA_LOCK_ROOT"] = previous
