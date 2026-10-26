import shutil
import unittest

from helpers import ROOT, Repo

T1 = "plans/f/tasks/01-a.md"
T2 = "plans/f/tasks/02-b.md"
CHECK = "```check\n$ python3 -c \"print('fine')\"\nprints fine\n```\n"


def with_header(text, line):
    return text.replace("Type: task\n", "Type: task\n%s\n" % line, 1) if line else text


class SmallReview(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        for folder in ("agents", "guides"):
            shutil.copytree(str(ROOT / folder), str(self.repo.path(folder)))
        self.repo.commit("prompts")

    def tearDown(self):
        self.repo.close()

    def prepare(self, check=True, header="", ticket_type=None):
        """Edit ticket 01 (check block, header line) and commit it, so it is part of the base."""
        path = self.repo.path(T1)
        text = path.read_text(encoding="utf-8")
        if check:
            text = text.replace("## Answer", CHECK + "\n## Answer")
        text = with_header(text, header)
        if ticket_type:
            text = text.replace("Type: task", "Type: %s" % ticket_type)
        path.write_text(text, encoding="utf-8")
        self.repo.git("add", "-A")
        self.repo.git("commit", "--allow-empty", "-qm", "ticket")
        self.base = self.repo.head()
        self.review = "REVIEW %s 01 %s" % (T1, self.base)

    def build(self, lines=1, **env):
        self.assertEqual(self.repo.flow("next", **env)[1].split(" ")[0], "BUILD")
        path = self.repo.path("work.txt")
        path.write_text("x\n" * lines, encoding="utf-8")
        self.repo.set_status(T1, "resolved")
        self.repo.commit("feat: work")
        return self.repo.flow("next", **env)

    def reply(self, text, **env):
        path = self.repo.dir.parent / (self.repo.dir.name + "-reply.txt")
        path.write_text(text, encoding="utf-8")
        self.addCleanup(path.unlink, missing_ok=True)
        return self.repo.flow("verdict", str(path), **env)

    def test_small_checked_ticket_gets_one_review(self):
        self.prepare()
        self.assertEqual(self.build(), (0, self.review))
        self.assertEqual(self.repo.state()["review_pass"], "single")
        self.assertIn("REVIEW-SMALL", self.repo.log())
        prompt = self.repo.flow("prompt")[1]
        self.assertIn("(single pass)", prompt)
        self.assertIn("the conductor judged this ticket small (", prompt)
        self.assertEqual(self.reply("fine\nREVIEW: PASS\n"), (0, "OK"))
        rc, out = self.repo.flow("next")
        self.assertEqual(rc, 0)
        self.assertTrue(out.startswith("BUILD %s 02 " % T2), out)

    def test_small_review_fail_sends_back_as_single_review(self):
        self.prepare()
        self.build()
        self.assertEqual(self.reply("no\nREVIEW: FAIL\n"), (0, "OK"))
        rc, out = self.repo.flow("next")
        self.assertTrue(out.startswith("BUILD %s 01 " % T1), out)
        self.assertIn("## Review findings (round 1, single review)", self.repo.path(T1).read_text(encoding="utf-8"))
        self.assertEqual(self.repo.state()["review_pass"], "spec")

    def assert_two_passes(self, **env):
        self.assertEqual(self.build(**env), (0, self.review))
        self.assertEqual(self.repo.state().get("review_pass", "spec"), "spec")
        self.assertNotIn("REVIEW-SMALL", self.repo.log())
        self.assertEqual(self.reply("ok\nREVIEW: PASS\n"), (0, "OK"))
        self.assertEqual(self.repo.flow("next", **env), (0, self.review))
        self.assertEqual(self.repo.state()["review_pass"], "quality")

    def test_review_full_at_base_keeps_two_passes(self):
        self.prepare(header="Review: full")
        self.assert_two_passes()

    def test_review_full_added_after_base_is_ignored(self):
        self.prepare(header="Floor: allow ticket-edit")
        self.repo.flow("next")
        path = self.repo.path(T1)
        path.write_text(with_header(path.read_text(encoding="utf-8"), "Review: full"), encoding="utf-8")
        self.repo.set_status(T1, "resolved")
        self.repo.path("work.txt").write_text("x\n", encoding="utf-8")
        self.repo.commit("feat: work")
        self.assertEqual(self.repo.flow("next"), (0, self.review))
        self.assertEqual(self.repo.state()["review_pass"], "single")

    def test_no_check_block_keeps_two_passes(self):
        self.prepare(check=False)
        self.assert_two_passes()

    def test_convert_is_level_3_with_one_review(self):
        self.prepare(ticket_type="convert")
        self.assertEqual(self.build(), (0, self.review))
        self.assertEqual(self.repo.state()["review_pass"], "single")
        self.assertIn("hostile caller", self.repo.flow("prompt")[1])

    def test_big_diff_keeps_two_passes(self):
        self.prepare()
        self.base_lines = 61
        self.assertEqual(self.build(lines=61), (0, self.review))
        self.assertEqual(self.repo.state()["review_pass"], "spec")
        self.assertNotIn("REVIEW-SMALL", self.repo.log())

    def test_small_lines_zero_keeps_two_passes(self):
        self.prepare()
        self.assert_two_passes(FLOW_SMALL_LINES="0")

    def test_bad_small_lines_stops(self):
        self.prepare()
        rc, out = self.repo.flow("next", FLOW_SMALL_LINES="abc")
        self.assertEqual((rc, out), (1, "STOP FLOW_SMALL_LINES must be a whole number, not abc"))

    def test_state_saved_by_0_5_0_mid_quality_pass_picks_next_ticket(self):
        self.prepare(header="Review: full")
        self.build()
        self.reply("ok\nREVIEW: PASS\n")
        self.repo.flow("next")
        self.assertEqual(self.repo.state()["review_pass"], "quality")
        self.assertEqual(self.reply("ok\nREVIEW: PASS\n"), (0, "OK"))
        rc, out = self.repo.flow("next")
        self.assertTrue(out.startswith("BUILD %s 02 " % T2), out)


if __name__ == "__main__":
    unittest.main()
