"""The helpers outside the conductor package take an optional cwd= keyword: given, they act on that
folder (its commits, its plan, its commands.md) and leave the process working folder alone; left out,
they act on the working folder as before."""

import os
import sys
import unittest
from unittest import mock

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import checks, git  # the package under test, from this checkout

THREE = (("01-a", "A", "—"), ("02-b", "B", "01"), ("03-c", "C", "02"))


def py(code):
    return '"%s" -c "%s"' % (sys.executable, code)


def commands(test):
    return "# Commands: f\n\nTest: `%s`\n" % test


class Cwd(unittest.TestCase):
    """here is the working folder (two tickets), there the other repo (three tickets)."""

    def setUp(self):
        self.here = helpers.Repo(local=False)
        self.there = helpers.Repo(tickets=THREE, local=False)
        write = "open('ran.txt', 'w').write('%s')"
        self.here.path("plans/f/commands.md").write_text(commands(py(write % "here")), encoding="utf-8")
        self.there.path("plans/f/commands.md").write_text(commands(py(write % "there")), encoding="utf-8")
        self.here.commit("here")
        self.there.commit("there")
        env = {k: v for k, v in os.environ.items() if not k.startswith("FLOW_")}
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.old = os.getcwd()
        os.chdir(str(self.here.dir))
        self.addCleanup(self.here.close)
        self.addCleanup(self.there.close)
        self.addCleanup(os.chdir, self.old)
        self.start = os.getcwd()

    def same_folder(self):
        self.assertEqual(os.getcwd(), self.start)

    def test_git_helpers(self):
        there = str(self.there.dir)
        self.assertEqual(git.head(cwd=there), self.there.head())
        self.assertEqual(git.head(), self.here.head())
        self.assertEqual(os.path.realpath(str(git.toplevel(cwd=there))), os.path.realpath(there))
        self.assertIn("# C\n", git.show_text("HEAD:plans/f/tasks/03-c.md", cwd=there))
        with self.assertRaises(RuntimeError):
            git.show_text("HEAD:plans/f/tasks/03-c.md")
        self.there.path("only-there.txt").write_text("x\n", encoding="utf-8")
        self.assertEqual(git.changes(cwd=there), ["only-there.txt"])
        self.assertFalse(git.is_clean(cwd=there))
        self.assertTrue(git.is_clean())
        self.assertEqual(git.diff_names("HEAD~1", "HEAD", "nothing", cwd=there), ["plans/f/commands.md"])
        self.same_folder()

    def test_gate(self):
        there = str(self.there.dir)
        result = checks.gate("scripts", "f", 1, cwd=there)
        self.assertTrue(result.ok, result.out)
        self.assertEqual(self.there.path("ran.txt").read_text(encoding="utf-8"), "there")
        self.assertFalse(self.here.path("ran.txt").exists())
        self.same_folder()
        result = checks.gate("scripts", "f", 1)
        self.assertTrue(result.ok, result.out)
        self.assertEqual(self.here.path("ran.txt").read_text(encoding="utf-8"), "here")

    def test_floor_guard(self):
        there = str(self.there.dir)
        base = self.there.head()
        self.there.path("plans/f/tasks/02-b.md").write_text("changed\n", encoding="utf-8")
        self.there.commit("edit another ticket")
        result = checks.floor_guard("scripts", "f", "03", base, cwd=there)
        self.assertEqual(result.code, 1, result.out)
        self.assertIn("ticket-edit: plans/f/tasks/02-b.md", result.out)
        self.same_folder()
        result = checks.floor_guard("scripts", "f", "03", base)
        self.assertEqual(result.code, 2, result.out)
        self.assertIn("no ticket 03 in plans/f/tasks", result.out)
        result = checks.floor_guard("scripts", "f", "02", self.here.head())
        self.assertEqual((result.code, result.out), (0, "floor guard: clean\n"))

    def test_flow_status(self):
        there = str(self.there.dir)
        result = checks.flow_status("scripts", "f", "--counts", cwd=there)
        self.assertIn("total=3 ", result.out)
        result = checks.flow_status("scripts", "f", "--next", cwd=there)
        self.assertEqual((result.code, result.out), (0, "plans/f/tasks/01-a.md\n"))
        result = checks.flow_status("scripts", "f", "--check", cwd=there)
        self.assertEqual(result.code, 0, result.out)
        self.assertIn("OK: 3 tickets", result.out)
        self.same_folder()
        result = checks.flow_status("scripts", "f", "--counts")
        self.assertIn("total=2 ", result.out)

    def test_smoke(self):
        there = str(self.there.dir)
        result = checks.smoke(py("import os; print(os.getcwd())"), 1, cwd=there)
        self.assertTrue(result.ok, result.out)
        self.assertEqual(os.path.realpath(result.out.strip()), os.path.realpath(there))
        self.same_folder()
        result = checks.smoke(py("import os; print(os.getcwd())"), 1)
        self.assertEqual(os.path.realpath(result.out.strip()), os.path.realpath(self.start))


if __name__ == "__main__":
    unittest.main()
