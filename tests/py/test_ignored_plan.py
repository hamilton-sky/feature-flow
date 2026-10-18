"""A plan folder that git ignores: the conductor sends back, resets and guards the ticket without
`git add`, and the review guides read the ticket from the working copy, cut at its Answer."""

import re
import shutil
import subprocess
import sys
import unittest

from helpers import ROOT, Repo

T1 = "plans/f/tasks/01-a.md"


class IgnoredPlan(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.addCleanup(self.repo.close)
        self.repo.path(".gitignore").write_text("plans/\n", encoding="utf-8")
        self.repo.git("rm", "-rq", "--cached", "plans")
        self.repo.commit("ignore the plans")
        self.reply = self.repo.dir.parent / (self.repo.dir.name + "-reply.txt")
        self.addCleanup(self.reply.unlink, missing_ok=True)

    def start(self, **env):
        rc, out = self.repo.flow("start", **env)
        self.assertEqual(rc, 0, out)
        env["FLOW_SESSION"] = out.split()[1]
        return env

    def build(self, env):
        rc, out = self.repo.flow("next", **env)
        self.assertTrue(out.startswith("BUILD %s " % T1), out)
        self.repo.resolve(T1)
        return self.repo.flow("next", **env)

    def fail_review(self, env):
        rc, out = self.build(env)
        self.assertTrue(out.startswith("REVIEW %s " % T1), out)
        self.reply.write_text("1. major x.py: wrong\nREVIEW: FAIL\n", encoding="utf-8")
        self.assertEqual(self.repo.flow("verdict", str(self.reply), **env), (0, "OK"))
        return self.repo.flow("next", **env)

    def test_the_plan_is_not_tracked(self):
        self.assertEqual(self.repo.git("ls-files", "plans"), "")

    def test_a_failed_review_goes_back_without_git_add(self):
        env = self.start()
        rc, out = self.fail_review(env)
        self.assertEqual(rc, 0, out)
        self.assertTrue(out.startswith("BUILD %s " % T1), out)
        text = self.repo.path(T1).read_text(encoding="utf-8")
        self.assertIn("## Review findings (round 1, spec review)", text)
        self.assertIn("Status: open", text)
        self.assertNotIn("review findings", self.repo.git("log", "--format=%s"))

    def test_track_plan_yes_commits_the_findings_anyway(self):
        env = self.start(FLOW_TRACK_PLAN="yes")
        rc, out = self.fail_review(env)
        self.assertTrue(out.startswith("BUILD %s " % T1), out)
        self.assertIn("f): 01 review findings, round 1", self.repo.git("log", "-1", "--format=%s"))
        self.assertEqual(self.repo.git("ls-files", "plans"), T1)

    def test_a_bad_track_plan_value_stops(self):
        rc, out = self.repo.flow("start", FLOW_TRACK_PLAN="sometimes")
        self.assertEqual(rc, 1)
        self.assertIn("FLOW_TRACK_PLAN must be auto or yes", out)

    def test_a_builder_that_edits_its_untracked_ticket_is_sent_back(self):
        env = self.start()
        rc, out = self.repo.flow("next", **env)
        self.assertTrue(out.startswith("BUILD"), out)
        path = self.repo.path(T1)
        path.write_text(path.read_text(encoding="utf-8").replace("- x", "- nothing to prove"), encoding="utf-8")
        self.repo.resolve(T1)
        rc, out = self.repo.flow("next", **env)
        self.assertTrue(out.startswith("BUILD %s " % T1), out)
        self.assertIn("ticket-edit: %s: text outside the Status line" % T1, path.read_text(encoding="utf-8"))
        self.assertIn("GUARD-FAIL", self.repo.log())

    def test_the_copy_from_before_the_work_is_kept_and_checked(self):
        """The conductor keeps the untracked ticket as it was at the pick, and stops if that copy changes."""
        env = self.start(FLOW_TICKETS_PER_SESSION="9")
        self.repo.flow("next", **env)
        copy = self.repo.path(".feature-flow/state/flow-f.ticket")
        self.assertTrue(copy.is_file())
        self.assertNotIn("```check", copy.read_text(encoding="utf-8"))
        self.assertTrue(self.repo.state()["ticket_copy"])
        copy.write_text("tampered\n", encoding="utf-8")
        self.repo.resolve(T1)
        rc, out = self.repo.flow("next", **env)
        self.assertEqual(rc, 1)
        self.assertIn("copy of 01-a", out)

    def test_reset_reopens_an_untracked_ticket_without_a_commit(self):
        self.repo.set_status(T1, "claimed")
        before = self.repo.head()
        rc, out = self.repo.flow("reset")
        self.assertEqual(rc, 0, out)
        self.assertIn("reopened 01-a", out)
        self.assertIn("Status: open", self.repo.path(T1).read_text(encoding="utf-8"))
        self.assertEqual(self.repo.head(), before)

    @unittest.skipIf(sys.platform == "win32" or shutil.which("bash") is None, "the guide's snippet is bash")
    def test_the_review_guides_read_an_untracked_ticket_without_its_answer(self):
        path = self.repo.path(T1)
        path.write_text(path.read_text(encoding="utf-8") + "the author's claim\n", encoding="utf-8")
        for name in ("review.md", "review-quality.md", "review-single.md"):
            guide = (ROOT / "guides" / name).read_text(encoding="utf-8")
            block = re.search(r"```\n(TICKET=.*?)```", guide, re.S).group(1)
            block = block.replace("<feature>", "f").replace("<NN>", "01").replace("<base>", self.repo.head())
            out = subprocess.run(["bash", "-c", block], cwd=str(self.repo.dir), stdout=subprocess.PIPE,
                                 universal_newlines=True).stdout
            self.assertIn("## Done when", out, name)
            self.assertNotIn("the author's claim", out, name)
            self.assertTrue(out.rstrip().endswith("## Answer"), name)


if __name__ == "__main__":
    unittest.main()
