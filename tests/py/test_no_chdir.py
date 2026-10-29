"""Nothing calls os.chdir: a lane run driven in process with os.chdir patched to raise leases, builds, reviews and
merges two tickets to DONE, and proof.test_first, given the absolute plan folder of a second repo, checks that
repo's commits. The working folder is the same after every call."""

import contextlib
import io
import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import helpers
from helpers import Repo

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import cli, proof  # the package under test, from this checkout

PYTHON = '"%s"' % sys.executable
CHECK = "```check\n$ %s -c \"print('fine')\"\nprints fine\n```\n\n" % PYTHON


def py(code):
    return '"%s" -c "%s"' % (sys.executable, code)


def no_chdir(path):
    raise AssertionError("os.chdir(%r) was called" % (path,))


def ticket(title, touches):
    return ("# %s\n\nType: task\nStatus: open\nBlocked by: —\nTest first: no\nLevel: 2\nTouches: %s\n\nbody\n\n"
            "## Done when\n\n- x\n\n%s## Answer\n" % (title, touches, CHECK))


def git(cwd, *args):
    return subprocess.run(["git"] + list(args), cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True, check=True).stdout.strip()


class LaneRun(unittest.TestCase):
    def setUp(self):
        self.repo = repo = Repo(tickets=())
        self.addCleanup(repo.close)
        for folder in ("agents", "guides"):
            shutil.copytree(str(helpers.ROOT / folder), str(repo.path(folder)))
        repo.path("plans/f/commands.md").write_text(
            "# Commands: f\n\nSetup: `%s -c \"pass\"`\nSmoke: `%s -c \"pass\"`\nTest: `%s -c \"pass\"`\n"
            % (PYTHON, PYTHON, PYTHON), encoding="utf-8")
        repo.path("plans/f/tasks/01-a.md").write_text(ticket("A", "a/"), encoding="utf-8")
        repo.path("plans/f/tasks/02-b.md").write_text(ticket("B", "b/"), encoding="utf-8")
        repo.commit("plan")
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(str(repo.dir))  # once, before the conductor runs; it must never change it again
        self.home = os.getcwd()
        self.env = dict({k: v for k, v in os.environ.items() if not k.startswith("FLOW_")},
                        FLOW_TRUSTED="1", FLOW_LANES="2", FLOW_TICKETS_PER_SESSION="99", FLOW_SCOUTS="off")
        self.reply = repo.dir.parent / (repo.dir.name + "-reply.txt")
        self.addCleanup(self.reply.unlink, missing_ok=True)

    def call(self, *args, rc=0):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(os, "chdir", no_chdir), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            got = cli.main(["f"] + list(args), scripts=self.repo.path("scripts"))
        self.assertEqual(os.getcwd(), self.home, "the working folder changed in %s" % (args,))
        self.assertEqual(got, rc, "%s: %s\n%s" % (args, out.getvalue(), err.getvalue()))
        return out.getvalue().strip()

    def lane_dir(self, lane):
        return self.repo.path(".feature-flow/lanes/f/lane-%s" % lane)

    def build(self, lane, path, folder):
        where = self.lane_dir(lane)
        (where / folder).mkdir(parents=True, exist_ok=True)
        (where / folder / "x.txt").write_text("built in lane %s\n" % lane, encoding="utf-8")
        ticket_file = where / path
        ticket_file.write_text(re.sub(r"(?m)^Status: .*$", "Status: resolved", ticket_file.read_text(encoding="utf-8"),
                                      count=1), encoding="utf-8")
        git(where, "add", "-A")
        git(where, "commit", "-qm", "feat: %s" % path)

    def test_two_lanes_build_review_and_merge_to_done(self):
        self.env["FLOW_SESSION"] = self.call("start").split()[1]
        pending, seen = [], []
        line = self.call("next")
        for _ in range(40):
            seen.append(line)
            word = line.split()[0]
            if word in ("BUILD", "REVIEW"):
                pending.append(line.split())
                line = self.call("next")
                continue
            if word != "WAIT" or not pending:
                break
            kind, path, _num, _base, lane = pending.pop(0)
            self.assertIn("Work in the folder `%s`" % self.lane_dir(lane).resolve(), self.call("prompt", lane))
            if kind == "BUILD":
                self.build(lane, path, "a" if path.endswith("01-a.md") else "b")
            else:
                self.reply.write_text("fine\nREVIEW: PASS\n", encoding="utf-8")
                self.assertEqual(self.call("verdict", str(self.reply), lane), "OK")
            line = self.call("next", lane)
        self.assertTrue(line.startswith("DONE f is complete: 2 ticket(s)"), seen + [line])
        self.assertEqual(sorted(l.split()[0] + " " + l.split()[2] for l in seen if l.split()[0] in ("BUILD", "REVIEW")),
                         ["BUILD 01", "BUILD 02", "REVIEW 01", "REVIEW 02"])
        self.assertTrue(self.repo.path("a/x.txt").is_file())
        self.assertTrue(self.repo.path("b/x.txt").is_file())
        self.assertFalse(self.repo.path(".feature-flow/lanes/f").exists())

    def test_a_lane_folder_that_is_gone_stops_before_any_helper_runs_there(self):
        self.env["FLOW_SESSION"] = self.call("start").split()[1]
        self.assertTrue(self.call("next").startswith("BUILD plans/f/tasks/01-a.md 01 "))
        git(self.repo.dir, "worktree", "remove", "--force", str(self.lane_dir(1)))
        out = self.call("next", "1", rc=1)
        self.assertEqual(out, "STOP lane 1 (%s) is gone. run reset to drop the lanes and start again"
                         % self.lane_dir(1).resolve())


