import unittest

from helpers import Repo

T1 = "plans/f/tasks/01-a.md"
T2 = "plans/f/tasks/02-b.md"


class BuildAndChecks(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()

    def tearDown(self):
        self.repo.close()

    def test_first_next_hands_out_the_first_ticket(self):
        sha = self.repo.head()
        rc, out = self.repo.flow("next")
        self.assertEqual((rc, out), (0, "BUILD %s 01 %s" % (T1, sha)))
        self.assertTrue(self.repo.path(".git/flow-f.state").is_file())
        self.assertIn(",01,BUILD", self.repo.log())
        self.assertEqual(self.repo.porcelain(), "")

    def test_resolved_ticket_goes_to_review_after_the_checks(self):
        sha = self.repo.head()
        self.repo.flow("next")
        self.repo.resolve(T1)
        rc, out = self.repo.flow("next")
        self.assertEqual((rc, out), (0, "REVIEW %s 01 %s" % (T1, sha)))
        self.assertEqual(self.repo.state()["review_sha"], self.repo.head())
        self.assertIn("GATE-PASS", self.repo.log())
        self.assertIn("GUARD-PASS", self.repo.log())

    def test_claimed_ticket_is_reset_and_built_again_then_stops(self):
        self.repo.flow("next")
        self.repo.set_status(T1, "claimed")
        rc, out = self.repo.flow("next")
        self.assertEqual(rc, 0)
        self.assertTrue(out.startswith("BUILD %s 01 " % T1))
        self.assertIn("Status: open", self.repo.path(T1).read_text())
        rc, out = self.repo.flow("next")
        self.assertEqual((rc, out), (1, "STOP 01-a is still unresolved after 2 attempt(s)"))

    def test_failing_gate_sends_the_ticket_back_then_stops(self):
        cmd = self.repo.path("plans/f/commands.md")
        cmd.write_text(cmd.read_text() + "Test: `test ! -e FAILING`\n")
        self.repo.path("FAILING").write_text("x\n")
        self.repo.commit("failing test")
        self.repo.flow("next")
        for round_no in (1, 2, 3):
            self.repo.resolve(T1, "feat: round %d" % round_no)
            rc, out = self.repo.flow("next")
            self.assertEqual(rc, 0)
            self.assertTrue(out.startswith("BUILD %s 01 " % T1), out)
            text = self.repo.path(T1).read_text()
            self.assertIn("## Review findings (round %d, gate)" % round_no, text)
            self.assertIn("Status: open", text)
            self.assertEqual(self.repo.git("log", "-1", "--format=%s"), "chore(f): 01 review findings, round %d" % round_no)
        self.repo.resolve(T1, "feat: round 4")
        rc, out = self.repo.flow("next")
        self.assertEqual((rc, out), (1, "STOP 01-a still fails the gate after 3 round(s)"))

    def test_resolved_ticket_with_a_dirty_tree_stops(self):
        self.repo.flow("next")
        self.repo.set_status(T1, "resolved")
        self.repo.commit("feat: 01")
        self.repo.path("stray.txt").write_text("x\n")
        rc, out = self.repo.flow("next")
        self.assertEqual((rc, out), (1, "STOP working tree is dirty after 01-a, it should have been committed"))

    def test_failing_smoke_stops_before_the_first_build(self):
        rc, out = self.repo.flow("next", FLOW_SMOKE="false")
        self.assertEqual(rc, 1)
        self.assertTrue(out.startswith("STOP smoke test failed before 01-a"), out)

    def test_usage(self):
        rc, _ = self.repo.flow("bogus")
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
