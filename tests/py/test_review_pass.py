import shutil
import unittest

from helpers import ROOT, Repo

T1 = "plans/f/tasks/01-a.md"
T2 = "plans/f/tasks/02-b.md"


class ReviewPasses(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        for folder in ("agents", "guides"):
            shutil.copytree(str(ROOT / folder), str(self.repo.path(folder)))
        self.repo.commit("prompts")
        self.base = self.repo.head()
        self.repo.flow("next")
        self.repo.resolve(T1)
        self.review = "REVIEW %s 01 %s" % (T1, self.base)

    def tearDown(self):
        self.repo.close()

    def reply(self, text, **env):
        path = self.repo.dir.parent / (self.repo.dir.name + "-reply.txt")
        path.write_text(text, encoding="utf-8")
        self.addCleanup(path.unlink, missing_ok=True)
        return self.repo.flow("verdict", str(path), **env)

    def passed(self):
        self.assertEqual(self.reply("fine\nREVIEW: PASS\n"), (0, "OK"))

    def to_quality(self):
        self.assertEqual(self.repo.flow("next"), (0, self.review))
        self.passed()
        self.assertEqual(self.repo.flow("next"), (0, self.review))

    def test_review_pass_one_pass_hands_out_the_quality_review_of_the_same_ticket(self):
        self.assertEqual(self.repo.flow("next"), (0, self.review))
        self.assertEqual(self.repo.state().get("review_pass", "spec"), "spec")
        spec = self.repo.flow("prompt")[1]
        self.assertIn("Verdict 1: does it meet the ticket?", spec)
        self.assertIn("(spec pass)", spec)
        self.passed()
        self.assertEqual(self.repo.flow("next"), (0, self.review))
        self.assertEqual(self.repo.state()["review_pass"], "quality")
        quality = self.repo.flow("prompt")[1]
        self.assertIn("Verdict 2: is it good?", quality)
        self.assertNotIn("Verdict 1", quality)
        self.assertIn("(quality pass)", quality)
        self.assertNotEqual(spec, quality)

    def test_review_pass_second_pass_picks_the_next_ticket(self):
        self.to_quality()
        self.passed()
        rc, out = self.repo.flow("next")
        self.assertEqual(rc, 0)
        self.assertTrue(out.startswith("BUILD %s 02 " % T2), out)
        self.assertEqual(self.repo.state()["review_pass"], "spec")

    def test_review_pass_a_fail_in_the_spec_pass_builds_the_same_ticket_again(self):
        self.repo.flow("next")
        self.assertEqual(self.reply("not met\nREVIEW: FAIL\n"), (0, "OK"))
        rc, out = self.repo.flow("next")
        self.assertEqual(rc, 0)
        self.assertTrue(out.startswith("BUILD %s 01 " % T1), out)
        self.assertIn("## Review findings (round 1, spec review)", self.repo.path(T1).read_text(encoding="utf-8"))

    def test_review_pass_a_fail_in_the_quality_pass_builds_the_same_ticket_again(self):
        self.to_quality()
        self.assertEqual(self.reply("1. major x.py: bad\nREVIEW: FAIL\n"), (0, "OK"))
        rc, out = self.repo.flow("next")
        self.assertEqual(rc, 0)
        self.assertTrue(out.startswith("BUILD %s 01 " % T1), out)
        self.assertIn("## Review findings (round 1, quality review)", self.repo.path(T1).read_text(encoding="utf-8"))
        self.assertEqual(self.repo.state()["review_pass"], "spec")

    def test_review_pass_after_a_send_back_the_review_starts_with_the_spec_pass(self):
        self.to_quality()
        self.assertEqual(self.reply("1. major x.py: bad\nREVIEW: FAIL\n"), (0, "OK"))
        self.repo.flow("next")
        self.repo.resolve(T1, "feat: again")
        rc, out = self.repo.flow("next")
        self.assertEqual(rc, 0, out)
        self.assertTrue(out.startswith("REVIEW %s 01 " % T1), out)
        self.assertIn("Verdict 1: does it meet the ticket?", self.repo.flow("prompt")[1])

    def test_review_pass_a_reviewer_commit_in_the_quality_pass_stops(self):
        self.to_quality()
        self.passed()
        self.repo.path("sneaky.txt").write_text("x\n", encoding="utf-8")
        self.repo.commit("reviewer edit")
        rc, out = self.repo.flow("next")
        self.assertEqual(rc, 1)
        self.assertIn("STOP the reviewer changed tracked files", out)

    def test_review_pass_no_verdict_in_the_quality_pass_retries_the_quality_review(self):
        self.to_quality()
        self.assertEqual(self.reply("no verdict here\n"), (0, "RETRY no review verdict"))
        self.assertEqual(self.repo.flow("next"), (0, self.review))
        self.assertIn("Verdict 2: is it good?", self.repo.flow("prompt")[1])

    def test_review_pass_no_verdict_in_the_quality_pass_stops_after_the_retries(self):
        self.to_quality()
        self.assertEqual(self.reply("none\n"), (0, "RETRY no review verdict"))
        self.assertEqual(self.repo.flow("next"), (0, self.review))
        self.assertEqual(self.reply("none\n"), (0, "RETRY no review verdict"))
        rc, out = self.repo.flow("next")
        self.assertEqual(rc, 1)
        self.assertIn("STOP no review verdict for 01-a after 2 attempt(s)", out)

    def test_review_pass_attempts_are_counted_per_pass(self):
        env = {"FLOW_MAX_RETRIES": "2"}
        self.assertEqual(self.repo.flow("next", **env), (0, self.review))
        self.assertEqual(self.reply("none\n", **env), (0, "RETRY no review verdict"))
        self.assertEqual(self.repo.flow("next", **env), (0, self.review))
        self.assertEqual(self.reply("fine\nREVIEW: PASS\n", **env), (0, "OK"))
        self.assertEqual(self.repo.flow("next", **env), (0, self.review))
        self.assertEqual(self.reply("none\n", **env), (0, "RETRY no review verdict"))
        self.assertEqual(self.repo.flow("next", **env), (0, self.review))
        self.assertIn("Verdict 2: is it good?", self.repo.flow("prompt")[1])


if __name__ == "__main__":
    unittest.main()
