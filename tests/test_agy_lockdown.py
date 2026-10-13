"""agy runs in default mode only from a home whose settings deny every tool."""
from __future__ import annotations

import json
import os
import tempfile
import unittest

from core.cli_backend import AGY_TEXT_ONLY_DENY, _agy_locked_down, _without_plan_mode


def _home(settings):
    home = tempfile.mkdtemp()
    if settings is not None:
        path = os.path.join(home, ".gemini", "antigravity-cli")
        os.makedirs(path)
        with open(os.path.join(path, "settings.json"), "w", encoding="utf-8") as fh:
            fh.write(settings if isinstance(settings, str) else json.dumps(settings))
    return {"USERPROFILE": home, "HOME": home}


class AgyLockdownTests(unittest.TestCase):
    def test_full_deny_list_unlocks_default_mode(self):
        env = _home({"permissions": {"deny": list(AGY_TEXT_ONLY_DENY)}})
        self.assertTrue(_agy_locked_down(env))

    def test_missing_rule_keeps_plan_mode(self):
        rules = [r for r in AGY_TEXT_ONLY_DENY if r != "write_file(*)"]
        self.assertFalse(_agy_locked_down(_home({"permissions": {"deny": rules}})))

    def test_no_settings_or_broken_settings_keep_plan_mode(self):
        self.assertFalse(_agy_locked_down(_home(None)))
        self.assertFalse(_agy_locked_down(_home("{not json")))
        self.assertFalse(_agy_locked_down({}))

    def test_without_plan_mode_removes_only_that_pair(self):
        argv = ["agy", "--print", "p", "--mode", "plan", "--effort", "high"]
        self.assertEqual(_without_plan_mode(argv), ["agy", "--print", "p", "--effort", "high"])
        self.assertEqual(_without_plan_mode(["agy", "--print", "p"]), ["agy", "--print", "p"])


if __name__ == "__main__":
    unittest.main()
