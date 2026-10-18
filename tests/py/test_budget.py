"""What a run costs and when a session hands off: the adaptive handoff, FLOW_TOKENS, the stop-and-ask
budget, the minutes and tokens in the report, and the agent estimate of flow-status."""

import io
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import helpers
from helpers import ROOT, Repo

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import report, status  # the package under test, from this checkout

T1, T2 = "plans/f/tasks/01-a.md", "plans/f/tasks/02-b.md"


class Session(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.addCleanup(self.repo.close)
        for folder in ("agents", "guides"):
            shutil.copytree(str(ROOT / folder), str(self.repo.path(folder)))
        self.repo.commit("guides")
        self.reply = self.repo.dir.parent / (self.repo.dir.name + "-reply.txt")
        self.addCleanup(self.reply.unlink, missing_ok=True)
        self.reply.write_text("fine\nREVIEW: PASS\n", encoding="utf-8")

    def start(self, **env):
        rc, out = self.repo.flow("start", **env)
        self.assertEqual(rc, 0, out)
        return dict(env, FLOW_SESSION=out.split()[1])

    def ticket(self, rel, env, prompt=("prompt",)):
        """Build and review one ticket; returns what `next` says after its last review."""
        rc, out = self.repo.flow("next", **env)
        self.assertTrue(out.startswith("BUILD %s " % rel), out)
        self.repo.flow(*prompt, **env)
        self.repo.resolve(rel)
        while True:
            rc, out = self.repo.flow("next", **env)
            if not out.startswith("REVIEW"):
                return out
            self.repo.flow(*prompt, **env)
            self.repo.flow("verdict", str(self.reply), **env)

    def test_a_full_session_hands_off_at_the_next_ticket(self):
        env = self.start(FLOW_SESSION_BUDGET="1")
        rc, out = self.repo.flow("next", **env)
        self.assertTrue(out.startswith("BUILD"), out)  # the first ticket of a session always starts
        self.repo.resolve(T1)
        self.repo.flow("next", **env)
        self.repo.flow("verdict", str(self.reply), **env)
        self.repo.flow("next", **env)
        self.repo.flow("verdict", str(self.reply), **env)
        self.assertEqual(self.repo.flow("next", **env), (0, "HANDOFF /feature-flow f"))

    def test_the_default_budget_keeps_a_small_session_going(self):
        env = self.start()
        out = self.ticket(T1, env)
        self.assertTrue(out.startswith("BUILD %s " % T2), out)

    def test_prompts_in_files_cost_the_session_far_less(self):
        env = self.start()
        self.ticket(T1, env)
        inline = int(self.repo.state()["session_load"])
        self.repo.flow("reset", "1", FLOW_TAKEOVER="1")
        env = self.start(FLOW_TAKEOVER="1")
        self.ticket(T1, env, prompt=("prompt", "--file"))
        filed = int(self.repo.state()["session_load"])
        self.assertLess(filed * 2, inline, (filed, inline))

    def test_a_ticket_count_still_hands_off_the_old_way(self):
        env = self.start(FLOW_TICKETS_PER_SESSION="1", FLOW_SESSION_BUDGET="1")
        self.assertEqual(self.ticket(T1, env), "HANDOFF /feature-flow f")
        env = self.start(FLOW_TICKETS_PER_SESSION="0", FLOW_SESSION_BUDGET="1", FLOW_TAKEOVER="1")
        self.assertTrue(self.ticket(T2, env).startswith("DONE"))

    def test_tokens_are_logged_against_the_ticket(self):
        env = self.start()
        self.repo.flow("next", **env)
        self.repo.resolve(T1)
        self.repo.flow("next", FLOW_TOKENS="45210", **env)
        self.assertRegex(self.repo.log(), r"\n\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d,01,SPENT 45210\n")
        rc, out = self.repo.flow("verdict", str(self.reply), FLOW_TOKENS="many", **env)
        self.assertEqual(rc, 1)
        self.assertIn("FLOW_TOKENS must be a whole number", out)

    def test_the_budget_stops_the_run_at_a_ticket_boundary(self):
        env = self.start(FLOW_BUDGET_TOKENS="1000")
        self.repo.flow("next", **env)
        self.repo.resolve(T1)
        self.repo.flow("next", FLOW_TOKENS="900", **env)
        self.repo.flow("verdict", str(self.reply), FLOW_TOKENS="300", **env)
        self.repo.flow("next", **env)
        self.repo.flow("verdict", str(self.reply), **env)
        rc, out = self.repo.flow("next", **env)
        self.assertEqual(rc, 1)
        self.assertIn("STOP budget reached: 1200 of 1000 tokens spent in this run", out)
        rc, out = self.repo.flow("next", **dict(env, FLOW_BUDGET_TOKENS="5000"))
        self.assertTrue(out.startswith("BUILD %s " % T2), out)


LOG = """2026-10-18T10:00:00,-,START
2026-10-18T10:00:00,01,BUILD
2026-10-18T10:11:00,01,SPENT 60000
2026-10-18T10:11:00,01,GATE-QUICK
2026-10-18T10:17:00,01,GATE-PASS 360s
2026-10-18T10:17:00,01,REVIEW-SKIP
2026-10-18T10:18:00,02,BUILD
2026-10-18T14:18:00,02,GATE-QUICK
2026-10-18T14:20:00,02,REVIEW
2026-10-18T14:25:00,02,SPENT 30000
2026-10-18T14:25:00,02,VERDICT-PASS
2026-10-18T14:26:00,phase,PHASE-REVIEW
2026-10-18T14:30:00,phase,VERDICT-PASS correctness
2026-10-18T14:31:00,phase,VERDICT-FAIL security
"""


class Report(unittest.TestCase):
    def test_minutes_and_tokens_per_ticket_with_pauses_left_out(self):
        cells = report.costs(report.timed(LOG))
        self.assertEqual(cells["01"], [17 * 60, 60000])
        self.assertEqual(cells["02"], [60 + 3600 + 7 * 60, 30000])  # the four hour gap counts as one hour
        self.assertEqual(report.usage(report.timed(LOG)), (91, 90000))

    def test_the_report_shows_them_and_counts_the_agents(self):
        text = report.render("f", report.parse(LOG), report.timed(LOG))
        self.assertIn("minutes  tokens", text)
        self.assertRegex(text, r"01 +1 +0 +1 .* 17 +60k +none")
        self.assertIn("this run: 91 minutes, 5 subagents, 90k tokens", text)

    def test_an_old_log_without_dates_still_reads(self):
        old = "23:59:00,01,BUILD\n00:04:00,01,REVIEW\n"
        self.assertEqual(report.costs(report.timed(old))["01"], [300, 0])

    def test_a_reset_starts_a_new_run(self):
        self.assertEqual(report.usage(report.timed(LOG + "2026-10-18T15:00:00,-,RESET\n")), (0, 0))


class Estimate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        Path("plans/f/tasks").mkdir(parents=True)
        check = "```check\n$ true\n```\n"
        for num, header, block in (("01", "Review: gate", check), ("02", "Review: full", check), ("03", "", check),
                                   ("04", "Review: gate", ""), ("05", "Type: acceptance\nReview: gate", check)):
            Path("plans/f/tasks/%s-t.md" % num).write_text(
                "# T\n\nStatus: open\nBlocked by: —\n%s\n\n## Done when\n\n- x\n%s\n## Answer\n" % (header, block),
                encoding="utf-8")

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def test_it_counts_builders_reviewers_and_the_phase_review(self):
        out = io.StringIO()
        self.assertEqual(status.run(["f", "--estimate"], out, out), 0)
        text = out.getvalue()
        self.assertIn("01  builder 1  reviewers 0  Review: gate", text)
        self.assertIn("03  builder 1  reviewers 1-2  Review: auto", text)
        self.assertIn("04  builder 1  reviewers 2  Review: gate, no check block", text)
        self.assertIn("estimate: 5 ticket(s) to build: 5 builder(s), 5-6 ticket reviewer(s), 3 phase reviewer(s): "
                      "13-14 fresh subagents on the first try", text)


if __name__ == "__main__":
    unittest.main()
