"""Reversible config overlays (muse_trial, quota_relief).

Each overlay is loaded with override only while its config/<name>.enabled
marker exists, so a profile can be toggled without editing .env. The overlays
are mutually exclusive (each sets ASTRA_ARCHITECTURE_PROFILE); if two markers
ever coexist the loader refuses both and falls back to the base .env.

These tests drive the real loader against a temporary project root, so they
are independent of whatever overlay happens to be enabled on this machine.
"""
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from core import preflight


def _make_root(tmp: str, markers=()):
    root = Path(tmp)
    (root / ".env").write_text("ASTRA_BASE_SENTINEL=1\n", encoding="utf-8")
    cfg = root / "config"
    cfg.mkdir()
    (cfg / "muse_trial.env").write_text(
        "ASTRA_ARCHITECTURE_PROFILE=muse-trial\nASTRA_CONJECTURE_PROVIDER=codex_cli,agy_cli,muse_cli\n",
        encoding="utf-8",
    )
    (cfg / "quota_relief.env").write_text(
        "ASTRA_ARCHITECTURE_PROFILE=quota-relief\nASTRA_SYNTH_PROVIDER=agy_cli\n",
        encoding="utf-8",
    )
    for name in markers:
        (cfg / f"{name}.enabled").write_text("test", encoding="utf-8")
    return root


class EnabledOverlays(unittest.TestCase):
    def test_both_overlays_are_registered(self):
        self.assertEqual(set(preflight._ENV_OVERLAYS), {"muse_trial", "quota_relief"})

    def test_no_marker_loads_base_only(self):
        with TemporaryDirectory() as tmp:
            root = _make_root(tmp, markers=())
            with patch.object(preflight, "project_root", return_value=root), \
                 patch.dict(os.environ, {}, clear=False):
                os.environ.pop("ASTRA_ARCHITECTURE_PROFILE", None)
                preflight.load_project_env()
                self.assertEqual(os.environ.get("ASTRA_BASE_SENTINEL"), "1")
                self.assertNotIn("ASTRA_ARCHITECTURE_PROFILE", os.environ)

    def test_single_marker_loads_that_overlay(self):
        with TemporaryDirectory() as tmp:
            root = _make_root(tmp, markers=("quota_relief",))
            with patch.object(preflight, "project_root", return_value=root), \
                 patch.dict(os.environ, {}, clear=False):
                self.assertEqual(
                    preflight._enabled_overlays(), [root / "config" / "quota_relief.env"]
                )
                preflight.load_project_env()
                self.assertEqual(os.environ.get("ASTRA_ARCHITECTURE_PROFILE"), "quota-relief")
                self.assertEqual(os.environ.get("ASTRA_SYNTH_PROVIDER"), "agy_cli")

    def test_muse_trial_marker_loads_muse_overlay(self):
        with TemporaryDirectory() as tmp:
            root = _make_root(tmp, markers=("muse_trial",))
            with patch.object(preflight, "project_root", return_value=root), \
                 patch.dict(os.environ, {}, clear=False):
                preflight.load_project_env()
                self.assertEqual(os.environ.get("ASTRA_ARCHITECTURE_PROFILE"), "muse-trial")

    def test_two_markers_refuse_and_fall_back_to_base(self):
        # Mutual exclusivity enforced in code, independent of list order.
        with TemporaryDirectory() as tmp:
            root = _make_root(tmp, markers=("muse_trial", "quota_relief"))
            with patch.object(preflight, "project_root", return_value=root), \
                 patch.dict(os.environ, {}, clear=False):
                os.environ.pop("ASTRA_ARCHITECTURE_PROFILE", None)
                self.assertEqual(preflight._enabled_overlays(), [])
                preflight.load_project_env()
                # Base .env only: neither profile applied.
                self.assertEqual(os.environ.get("ASTRA_BASE_SENTINEL"), "1")
                self.assertNotIn("ASTRA_ARCHITECTURE_PROFILE", os.environ)


if __name__ == "__main__":
    unittest.main()