class ProofElsewhere(unittest.TestCase):
    """proof works in the repo its arguments name, never by changing the working folder."""

    def setUp(self):
        self.here = Repo()
        self.addCleanup(self.here.close)
        self.there = Repo()
        self.addCleanup(self.there.close)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(str(self.here.dir))
        self.home = os.getcwd()
        self.chdir = mock.patch.object(os, "chdir", no_chdir)
        self.chdir.start()
        self.addCleanup(self.chdir.stop)

    def test_test_first_with_the_absolute_plan_folder_of_another_repo_checks_that_repo(self):
        there = self.there
        base = there.head()
        branch = there.git("symbolic-ref", "--short", "HEAD")
        there.path("tests").mkdir()
        there.path("tests/test_feature.py").write_text("x\n", encoding="utf-8")
        there.commit("test")
        red = there.head()
        there.path("feature.txt").write_text("done", encoding="utf-8")
        there.commit("code")
        cmd = py("import os, sys; sys.exit(0 if os.path.exists('feature.txt') else 1)")
        remembered = []
        ok, text = proof.test_first(base, cmd, there.path("plans/f").resolve(), 1, remembered.append)
        self.assertTrue(ok, text)
        self.assertIn(red[:10], text)
        self.assertEqual(os.getcwd(), self.home)
        self.assertEqual(remembered, [branch, ""])
        self.assertEqual(there.git("symbolic-ref", "--short", "HEAD"), branch)
        self.assertEqual(there.porcelain(), "")
        # a relative plan folder is read in the working folder, as before: this repo has no test commit
        ok, _ = proof.test_first(self.here.head(), cmd, "plans/f", 1, remembered.append)
        self.assertFalse(ok)
        self.assertEqual(os.getcwd(), self.home)

    def test_run_checks_runs_in_the_top_of_the_folder_it_is_given(self):
        self.there.path("sub").mkdir()
        self.there.path("marker.txt").write_text("x", encoding="utf-8")
        check = proof.Check(py("import os, sys; sys.exit(0 if os.path.exists('marker.txt') else 1)"))
        self.assertEqual(proof.run_checks([check], 1, cwd=str(self.there.path("sub"))), (True, ""))
        self.assertFalse(proof.run_checks([check], 1)[0])
        self.assertEqual(os.getcwd(), self.home)

    def test_repo_relative_reads_a_relative_path_under_the_folder_it_is_given(self):
        self.assertEqual(proof.repo_relative("plans/f/tasks/01-a.md", cwd=str(self.there.dir)),
                         "plans/f/tasks/01-a.md")
        self.assertEqual(proof.repo_relative(self.there.path("plans/f"), cwd=str(self.there.dir)), "plans/f")


if __name__ == "__main__":
    unittest.main()
