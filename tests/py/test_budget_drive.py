"""Drive the time budget the way the skill does: FLOW_BUDGET or `budget` sets minutes of work, `next` counts the
time between steps, and once it is spent the conductor turns fast mode on by itself, then stops once to offer a
re-plan. `replan-prompt` hands the planner the open tickets, and the next `next` checks that the re-plan left the
resolved tickets alone. A second `fast on` points at the re-plan.

The time spent is set in the state file here, as hours of real work would leave it.
"""

import shutil
import sys
import time
import unittest

from helpers import ROOT, Repo

PYTHON = '"%s"' % sys.executable
CHECK = "```check\n$ %s -c \"print('fine')\"\nprints fine\n```\n\n" % PYTHON


def ticket(index):
    return ("# T%d\n\nType: task\nStatus: open\nBlocked by: %s\nTest first: no\nLevel: 2\n\nbody\n\n## Done when\n\n"
            "- x\n\n" % (index, "—" if index == 1 else "%02d" % (index - 1))) + CHECK + "## Answer\n"


def path(index):
    return "plans/f/tasks/%02d-t.md" % index


class Base(unittest.TestCase):
    def setup(self, count=4, **env):
        repo = Repo(tickets=())
        self.addCleanup(repo.close)
        env = dict({"FLOW_TICKETS_PER_SESSION": "99", "FLOW_SCOUTS": "off"}, **env)
        for folder in ("agents", "guides"):
            shutil.copytree(str(ROOT / folder), str(repo.path(folder)))
        repo.path("plans/f/commands.md").write_text(
            "# Commands: f\n\nSmoke: `%s -c \"pass\"`\nTest: `%s -c \"pass\"`\n" % (PYTHON, PYTHON), encoding="utf-8")
        for index in range(1, count + 1):
            repo.path(path(index)).write_text(ticket(index), encoding="utf-8")
        repo.commit("plan")
        rc, out = repo.flow("start", **env)
        self.assertEqual(rc, 0, out)
        env["FLOW_SESSION"] = out.split()[1]
        self.repo, self.env = repo, env
        return repo

    def flow(self, *args):
        return self.repo.flow(*args, **self.env)

    def spend(self, minutes, **more):
        """Write the minutes spent into the state, with the last step just now."""
        values = dict({"spent": minutes * 60, "seen": int(time.time())}, **more)
        file = self.repo.path(".feature-flow/state/flow-f.state")
        lines = [line for line in file.read_text(encoding="utf-8").splitlines()
                 if line.split("=", 1)[0] not in values]
        file.write_text("\n".join(lines + ["%s=%s" % kv for kv in values.items()]) + "\n", encoding="utf-8")

    def build(self, index):
        """Resolve a handed out ticket, then `next` (which passes it in fast mode, or hands out its review)."""
        self.repo.resolve(path(index))
        return self.flow("next")


