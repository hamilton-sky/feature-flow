"""A module planted in scripts/ or the repo root must not replace one the conductor imports."""

import os
import re
import shutil
import subprocess
import sys
import unittest

import helpers

OK_TOKEN = re.compile(r"^OK [0-9a-f]{16}$")


class ShadowTests(unittest.TestCase):
    def setUp(self):
        self.repo = helpers.Repo()
        shutil.copy(helpers.ROOT / "scripts" / "flow-status.py", self.repo.path("scripts"))

    def tearDown(self):
        self.repo.close()

    def plant(self, rel, text):
        self.repo.path(rel).write_text(text, encoding="utf-8")

    def run_script(self, *args, isolated=False):
        env = dict(os.environ)
        for key in list(env):
            if key.startswith("FLOW_"):
                del env[key]
        cmd = [sys.executable] + (["-I"] if isolated else []) + list(args)
        result = subprocess.run(cmd, cwd=str(self.repo.dir), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, universal_newlines=True, env=env)
        return result.returncode, result.stdout.strip(), result.stderr.strip()

    def start(self, isolated=False):
        return self.run_script("scripts/flow.py", "f", "start", isolated=isolated)

    def check(self, isolated=False):
        return self.run_script("scripts/flow-status.py", "f", "--check", isolated=isolated)

    def assert_start_ok(self, isolated=False):
        code, out, err = self.start(isolated=isolated)
        self.assertEqual(code, 0, err)
        self.assertRegex(out, OK_TOKEN)

    def test_planted_secrets_in_scripts_is_not_imported(self):
        self.plant("scripts/secrets.py", "def token_hex(n):\n    return 'planted'\n")
        self.assert_start_ok()

    def test_planted_secrets_in_repo_root_is_not_imported(self):
        self.plant("secrets.py", "def token_hex(n):\n    return 'planted'\n")
        self.assert_start_ok()

    def test_planted_json_in_scripts_leaves_check_unchanged(self):
        normal = self.check()
        self.assertEqual(normal[0], 0, normal)
        self.plant("scripts/json.py", "raise ImportError('planted json')\n")
        self.assertEqual(self.check(), normal)

    def test_planted_re_in_scripts_changes_nothing(self):
        normal = self.check()
        self.plant("scripts/re.py", "raise ImportError('planted re')\n")
        self.assert_start_ok()
        self.assertEqual(self.check(), normal)

    def test_scripts_work_under_isolated_mode(self):
        self.assert_start_ok(isolated=True)
        self.assertEqual(self.check(isolated=True), self.check())


if __name__ == "__main__":
    unittest.main()
