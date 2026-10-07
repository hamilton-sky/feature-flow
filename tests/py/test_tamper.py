import shutil
import subprocess
import sys
import unittest

import helpers
from helpers import Repo

T1 = "plans/f/tasks/01-a.md"
EDITS = ("feature_flow/floorguard.py", "scripts/flow.py")


class Tamper:
    """The builder edits the code the conductor loads; the conductor must notice."""

    prefix = ""      # where the package lives, relative to the repo
    allow = False    # the ticket carries `Floor: allow flow-edit`

    def setUp(self):
        self.repo = Repo()
        self.layout()
        if self.allow:
            path = self.repo.path(T1)
            text = path.read_text(encoding="utf-8")
            path.write_text(text.replace("Type: task\n", "Type: task\nFloor: allow flow-edit\n", 1), encoding="utf-8")
        self.repo.git("add", "-A")
        self.repo.git("commit", "-q", "--allow-empty", "-m", "layout")

    def tearDown(self):
        self.repo.close()

    def layout(self):
        pass

    def edited(self):
        return (self.prefix + "feature_flow/floorguard.py", "scripts/flow.py")

    def begin(self):
        rc, out = self.repo.flow("start")
        self.assertEqual(rc, 0, out)
        self.token = out.split()[1]
        rc, out = self.repo.flow("next", FLOW_SESSION=self.token)
        self.assertEqual(rc, 0, out)
        self.assertTrue(out.startswith("BUILD "), out)

    def edit(self):
        for rel in self.edited():
            with open(str(self.repo.path(rel)), "a", encoding="utf-8") as handle:
                handle.write("\n# edited by the builder\n")

    def finish(self):
        self.repo.resolve(T1)
        return self.repo.flow("next", FLOW_SESSION=self.token)

    def test_an_edit_during_the_build_stops_the_run(self):
        self.begin()
        self.edit()
        rc, out = self.finish()
        self.assertEqual(rc, 1, out)
        self.assertTrue(out.startswith("STOP flow code changed while building "), out)
        for rel in self.edited():
            self.assertIn(rel, out)


class SourceCheckout(Tamper, unittest.TestCase):
    pass


class InstallTamper(Tamper):
    prefix = ".feature-flow/"
    private = False

    def layout(self):
        shutil.rmtree(str(self.repo.path("feature_flow")))
        shutil.rmtree(str(self.repo.path("scripts")))
        self.repo.commit("remove the source copy")
        args = [sys.executable, str(helpers.ROOT / "install.py"), str(self.repo.dir)]
        subprocess.run(args + (["--private"] if self.private else []), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, check=True)


class CommittedInstall(InstallTamper, unittest.TestCase):
    pass


class PrivateInstall(InstallTamper, unittest.TestCase):
    private = True


class FlowEditAllowed(Tamper, unittest.TestCase):
    allow = True

    def test_an_edit_during_the_build_stops_the_run(self):
        self.begin()
        self.edit()
        rc, out = self.finish()
        self.assertEqual((rc, out.split()[0]), (0, "REVIEW"), out)


class EditBeforeStart(Tamper, unittest.TestCase):
    def test_an_edit_during_the_build_stops_the_run(self):
        self.edit()
        self.repo.commit("edit before the run")
        self.begin()
        rc, out = self.finish()
        self.assertEqual((rc, out.split()[0]), (0, "REVIEW"), out)


if __name__ == "__main__":
    unittest.main()
