"""`resume [NN] [--from <commit>]`: carry on after an upgrade, a flow code change or a reset without losing where the
ticket started, and the stops and reset lines that point to it."""

import os
import subprocess
import sys
import unittest

import helpers
import test_proof
from test_proof import T1

sys.path.insert(0, str(helpers.ROOT))


class Resume(unittest.TestCase):
    setUp = test_proof.TestFirst.setUp
    tearDown = test_proof.TestFirst.tearDown
    prepare = test_proof.TestFirst.prepare
    write = test_proof.TestFirst.write
    resolve_with = test_proof.TestFirst.resolve_with
    findings = test_proof.TestFirst.findings

    def failing_test(self):
        self.write("tests/t.txt", "test(f): 01 failing test")
        return self.repo.head()

    def test_a_reset_after_the_failing_test_then_resume_keeps_the_start(self):
        self.prepare()
        base = self.repo.state()["base"]
        self.failing_test()
        rc, out = self.repo.flow("reset", "01")
        self.assertEqual(rc, 0, out)
        self.assertIn("01 had 1 commit(s) since it started at %s" % base[:10], out)
        self.assertIn("feature-flow resume f 01", out)
        rc, out = self.repo.flow("resume")
        self.assertEqual(rc, 0, out)
        self.assertIn("ticket 01 starts again when it is picked from %s (where it was before the reset)" % base[:10], out)
        self.assertIn("test(f): 01 failing test", out)
        rc, out = self.repo.flow("next")
        self.assertEqual((rc, out), (0, "BUILD %s 01 %s" % (T1, base)))
        self.assertIn("RESUMED-START", self.repo.log())
        self.resolve_with("code.txt")
        rc, out = self.repo.flow("next")
        self.assertTrue(out.startswith("REVIEW %s 01 " % T1), out)
        self.assertIn("TESTFIRST-PASS", self.repo.log())

    def test_a_start_moved_past_the_failing_test_stops_and_resume_puts_it_back(self):
        self.prepare()
        test = self.failing_test()
        state = self.repo.path(".feature-flow/state/flow-f.state")
        state.unlink()  # an old reset: it forgot where the ticket started
        rc, out = self.repo.flow("next")
        self.assertEqual((rc, out), (0, "BUILD %s 01 %s" % (T1, test)))
        self.resolve_with("code.txt")
        rc, out = self.repo.flow("next")
        self.assertEqual(rc, 1, out)
        self.assertIn("failing test commit %s is before where this build started" % test[:10], out)
        self.assertIn("feature-flow resume f 01", out)
        rc, out = self.repo.flow("resume")
        self.assertEqual(rc, 0, out)
        parent = self.repo.git("rev-parse", test + "^")
        self.assertIn("ticket 01 carries on from %s (just before its failing test commit %s)" % (parent[:10], test[:10]), out)
        rc, out = self.repo.flow("next")
        self.assertTrue(out.startswith("REVIEW %s 01 " % T1), out)
        self.assertIn("TESTFIRST-PASS", self.repo.log())

    def test_resume_still_runs_the_test_first_check(self):
        self.prepare()
        self.write("code.txt", "code first")  # the test commit after it passes: not a failing test
        self.write("tests/t.txt", "test(f): 01 failing test")
        self.resolve_with("work.txt")
        rc, out = self.repo.flow("resume")
        self.assertEqual(rc, 0, out)
        rc, out = self.repo.flow("next")
        self.assertTrue(out.startswith("BUILD %s 01 " % T1), out)
        self.assertIn("## Review findings (round 1, test first)", self.findings())

    def test_a_flow_code_change_stops_with_resume_and_resume_accepts_it(self):
        self.prepare()
        self.failing_test()
        flow = self.repo.path("feature_flow/__init__.py")
        flow.write_text(flow.read_text(encoding="utf-8") + "\n# upgraded\n", encoding="utf-8")
        self.resolve_with("code.txt")
        self.repo.git("update-index", "--assume-unchanged", "feature_flow/__init__.py")  # an upgrade outside git
        rc, out = self.repo.flow("next")
        self.assertEqual(rc, 1, out)
        self.assertIn("flow code changed while building", out)
        self.assertIn("feature-flow resume f", out)
        rc, out = self.repo.flow("resume")
        self.assertEqual(rc, 0, out)
        self.assertIn("accepted the flow code as it is now (changed: feature_flow/__init__.py)", out)
        rc, out = self.repo.flow("next")
        self.assertTrue(out.startswith("REVIEW %s 01 " % T1), out)

    def test_from_names_the_start(self):
        self.prepare()
        first = self.repo.head()
        self.write("other.txt", "unrelated")
        rc, out = self.repo.flow("resume", "01", "--from", first[:12])
        self.assertEqual(rc, 0, out)
        self.assertIn("from %s (the commit you named)" % first[:10], out)
        self.assertEqual(self.repo.state()["base"], first)

    def test_from_must_be_an_ancestor(self):
        self.prepare()
        rc, out = self.repo.flow("resume", "01", "--from", "nope")
        self.assertEqual(rc, 1, out)
        self.assertIn("--from nope names no commit", out)

    def test_nothing_says_where_it_started(self):
        rc, out = self.repo.flow("resume", "01")
        self.assertEqual(rc, 1, out)
        self.assertIn("cannot tell where ticket 01 started", out)
        self.assertIn("--from <commit>", out)

    def test_no_ticket_in_progress_asks_which(self):
        rc, out = self.repo.flow("resume")
        self.assertEqual(rc, 1, out)
        self.assertIn("say which one: `feature-flow resume f NN`", out)

    def test_a_dirty_tree_stops_first(self):
        self.prepare()
        self.repo.path("loose.txt").write_text("x\n", encoding="utf-8")
        rc, out = self.repo.flow("resume")
        self.assertEqual(rc, 1, out)
        self.assertIn("commit or stash first: loose.txt", out)

    def test_feature_flow_resume_runs_in_the_current_repo(self):
        self.prepare()
        env = {k: v for k, v in os.environ.items() if not k.startswith("FLOW_")}
        env["PYTHONPATH"] = str(helpers.ROOT)
        result = subprocess.run([sys.executable, "-m", "feature_flow", "resume", "f"], cwd=str(self.repo.dir),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ticket 01 carries on", result.stdout)


if __name__ == "__main__":
    unittest.main()
