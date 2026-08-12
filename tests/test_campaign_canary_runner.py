"""Stage 6 infrastructure: the campaign canary runner (no model calls)."""
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from core.campaign_models import validate_record_id
from core.campaign_store import CampaignStore

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_campaign_canary.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("run_campaign_canary", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CanaryRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = load_runner()

    def fresh_dir(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)

    def test_preregistration_fingerprint_is_frozen(self):
        expected = (
            ROOT
            / "docs"
            / "benchmarks"
            / "ASTRA2_CANARY_PREREGISTRATION_V1.sha256"
        ).read_text(encoding="utf-8").strip()
        self.assertEqual(self.runner.preregistration_fingerprint(), expected)
        self.assertEqual(self.runner.verify_preregistration(), expected)

    def test_build_plan_respects_frozen_budget_caps(self):
        plan = self.runner.build_plan(
            "gr_invariant_audit", max_cycles=3, wall_ceiling_minutes=60
        )
        self.assertEqual(plan["case"], "gr_invariant_audit")
        self.assertLessEqual(plan["budget"]["cycles"], 3)
        self.assertEqual(
            plan["budget"]["model_calls"], plan["budget"]["cycles"] * 12
        )
        self.assertLessEqual(plan["budget"]["wall_seconds"], 3600)
        self.assertEqual(plan["budget"]["remote_jobs"], 0)
        self.assertEqual(plan["oracle"], "local")
        selected = plan["seed_portfolio"]["selected"]
        self.assertEqual(selected["method_family"], "brief_bootstrap")
        self.assertIsNotNone(selected["crux"])
        self.assertIn(selected["deliverable"], plan["deliverables"])
        with self.assertRaises(SystemExit):
            self.runner.build_plan("case_that_does_not_exist")

    def test_dry_run_prints_the_plan_and_writes_nothing(self):
        root = self.fresh_dir()
        out = self.fresh_dir()
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.runner.main(
                ["--dry-run", "--root", str(root), "--out", str(out)]
            )
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertIn("plan", payload)
        self.assertIn("preregistration_fingerprint", payload)
        self.assertEqual(list(root.iterdir()), [])
        self.assertEqual(list(out.iterdir()), [])

    def test_live_without_yes_refuses_and_spends_nothing(self):
        root = self.fresh_dir()
        out = self.fresh_dir()
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.runner.main(
                ["--live", "--root", str(root), "--out", str(out)]
            )
        self.assertEqual(code, 2)
        self.assertEqual(list(root.iterdir()), [])
        self.assertEqual(list(out.iterdir()), [])

    def test_offline_smoke_runs_the_full_loop_without_models(self):
        root = self.fresh_dir()
        out = self.fresh_dir()
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = self.runner.main(
                [
                    "--offline-smoke",
                    "--root",
                    str(root),
                    "--out",
                    str(out),
                    "--max-cycles",
                    "2",
                ]
            )
        self.assertEqual(code, 0)
        summaries = list(out.glob("offline_smoke_*.json"))
        self.assertEqual(len(summaries), 1)
        summary = json.loads(summaries[0].read_text(encoding="utf-8"))
        self.assertEqual(summary["operability"]["episodes_completed"], 2)
        self.assertEqual(summary["operability"]["evidence_recorded"], 2)
        metrics = summary["trajectory_metrics"]
        self.assertEqual(metrics["episodes_completed"], 2)
        self.assertEqual(metrics["credible_evidence_episodes"], 2)
        # bootstrap branch + the promoted independent_check alternative
        self.assertEqual(metrics["branch_preservation"], 1)
        self.assertGreaterEqual(summary["operability"]["decisions_recorded"], 2)
        campaign_id = summary["campaign_id"]
        validate_record_id(campaign_id, "campaign")
        # The ledger must replay clean and the checkpoint must validate.
        store = CampaignStore(
            root, campaign_id, source_commit=summary["plan"]["brief_sha256"][:40]
        )
        self.addCleanup(store.close)
        result = store.replay()
        self.assertEqual(result.health.status, "HEALTHY")
        state = result.state
        self.assertEqual(len(state.episodes), 2)
        self.assertTrue(state.evidence)
        self.assertEqual(
            store.load_checkpoint()["last_sequence"], state.last_sequence
        )
        # The synthesis portfolio promoted a materially different alternative
        # exactly once (repeated portfolios must not duplicate branches).
        families = [
            branch.method_family for branch in state.branches.values()
        ]
        self.assertIn("brief_bootstrap", families)
        self.assertEqual(families.count("independent_check"), 1)
        # The selected synthesis claim was recorded and tested by episode 1.
        statements = {claim.statement for claim in state.claims.values()}
        self.assertIn(
            "The bounded invariant identity holds on the frozen scope.",
            statements,
        )


if __name__ == "__main__":
    unittest.main()
