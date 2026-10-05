"""Reintroduce historical context truncation in memory; regression tests must fail."""
import os
import sys
import tempfile
import unittest

# Runs outside pytest, so it gets the isolation tests/conftest.py gives the
# suite: its own lock root and workspace (never the machine-wide cycle slot a
# production cycle may hold), no progress window, no CLI auth probe. Without
# this, a running production cycle made the simulated cycle return BUSY.
_ISOLATION = tempfile.mkdtemp(prefix="astra_negctl_")
os.environ["ASTRA_LOCK_ROOT"] = os.path.join(_ISOLATION, "locks")
os.environ["ASTRA_WORKSPACE_ROOT"] = os.path.join(_ISOLATION, "workspace")
os.environ["ASTRA_PROGRESS_WINDOW"] = "0"
os.environ["ASTRA_CLI_AUTH_PREFLIGHT"] = "0"
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import astra_tool
from core.llm_client import ASTRAIntelligence
from tests.test_full_claim_context import FullClaimContextTests

build = astra_tool.build_translation_input
review = ASTRAIntelligence.review_validation_code
repair = ASTRAIntelligence.repair_validation_code


def broken_build(goal, intuition, inputs, conjecture):
    return build(goal, intuition[:3500], inputs, conjecture)


async def broken_review(self, shared_goal, conjecture, code, static_context=None):
    return await review(self, shared_goal, conjecture[:5000], code, static_context)


async def broken_repair(self, conjecture, previous_code, repair_instructions):
    return await repair(self, conjecture[:5000], previous_code, repair_instructions)


with patch.object(astra_tool, "build_translation_input", broken_build), patch.object(
    ASTRAIntelligence, "review_validation_code", broken_review
), patch.object(ASTRAIntelligence, "repair_validation_code", broken_repair):
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(FullClaimContextTests)
    result = unittest.TextTestRunner(verbosity=1).run(suite)

ok = result.testsRun == 3 and len(result.failures) == 3 and not result.errors
print("NEGATIVE CONTROL:", "PASS (all three guards reject historical truncation)" if ok else "FAIL")
sys.exit(0 if ok else 1)