class BudgetDrive(Base):
    def test_over_budget_turns_fast_on_then_stops_once_with_a_replan_offer(self):
        repo = self.setup(FLOW_BUDGET="30")
        self.assertTrue(self.flow("next")[1].startswith("BUILD %s" % path(1)))
        rc, line = self.build(1)
        self.assertTrue(line.startswith("REVIEW"), line)  # under budget, fast off: a review of its own
        reply = repo.dir.parent / (repo.dir.name + "-reply.txt")
        self.addCleanup(reply.unlink, missing_ok=True)
        reply.write_text("fine\nREVIEW: PASS\n", encoding="utf-8")
        self.spend(31)
        self.assertEqual(self.flow("verdict", str(reply)), (0, "OK"))
        rc, line = self.flow("next")
        self.assertTrue(line.startswith("BUILD %s" % path(2)), line)
        self.assertEqual(repo.state()["fast"], "1")
        self.assertIn("BUDGET-FAST", repo.log())
        rc, out = self.build(2)  # fast mode passes it without a review, then the offer comes
        self.assertEqual(rc, 1, out)
        self.assertIn("over the time budget for f: 31 of 30 active minute(s) spent, 2 ticket(s) left, fast mode on",
                      out)
        self.assertIn("with the user's yes, run replan-prompt", out)
        self.assertNotIn("stuck", out)
        rc, line = self.flow("next")  # no yes: go on as planned, and no second stop
        self.assertTrue(line.startswith("BUILD %s" % path(3)), line)

    def test_fast_already_on_gets_the_offer_at_once(self):
        repo = self.setup(FLOW_FAST="1", FLOW_BUDGET="10")
        self.flow("next")
        self.spend(11)
        rc, out = self.build(1)
        self.assertEqual(rc, 1)
        self.assertIn("over the time budget", out)

    def test_a_stuck_ticket_is_named_as_stuck(self):
        repo = self.setup(FLOW_FAST="1", FLOW_BUDGET="10")
        self.flow("next")
        self.spend(100, slowest="07:3600:3", ticket_clock=6000)  # 01 itself took no time
        rc, out = self.build(1)
        self.assertIn("Most of it went to ticket 07 (60 minute(s), 3 attempts): that ticket is stuck", out)

    def test_a_second_speed_up_points_at_the_replan(self):
        self.setup()
        self.assertEqual(self.flow("fast", "on"), (0, "OK fast on"))
        rc, out = self.flow("fast", "on")
        self.assertEqual(rc, 0)
        self.assertIn("fast is already on", out)
        self.assertIn("run replan-prompt", out)

    def test_budget_reports_sets_adds_and_turns_off(self):
        repo = self.setup()
        self.assertEqual(self.flow("budget"), (0, "OK no budget. 0 active minute(s) spent so far"))
        self.assertEqual(self.flow("budget", "20"), (0, "OK budget 20 minute(s), 0 spent, fast off"))
        self.assertEqual(self.flow("budget", "+15")[1], "OK budget 35 minute(s), 0 spent, fast off")
        self.assertEqual(self.flow("budget", "off")[1], "OK no budget. 0 active minute(s) spent so far")
        self.assertEqual(self.flow("budget", "soon"),
                         (1, "STOP the budget is a number of minutes, +minutes or off, not soon"))
        self.assertIn("flow-trust.py", repo.flow("budget", "5", FLOW_TRUSTED="0", FLOW_SESSION=self.env["FLOW_SESSION"])[1])

    def test_a_long_pause_counts_as_one_hour_at_most_and_a_new_session_as_none(self):
        repo = self.setup()
        self.spend(0, seen=int(time.time()) - 5 * 3600)
        self.flow("next")
        self.assertTrue(3600 <= int(repo.state()["spent"]) < 3700)
        self.spend(0, seen=int(time.time()) - 5 * 3600)
        rc, out = repo.flow("start", FLOW_TAKEOVER="1", FLOW_SCOUTS="off")
        self.env["FLOW_SESSION"] = out.split()[1]
        self.flow("next")
        self.assertLess(int(repo.state()["spent"]), 60)


    def test_reset_keeps_the_budget_and_the_time_spent(self):
        repo = self.setup(FLOW_BUDGET="30")
        self.spend(12)
        self.assertEqual(repo.flow("reset", FLOW_TAKEOVER="1")[0], 0)
        self.assertEqual((repo.state()["budget"], repo.state()["spent"]), ("30", "720"))

class Replan(Base):
    def test_replan_prompt_lists_the_open_tickets_between_tickets_only(self):
        self.setup(FLOW_FAST="1", FLOW_BUDGET="10")
        self.flow("next")
        self.assertEqual(self.flow("replan-prompt"), (1, "STOP a ticket is in progress. run replan-prompt between "
                                                         "tickets, when next would start a new one"))
        self.spend(11)
        self.assertEqual(self.build(1)[0], 1)  # the offer: between tickets now
        rc, out = self.flow("replan-prompt")
        self.assertEqual(rc, 0, out)
        self.assertIn("You are the **planner**, called back in the middle of a build", out)
        self.assertIn("- `%s`" % path(4), out)
        self.assertNotIn("- `%s`" % path(1), out)
        self.assertIn("`PLAN: READY`", out)

    def replan(self):
        repo = self.setup()
        rc, out = self.flow("replan-prompt")
        self.assertEqual(rc, 0, out)
        return repo

    def test_a_replan_that_folds_tickets_runs_on(self):
        repo = self.replan()
        repo.set_status(path(3), "parked (folded into 02)")
        text = repo.path(path(4)).read_text(encoding="utf-8").replace("Blocked by: 03", "Blocked by: 02")
        repo.path(path(4)).write_text(text, encoding="utf-8")
        repo.commit("plan(f): re-plan the open tickets")
        line = self.flow("next")[1]
        self.assertTrue(line.startswith("BUILD %s" % path(1)), line)
        self.assertIn("REPLAN", repo.log())
        self.assertEqual(repo.state().get("replan_sha", ""), "")

    def test_a_replan_that_changes_a_resolved_ticket_stops(self):
        repo = self.setup()
        repo.resolve(path(1))
        rc, out = self.flow("replan-prompt")
        self.assertEqual(rc, 0, out)
        text = repo.path(path(1)).read_text(encoding="utf-8").replace("body", "other body")
        repo.path(path(1)).write_text(text, encoding="utf-8")
        repo.commit("plan(f): re-plan the open tickets")
        rc, out = self.flow("next")
        self.assertEqual(rc, 1)
        self.assertIn("the re-plan changed %s, which was resolved before it" % path(1), out)

    def test_nothing_to_fold(self):
        self.setup(count=1)
        self.assertEqual(self.flow("replan-prompt"), (1, "STOP 1 open ticket(s) left, nothing to fold together"))


if __name__ == "__main__":
    unittest.main()
