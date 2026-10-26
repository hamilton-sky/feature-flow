"""Ticket levels: the Level line read at base, raised and never lowered, its review passes and rework rounds."""

import io
import re
import shutil
import sys
import unittest

from helpers import ROOT, Repo

sys.path.insert(0, str(ROOT))
from feature_flow import conductor, report, status, tickets  # the package under test, from this checkout

PYTHON = '"%s"' % sys.executable
T1 = "plans/f/tasks/01-a.md"
T2 = "plans/f/tasks/02-b.md"
CHECK = "```check\n$ %s -c \"print('fine')\"\nprints fine\n```\n\n" % PYTHON
MAJOR = "QUALITY\n1. major work.txt: could be tidier - tidy it\n\nREVIEW: FAIL\n"
BLOCKER = "QUALITY\n1. blocker work.txt: loses data - keep it\n2. major work.txt: tidy\n\nREVIEW: FAIL\n"


def ticket(index, header):
    lines = ["# T%d\n" % index, "Type: task", "Status: open",
             "Blocked by: %s" % ("—" if index == 1 else "%02d" % (index - 1)), "Test first: no"] + header
    return "\n".join(lines) + "\n\nbody\n\n## Done when\n\n- x\n\n" + CHECK + "## Answer\n"


class Levels(unittest.TestCase):
    def setUp(self):
        self.repo = Repo(tickets=())
        self.addCleanup(self.repo.close)
        for folder in ("agents", "guides"):
            shutil.copytree(str(ROOT / folder), str(self.repo.path(folder)))

    def plan(self, first, second=("Level: 2",), sensitive=""):
        commands = "# Commands: f\n\nSmoke: `%s -c \"pass\"`\n" % PYTHON
        if sensitive:
            commands += "Sensitive: `%s`\n" % sensitive
        self.repo.path("plans/f/commands.md").write_text(commands, encoding="utf-8")
        self.repo.path(T1).write_text(ticket(1, list(first)), encoding="utf-8")
        self.repo.path(T2).write_text(ticket(2, list(second)), encoding="utf-8")
        self.repo.commit("plan")

    def build(self, lines=1, name="work.txt", rel=T1):
        rc, out = self.repo.flow("next")
        self.assertEqual((rc, out.split(" ")[0]), (0, "BUILD"), out)
        self.repo.path(name).parent.mkdir(parents=True, exist_ok=True)
        self.repo.path(name).write_text("x\n" * lines, encoding="utf-8")
        self.repo.set_status(rel, "resolved")
        self.repo.commit("feat: work")
        return self.repo.flow("next")

    def rebuild(self, round_no):
        self.repo.path("work.txt").write_text("y\n" * round_no, encoding="utf-8")
        self.repo.set_status(T1, "resolved")
        self.repo.commit("feat: round %d" % round_no)
        return self.repo.flow("next")

    def reply(self, text):
        path = self.repo.dir.parent / (self.repo.dir.name + "-reply.txt")
        path.write_text(text, encoding="utf-8")
        self.addCleanup(path.unlink, missing_ok=True)
        return self.repo.flow("verdict", str(path))

    def review_pass(self):
        return re.search(r"\((single|spec|quality) pass\)", self.repo.flow("prompt")[1]).group(1)

    # ---- which reviews a level gets ---------------------------------------

    def test_level_1_gets_one_review(self):
        self.plan(["Level: 1"])
        self.assertTrue(self.build()[1].startswith("REVIEW "))
        self.assertEqual((self.repo.state()["level"], self.review_pass()), ("1", "single"))
        self.assertIn("this ticket is level 1 (light)", self.repo.flow("prompt")[1])
        self.assertIn("LEVEL-1", self.repo.log())

    def test_level_1_over_the_small_limits_becomes_level_2(self):
        self.plan(["Level: 1"])
        self.build(lines=61)
        self.assertEqual((self.repo.state()["level"], self.review_pass()), ("2", "single"))
        self.assertIn("raised because the diff (1 files, 61 lines) is over the small limits", self.repo.flow("prompt")[1])

    def test_level_2_big_diff_still_gets_one_review(self):
        self.plan(["Level: 2"])
        self.build(lines=200)
        self.assertEqual((self.repo.state()["level"], self.review_pass()), ("2", "single"))
        self.assertIn("REVIEW-SINGLE", self.repo.log())

    def test_level_3_gets_one_review_that_probes_as_a_hostile_caller(self):
        self.plan(["Level: 3"])
        self.build()
        self.assertEqual(self.review_pass(), "single")
        prompt = self.repo.flow("prompt")[1]
        self.assertIn("this ticket is level 3 (boundary)", prompt)
        self.assertIn("then probe the change as a hostile caller", prompt)
        self.assertEqual(self.reply("ok\nREVIEW: PASS\n"), (0, "OK"))
        self.assertTrue(self.repo.flow("next")[1].startswith("BUILD %s 02 " % T2))

    def test_level_3_with_review_full_gets_spec_then_quality(self):
        self.plan(["Level: 3", "Review: full"])
        self.build()
        self.assertEqual(self.review_pass(), "spec")
        self.assertEqual(self.reply("ok\nREVIEW: PASS\n"), (0, "OK"))
        self.assertTrue(self.repo.flow("next")[1].startswith("REVIEW "))
        self.assertEqual(self.review_pass(), "quality")

    def test_sensitive_path_makes_level_3(self):
        self.plan(["Level: 2"], sensitive="src/auth/, *token*")
        self.build(name="src/auth/login.py")
        self.assertEqual((self.repo.state()["level"], self.review_pass()), ("3", "single"))
        self.assertIn("touches a Sensitive path in commands.md: src/auth/login.py", self.repo.flow("prompt")[1])

    def test_sensitive_glob_crosses_folders(self):
        self.plan(["Level: 1"], sensitive="*token*")
        self.build(name="lib/run_token.py")
        self.assertEqual(self.repo.state()["level"], "3")

    def test_untouched_sensitive_path_leaves_the_level(self):
        self.plan(["Level: 2"], sensitive="src/auth/")
        self.build(name="src/other.py")
        self.assertEqual(self.repo.state()["level"], "2")

    def test_review_full_and_flow_edit_make_level_3(self):
        for header, review in ((["Level: 1", "Review: full"], "spec"), (["Level: 2", "Floor: allow flow-edit"], "single")):
            with self.subTest(header=header):
                self.repo.close()
                self.setUp()
                self.plan(header)
                self.build()
                self.assertEqual((self.repo.state()["level"], self.review_pass()), ("3", review))

    def test_level_lowered_by_the_builder_is_ignored(self):
        self.plan(["Level: 3", "Floor: allow ticket-edit"])
        self.repo.flow("next")
        path = self.repo.path(T1)
        path.write_text(path.read_text(encoding="utf-8").replace("Level: 3", "Level: 1"), encoding="utf-8")
        self.repo.set_status(T1, "resolved")
        self.repo.path("work.txt").write_text("x\n", encoding="utf-8")
        self.repo.commit("feat: work")
        self.assertTrue(self.repo.flow("next")[1].startswith("REVIEW "))
        self.assertEqual((self.repo.state()["level"], self.review_pass()), ("3", "single"))

    def test_no_level_keeps_the_size_rule(self):
        self.plan([], [])
        self.build()
        self.assertEqual((self.repo.state()["level"], self.review_pass()), ("0", "single"))
        self.assertIn("REVIEW-SMALL", self.repo.log())
        self.assertNotIn("LEVEL-", self.repo.log())

    # ---- a reviewer may raise, never lower --------------------------------

    def test_reviewer_raises_to_3_and_a_quality_review_follows(self):
        self.plan(["Level: 2"])
        self.build()
        self.assertEqual(self.reply("hole\nLEVEL: 3\nREVIEW: PASS\n"), (0, "OK"))
        self.assertEqual(self.repo.state()["level"], "3")
        self.assertTrue(self.repo.flow("next")[1].startswith("REVIEW "))
        prompt = self.repo.flow("prompt")[1]
        self.assertIn("(quality pass)", prompt)
        self.assertIn("this ticket is level 3 (boundary), raised because a reviewer raised it", prompt)
        self.assertIn("LEVEL-RAISE", self.repo.log())

    def test_reviewer_cannot_lower(self):
        self.plan(["Level: 2"])
        self.build()
        self.assertEqual(self.reply("fine\nLEVEL: 1\nREVIEW: PASS\n"), (0, "OK"))
        self.assertEqual(self.repo.state()["level"], "2")
        self.assertTrue(self.repo.flow("next")[1].startswith("BUILD %s 02 " % T2))

    def test_reviewer_level_2_on_a_ticket_without_level_is_ignored(self):
        self.plan([], [])
        self.build()
        self.reply("fine\nLEVEL: 2\nREVIEW: PASS\n")
        self.assertEqual(self.repo.state()["level"], "0")

    # ---- rework rounds by level -------------------------------------------

    def test_level_1_stops_after_one_round(self):
        self.plan(["Level: 1"])
        self.build()
        self.reply(MAJOR)
        self.assertTrue(self.repo.flow("next")[1].startswith("BUILD %s 01 " % T1))
        self.rebuild(1)
        self.reply(MAJOR)
        self.assertEqual(self.repo.flow("next"), (1, "STOP 01-a still fails the single review after 1 round(s) at "
                                                     "level 1. the user decides what happens next"))

    def fail_twice(self):
        self.build()
        for round_no in (1, 2):
            self.assertEqual(self.reply(MAJOR), (0, "OK"))
            self.assertTrue(self.repo.flow("next")[1].startswith("BUILD %s 01 " % T1))
            self.assertTrue(self.rebuild(round_no)[1].startswith("REVIEW "))

    def test_level_2_passes_with_followups_from_round_3(self):
        self.plan(["Level: 2"])
        self.fail_twice()
        self.assertIn("only a blocker finding sends the ticket back", self.repo.flow("prompt")[1])
        self.assertEqual(self.reply(MAJOR), (0, "OK"))
        rc, out = self.repo.flow("next")
        self.assertTrue(out.startswith("BUILD %s 02 " % T2), out)
        text = self.repo.path("plans/f/followups.md").read_text(encoding="utf-8")
        self.assertIn("## 01-a (round 3, single review)", text)
        self.assertIn("- 1. major work.txt: could be tidier - tidy it", text)
        self.assertEqual(self.repo.porcelain(), "")
        self.assertIn("PASS-FOLLOWUPS", self.repo.log())
        self.assertIn("follow-ups from the single review", self.repo.git("log", "-1", "--format=%s", "--", "plans/f/followups.md"))

    def test_level_2_blocker_in_round_3_still_sends_back(self):
        self.plan(["Level: 2"])
        self.fail_twice()
        self.reply(BLOCKER)
        self.assertTrue(self.repo.flow("next")[1].startswith("BUILD %s 01 " % T1))
        self.assertFalse(self.repo.path("plans/f/followups.md").exists())

    def test_level_2_unmet_done_when_in_round_3_still_sends_back(self):
        self.plan(["Level: 2"])
        self.fail_twice()
        self.reply("SPEC\n- x: NOT MET - printed nothing\n\nQUALITY\n1. major a: b - c\n\nREVIEW: FAIL\n")
        self.assertTrue(self.repo.flow("next")[1].startswith("BUILD %s 01 " % T1))

    def test_level_3_never_passes_with_followups(self):
        self.plan(["Level: 3"])
        self.build()
        for round_no in (1, 2, 3):
            self.reply(MAJOR)
            out = self.repo.flow("next")[1]
            self.assertTrue(out.startswith("BUILD %s 01 " % T1), out)
            self.assertTrue(self.rebuild(round_no)[1].startswith("REVIEW "))
            self.assertEqual(self.review_pass(), "single")
        self.reply(MAJOR)
        self.assertEqual(self.repo.flow("next"), (1, "STOP 01-a still fails the single review after 3 round(s) at "
                                                     "level 3. the user decides what happens next"))

    # ---- a rebuild reruns only the pass that failed -----------------------

    def test_quality_fail_rebuild_skips_the_spec_pass(self):
        self.plan(["Level: 3", "Review: full"])
        self.build()
        self.reply("ok\nREVIEW: PASS\n")
        self.repo.flow("next")
        self.reply(MAJOR)
        self.repo.flow("next")
        self.rebuild(1)
        prompt = self.repo.flow("prompt")[1]
        self.assertIn("(quality pass)", prompt)
        self.assertIn("the spec review passed in an earlier round", prompt)

    def test_spec_fail_rebuild_starts_at_spec(self):
        self.plan(["Level: 3", "Review: full"])
        self.build()
        self.reply("SPEC\n- x: NOT MET\n\nREVIEW: FAIL\n")
        self.repo.flow("next")
        self.rebuild(1)
        self.assertEqual(self.review_pass(), "spec")

    def test_done_line_counts_followups(self):
        self.plan(["Level: 2"], ["Level: 1"])
        self.fail_twice()
        self.reply(MAJOR)
        self.repo.flow("next")
        self.repo.path("two.txt").write_text("x\n", encoding="utf-8")
        self.repo.set_status(T2, "resolved")
        self.repo.commit("feat: two")
        self.repo.flow("next")
        self.reply("fine\nREVIEW: PASS\n")
        self.assertEqual(self.repo.flow("next"), (0, "DONE f is complete: 2 ticket(s) resolved in this run; "
                                                     "1 passed with follow-ups in plans/f/followups.md"))


