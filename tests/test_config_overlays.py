"""Reversible config overlays (quota_relief, strict_translator).

Each overlay is loaded with override only while its config/<name>.enabled
marker exists, so a profile can be toggled without editing .env. Two kinds:

  * PROFILE overlays (quota_relief) each set ASTRA_ARCHITECTURE_PROFILE and
    are mutually exclusive; if two markers ever coexist the loader refuses
    BOTH and falls back to the base .env profile.
  * COMPOSABLE overlays (strict_translator) touch an orthogonal knob and may
    coexist with one profile overlay -- and must still load when the profile
    overlays conflict.

quota_relief is the only profile overlay shipped today, so the exclusivity
tests register a second, test-only profile overlay (``alt_profile``) to keep
that rule covered for the next one that is added.

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
    (cfg / "alt_profile.env").write_text(
        "ASTRA_ARCHITECTURE_PROFILE=full\nASTRA_CONJECTURE_PROVIDER=codex_cli,agy_cli\n",
        encoding="utf-8",
    )
    (cfg / "quota_relief.env").write_text(
        "ASTRA_ARCHITECTURE_PROFILE=quota-relief\nASTRA_SYNTH_PROVIDER=agy_cli\n",
        encoding="utf-8",
    )
    (cfg / "strict_translator.env").write_text(
        "ASTRA_TRANSLATOR_STRICT_CONTRACT=1\n", encoding="utf-8",
    )
    for name in markers:
        (cfg / f"{name}.enabled").write_text("test", encoding="utf-8")
    return root


_KEYS = ("ASTRA_ARCHITECTURE_PROFILE", "ASTRA_TRANSLATOR_STRICT_CONTRACT",
         "ASTRA_SYNTH_PROVIDER", "ASTRA_CONJECTURE_PROVIDER")
_TWO_PROFILES = ("alt_profile", "quota_relief")


class _OverlayCase(unittest.TestCase):
    def _load(self, markers, profiles=None):
        profiles = preflight._PROFILE_OVERLAYS if profiles is None else profiles
        with TemporaryDirectory() as tmp:
            root = _make_root(tmp, markers=markers)
            with patch.object(preflight, "project_root", return_value=root), \
                 patch.object(preflight, "_PROFILE_OVERLAYS", profiles), \
                 patch.object(preflight, "_ENV_OVERLAYS",
                              profiles + preflight._COMPOSABLE_OVERLAYS), \
                 patch.dict(os.environ, {}, clear=False):
                for k in _KEYS:
                    os.environ.pop(k, None)
                preflight.load_project_env()
                return {k: os.environ.get(k) for k in _KEYS}


class Registry(unittest.TestCase):
    def test_overlays_are_registered_by_kind(self):
        self.assertEqual(set(preflight._PROFILE_OVERLAYS), {"quota_relief"})
        self.assertEqual(set(preflight._COMPOSABLE_OVERLAYS), {"strict_translator"})
        self.assertEqual(set(preflight._ENV_OVERLAYS),
                         {"quota_relief", "strict_translator"})


class ProfileOverlays(_OverlayCase):
    def test_no_marker_loads_base_only(self):
        env = self._load(())
        self.assertIsNone(env["ASTRA_ARCHITECTURE_PROFILE"])
        self.assertIsNone(env["ASTRA_TRANSLATOR_STRICT_CONTRACT"])

    def test_single_profile_marker_loads_that_overlay(self):
        env = self._load(("quota_relief",))
        self.assertEqual(env["ASTRA_ARCHITECTURE_PROFILE"], "quota-relief")
        self.assertEqual(env["ASTRA_SYNTH_PROVIDER"], "agy_cli")

    def test_unregistered_marker_is_ignored(self):
        # alt_profile.env exists on disk but is not a shipped overlay.
        self.assertIsNone(self._load(("alt_profile",))["ASTRA_ARCHITECTURE_PROFILE"])

    def test_two_profile_markers_refuse_and_fall_back_to_base(self):
        env = self._load(("alt_profile", "quota_relief"), profiles=_TWO_PROFILES)
        self.assertIsNone(env["ASTRA_ARCHITECTURE_PROFILE"])


class ComposableOverlay(_OverlayCase):
    def test_strict_translator_alone_sets_flag_only(self):
        env = self._load(("strict_translator",))
        self.assertEqual(env["ASTRA_TRANSLATOR_STRICT_CONTRACT"], "1")
        self.assertIsNone(env["ASTRA_ARCHITECTURE_PROFILE"])

    def test_strict_translator_composes_with_a_profile_overlay(self):
        # The regression this design prevents: enabling the strict contract
        # while a profile overlay is active must NOT disable that profile.
        env = self._load(("quota_relief", "strict_translator"))
        self.assertEqual(env["ASTRA_ARCHITECTURE_PROFILE"], "quota-relief")
        self.assertEqual(env["ASTRA_TRANSLATOR_STRICT_CONTRACT"], "1")

    def test_profile_conflict_still_loads_composable(self):
        env = self._load(("alt_profile", "quota_relief", "strict_translator"),
                         profiles=_TWO_PROFILES)
        self.assertIsNone(env["ASTRA_ARCHITECTURE_PROFILE"])     # profiles refused
        self.assertEqual(env["ASTRA_TRANSLATOR_STRICT_CONTRACT"], "1")  # composable kept


if __name__ == "__main__":
    unittest.main()
