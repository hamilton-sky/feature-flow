import os
import sys
import tempfile
import unittest
from pathlib import Path

import helpers
from helpers import Repo

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import install

T1 = "plans/f/tasks/01-a.md"
KEYS = ("HOME", "CLAUDE_HOME", "AGENTS_HOME", "FEATURE_FLOW_HOME")


class HomeConductor(unittest.TestCase):
    local = False

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.flow_home = self.home / ".feature-flow"
        self.saved = dict((k, os.environ.get(k)) for k in KEYS)
        os.environ["HOME"] = str(self.home)
        os.environ["CLAUDE_HOME"] = str(self.home / ".claude")
        os.environ["AGENTS_HOME"] = str(self.home / ".agents")
        os.environ["FEATURE_FLOW_HOME"] = str(self.flow_home)
        out, err = [], []
        self.assertEqual(install.run(["--user"], helpers.ROOT, out.append, err.append), 0, err)
        self.installed = self.files()
        self.repo = Repo(local=self.local)
        if not self.local:
            self.repo.script = str(self.flow_home / "scripts" / "flow.py")

    def tearDown(self):
        self.repo.close()
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def files(self):
        return sorted(p.relative_to(self.home).as_posix() for p in self.home.rglob("*")
                      if p.is_file() and "__pycache__" not in p.parts)

    def begin(self):
        rc, out = self.repo.flow("start")
        self.assertEqual(rc, 0, out)
        self.assertTrue(out.startswith("OK "), out)
        self.token = out.split()[1]
        rc, out = self.repo.flow("next", FLOW_SESSION=self.token)
        self.assertEqual(rc, 0, out)
        self.assertTrue(out.startswith("BUILD "), out)

    def edit(self, rel):
        with open(str(self.flow_home / rel), "a", encoding="utf-8") as handle:
            handle.write("\n# edited by the builder\n")

    def finish(self):
        self.repo.resolve(T1)
        return self.repo.flow("next", FLOW_SESSION=self.token)

    def stops_after_editing(self, rel):
        self.begin()
        self.edit(rel)
        rc, out = self.finish()
        self.assertEqual(rc, 1, out)
        self.assertTrue(out.startswith("STOP flow code changed while building "), out)
        self.assertIn(str(self.flow_home / rel), out)

    def test_start_and_next_run_from_the_repo_and_write_nothing_in_the_home(self):
        self.begin()
        self.assertTrue(self.repo.path(".feature-flow/state/flow-f.state").exists())
        self.assertEqual(self.files(), self.installed)

    def test_an_edit_to_the_home_floorguard_stops_the_run(self):
        self.stops_after_editing("feature_flow/floorguard.py")

    def test_an_edit_to_the_home_flow_script_stops_the_run(self):
        self.stops_after_editing("scripts/flow.py")


class RepoInstallBesideHome(HomeConductor):
    local = True

    test_start_and_next_run_from_the_repo_and_write_nothing_in_the_home = None
    test_an_edit_to_the_home_floorguard_stops_the_run = None
    test_an_edit_to_the_home_flow_script_stops_the_run = None

    def test_edits_to_the_home_copy_do_not_affect_the_repo_run(self):
        self.begin()
        self.edit("feature_flow/floorguard.py")
        self.edit("scripts/flow.py")
        rc, out = self.finish()
        self.assertEqual(rc, 0, out)
        self.assertFalse(out.startswith("STOP"), out)


if __name__ == "__main__":
    unittest.main()
