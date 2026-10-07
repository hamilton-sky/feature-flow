"""`flow.py <feature> reset [NN]`, `feature-flow reset`, and the did-you-mean hints on a typo."""

import io
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout

from helpers import ROOT, Repo

sys.path.insert(0, str(ROOT))
from feature_flow import cli, command  # noqa: E402

T1 = "plans/f/tasks/01-a.md"
T2 = "plans/f/tasks/02-b.md"


class Reset(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()

    def tearDown(self):
        self.repo.close()

    def test_reset_clears_the_run_and_reopens_a_claimed_ticket(self):
        rc, out = self.repo.flow("start")
        token = out.split()[1]
        self.repo.flow("next", FLOW_SESSION=token)
        self.repo.set_status(T1, "claimed")
        self.repo.commit("claim 01")
        rc, out = self.repo.flow("reset", FLOW_TAKEOVER="1")
        self.assertEqual(rc, 0, out)
        self.assertIn("reopened 01-a", out)
        self.assertIn("Status: open", self.repo.path(T1).read_text(encoding="utf-8"))
        self.assertFalse(self.repo.path(".feature-flow/state/flow-f.state").exists())
        self.assertEqual(self.repo.porcelain(), "")
        self.assertEqual(self.repo.git("log", "-1", "--format=%s"), "chore(f): reset 01 to open")
        rc, out = self.repo.flow("start")
        self.assertEqual(rc, 0)
        rc, out = self.repo.flow("next", FLOW_SESSION=out.split()[1])
        self.assertEqual((rc, out), (0, "BUILD %s 01 %s" % (T1, self.repo.head())))

    def test_reset_of_a_named_ticket_reopens_it_even_when_resolved(self):
        self.repo.resolve(T1)
        rc, out = self.repo.flow("reset", "01")
        self.assertEqual(rc, 0, out)
        self.assertIn("Status: open", self.repo.path(T1).read_text(encoding="utf-8"))
        self.assertEqual(self.repo.porcelain(), "")

    def test_reset_while_a_session_owns_the_feature_needs_takeover(self):
        self.repo.flow("start")
        rc, out = self.repo.flow("reset")
        self.assertEqual(rc, 1)
        self.assertIn("FLOW_TAKEOVER=1", out)
        self.assertTrue(self.repo.path(".feature-flow/state/flow-f.state").exists())

    def test_reset_of_an_unknown_ticket_changes_nothing(self):
        self.repo.flow("start")
        rc, out = self.repo.flow("reset", "07", FLOW_TAKEOVER="1")
        self.assertEqual(rc, 1)
        self.assertIn("no ticket 07", out)
        self.assertTrue(self.repo.path(".feature-flow/state/flow-f.state").exists())

    def test_reset_commits_only_the_ticket(self):
        self.repo.set_status(T1, "claimed")
        self.repo.commit("claim")
        self.repo.path("mine.txt").write_text("x\n", encoding="utf-8")
        self.repo.git("add", "mine.txt")
        rc, out = self.repo.flow("reset")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.repo.porcelain(), "A  mine.txt")

    def test_reset_with_nothing_to_do_says_so(self):
        rc, out = self.repo.flow("reset")
        self.assertEqual((rc, out), (0, "OK nothing to reset for f. run /feature-flow f"))


class Typos(unittest.TestCase):
    def run_cli(self, fn, args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = fn(args)
        return rc, out.getvalue(), err.getvalue()

    def test_flow_suggests_the_closest_command(self):
        rc, _, err = self.run_cli(cli.main, ["f", "nxet"])
        self.assertEqual(rc, 2)
        self.assertIn("did you mean: next?", err)

    def test_flow_spots_the_feature_and_command_swapped(self):
        rc, _, err = self.run_cli(cli.main, ["next", "f"])
        self.assertEqual(rc, 2)
        self.assertIn("did you mean: flow.py f next?", err)

    def test_feature_flow_suggests_the_closest_command(self):
        rc, _, err = self.run_cli(command.main, ["stauts", "f"])
        self.assertEqual(rc, 2)
        self.assertIn("did you mean: status?", err)

    def run_module(self, repo, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith("FLOW_")}
        env["PYTHONPATH"] = str(ROOT)
        return subprocess.run([sys.executable, "-m", "feature_flow"] + list(args), cwd=str(repo.dir),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, env=env)

    def test_status_suggests_the_closest_feature(self):
        repo = Repo()
        try:
            result = self.run_module(repo, "status", "ff")
        finally:
            repo.close()
        self.assertEqual(result.returncode, 2)
        self.assertIn("no ticket folder: plans/ff/tasks", result.stderr)
        self.assertIn("did you mean: f?", result.stderr)

    def test_feature_flow_reset_runs_in_the_current_repo(self):
        repo = Repo()
        try:
            repo.set_status(T1, "in-progress")
            repo.commit("claim")
            result = self.run_module(repo, "reset", "f")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("reopened 01-a", result.stdout)
        finally:
            repo.close()


if __name__ == "__main__":
    unittest.main()