class Units(unittest.TestCase):
    def test_followups_only(self):
        self.assertTrue(conductor.followups_only(MAJOR))
        self.assertTrue(conductor.followups_only("SPEC\n- x: MET (conductor)\n- scope: OK\n- test first: n/a\n\n" + MAJOR))
        self.assertFalse(conductor.followups_only(BLOCKER))
        self.assertFalse(conductor.followups_only("no findings\nREVIEW: FAIL\n"))
        self.assertFalse(conductor.followups_only("- scope: src/extra.py\n" + MAJOR))
        self.assertFalse(conductor.followups_only("- test first: MISSING\n" + MAJOR))

    def test_sensitive_patterns(self):
        patterns = tickets.sensitive_patterns("Smoke: `x`\nSensitive: `src/auth/, *token*  scripts/flow.py`\n")
        self.assertEqual(patterns, ["src/auth/", "*token*", "scripts/flow.py"])
        self.assertTrue(tickets.matches_sensitive("src/auth/deep/a.py", patterns))
        self.assertTrue(tickets.matches_sensitive("a/b/run_token.go", patterns))
        self.assertTrue(tickets.matches_sensitive("scripts/flow.py", patterns))
        self.assertFalse(tickets.matches_sensitive("src/authx.py", patterns))
        self.assertEqual(tickets.sensitive_patterns("Sensitive: `<optional: paths>`\n"), [])

    def test_report_shows_the_level(self):
        log = "1,01,BUILD\n2,01,LEVEL-2\n3,01,REVIEW-SINGLE\n4,01,REVIEW\n5,01,LEVEL-RAISE\n6,01,PASS-FOLLOWUPS\n"
        text = report.render("f", report.parse(log))
        self.assertIn("ticket  level  builds  reviews  single", text)
        self.assertRegex(text, r"01\s+2\s+1\s+1\s+1\s")
        self.assertIn("tickets passed with follow-ups (see the plan's followups.md): 01", text)


class LevelCheck(unittest.TestCase):
    def setUp(self):
        self.repo = Repo(tickets=())
        self.addCleanup(self.repo.close)

    def run_status(self, mode):
        import os
        here = os.getcwd()
        os.chdir(str(self.repo.dir))
        try:
            out, err = io.StringIO(), io.StringIO()
            return status.run(["f", mode], out, err), out.getvalue()
        finally:
            os.chdir(here)

    def test_bad_level_fails_the_check(self):
        self.repo.path(T1).write_text(ticket(1, ["Level: 4"]), encoding="utf-8")
        code, out = self.run_status("--check")
        self.assertEqual(code, 1)
        self.assertIn("01: Level must be 1, 2 or 3", out)

    def test_missing_level_is_a_lint_warning(self):
        self.repo.path(T1).write_text(ticket(1, []), encoding="utf-8")
        self.assertNotIn("Level", self.run_status("--check")[1])
        self.assertIn("01: no `Level:` line", self.run_status("--lint")[1])


if __name__ == "__main__":
    unittest.main()
