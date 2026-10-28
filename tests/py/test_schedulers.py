"""The schedulers: the serial one hands out the lowest ready ticket and ends through the shared end of run, the
batch one picks what a builder may build together, and the end of run keeps its order (the tester, the
acceptance run, the feature review, DONE). Run in process on throwaway repos."""

import contextlib
import io
import os
import sys
import unittest
from unittest import mock

import helpers
from helpers import Repo

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import lanes  # the package under test, from this checkout
from feature_flow.conductor import Conductor
from feature_flow.conductor.phases.final import Final
from feature_flow.conductor.phases.test import Test
from feature_flow.conductor.schedulers import BatchScheduler, EndOfRun, SerialScheduler

T = "plans/f/tasks/%s.md"


def ticket(title, header=()):
    blocked = [h for h in header if h.startswith("Blocked by:")] or ["Blocked by: —"]
    lines = ["# %s\n" % title, "Type: task", "Status: open"] + blocked + ["Test first: no"]
    return "\n".join(lines + [h for h in header if not h.startswith("Blocked by:")]) + "\n\nbody\n\n## Done when\n\n- x\n\n## Answer\n"


class Run:
    """A throwaway repo with the given tickets ({slug: header lines}) and commands.md lines, and a Conductor on
    it built in process with only the given FLOW_ settings."""

    def __init__(self, test, tickets, commands="", **env):
        self.repo = repo = Repo(tickets=())
        test.addCleanup(repo.close)
        repo.path("plans/f/commands.md").write_text("# Commands: f\n\n" + commands, encoding="utf-8")
        for slug, header in tickets.items():
            repo.path(T % slug).write_text(ticket(slug, header), encoding="utf-8")
        repo.commit("plan")
        self.env = dict({k: v for k, v in os.environ.items() if not k.startswith("FLOW_")},
                        FLOW_TRUSTED="1", **env)
        stack = contextlib.ExitStack()
        test.addCleanup(stack.close)
        here = os.getcwd()
        os.chdir(str(repo.dir))
        stack.callback(os.chdir, here)
        stack.enter_context(mock.patch.dict(os.environ, self.env, clear=True))
        stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
        self.c = Conductor("f", str(repo.path("scripts")))


class Serial(unittest.TestCase):
    def test_hands_out_the_lowest_ready_ticket(self):
        run = Run(self, {"03-c": (), "01-a": ["Blocked by: 02"], "02-b": ()})
        line = SerialScheduler(run.c).next(None)
        self.assertTrue(line.startswith("BUILD %s 02 " % (T % "02-b")), line)
        self.assertEqual((run.c.get("phase"), run.c.get("num")), ("build", "02"))

    def test_finishes_through_the_end_of_run(self):
        run = Run(self, {"01-a": ()})
        run.repo.resolve(T % "01-a")
        with mock.patch.object(EndOfRun, "finish", autospec=True, side_effect=EndOfRun.finish) as finish:
            line = SerialScheduler(run.c).next(None)
        self.assertEqual(finish.call_count, 1)
        self.assertTrue(line.startswith("DONE f is complete: 0 ticket(s) resolved"), line)

    def test_a_pass_counts_the_ticket_and_resumes_with_the_next(self):
        run = Run(self, {"01-a": (), "02-b": ()})
        sched = SerialScheduler(run.c)
        sched.next(None)
        run.repo.resolve(T % "01-a")
        line = sched.on_passed(run.c)
        self.assertTrue(line.startswith("BUILD %s 02 " % (T % "02-b")), line)
        self.assertEqual((run.c.num("done"), run.c.num("session_done")), (1, 1))

    def test_the_facade_picks_its_scheduler_once_per_call(self):
        run = Run(self, {"01-a": ()})
        sched = run.c.scheduler()
        self.assertIsInstance(sched, SerialScheduler)
        self.assertIs(run.c.scheduler(), sched)


class BatchFor(unittest.TestCase):
    SMALL = ["Level: 1"]

    def choose(self, tickets, commands="", fast="1", no_batch="", session_done=0, **env):
        run = Run(self, tickets, commands, FLOW_TICKETS_PER_SESSION="4", **env)
        run.c.all["fast"] = fast
        run.c.all["no_batch"] = no_batch
        run.c.st["session_done"] = session_done
        first = T % sorted(tickets)[0]
        return [os.path.basename(p)[:-3] for p in BatchScheduler(run.c).batch_for(first)]

    def test_the_table(self):
        small = self.SMALL
        rows = [
            ("disjoint small tickets go together",
             dict(tickets={"01-a": small + ["Touches: a/"], "02-b": ["Level: 2", "Touches: b/"],
                           "03-c": small + ["Touches: c/"]}),
             ["02-b", "03-c"]),
            ("a first ticket of level 3 builds alone",
             dict(tickets={"01-a": ["Level: 3", "Touches: a/"], "02-b": small + ["Touches: b/"]}), []),
            ("a first ticket without Touches builds alone",
             dict(tickets={"01-a": small, "02-b": small + ["Touches: b/"]}), []),
            ("a ticket without Touches or of level 3 is left out",
             dict(tickets={"01-a": small + ["Touches: a/"], "02-b": small, "03-c": ["Level: 3", "Touches: c/"],
                           "04-d": small + ["Touches: d/"]}),
             ["04-d"]),
            ("a ticket that touches what another touches is left out",
             dict(tickets={"01-a": small + ["Touches: a/"], "02-b": small + ["Touches: a/x.py"],
                           "03-c": small + ["Touches: c/"]}),
             ["03-c"]),
            ("a ticket on a Sensitive path is left out",
             dict(tickets={"01-a": small + ["Touches: a/"], "02-b": small + ["Touches: secret/x.py"],
                           "03-c": small + ["Touches: c/"]}, commands="Sensitive: secret/\n"),
             ["03-c"]),
            ("a first ticket on a Sensitive path builds alone",
             dict(tickets={"01-a": small + ["Touches: secret/"], "02-b": small + ["Touches: b/"]},
                  commands="Sensitive: secret/\n"), []),
            ("a ticket sent back from a batch builds alone",
             dict(tickets={"01-a": small + ["Touches: a/"], "02-b": small + ["Touches: b/"],
                           "03-c": small + ["Touches: c/"]}, no_batch="02"),
             ["03-c"]),
            ("a first ticket sent back from a batch builds alone",
             dict(tickets={"01-a": small + ["Touches: a/"], "02-b": small + ["Touches: b/"]}, no_batch="01"), []),
            ("the room left in the session caps the batch",
             dict(tickets={"01-a": small + ["Touches: a/"], "02-b": small + ["Touches: b/"],
                           "03-c": small + ["Touches: c/"]}, session_done=2),
             ["02-b"]),
            ("one ticket of room left is no batch",
             dict(tickets={"01-a": small + ["Touches: a/"], "02-b": small + ["Touches: b/"]}, session_done=3), []),
            ("FLOW_BATCH caps the batch",
             dict(tickets={"01-a": small + ["Touches: a/"], "02-b": small + ["Touches: b/"],
                           "03-c": small + ["Touches: c/"]}, FLOW_BATCH="2"),
             ["02-b"]),
            ("no batch outside fast mode",
             dict(tickets={"01-a": small + ["Touches: a/"], "02-b": small + ["Touches: b/"]}, fast=""), []),
            ("no batch with the gate off",
             dict(tickets={"01-a": small + ["Touches: a/"], "02-b": small + ["Touches: b/"]}, FLOW_GATE="off"), []),
        ]
        for name, kw, want in rows:
            with self.subTest(name):
                self.assertEqual(self.choose(**kw), want)


class EndOrder(unittest.TestCase):
    """With every step due, the end of run takes them in order: each one is reached only when the ones before it
    have nothing left."""

    def test_tester_then_acceptance_then_feature_review_then_done(self):
        run = Run(self, {"01-a": ()})
        run.repo.resolve(T % "01-a")
        calls = []
        due = {"tests": True, "accept": "BUILD acceptance fixes", "final": True}

        def step(name, line):
            def record(*args, **kw):
                calls.append(name)
                return line()
            return record

        with mock.patch.object(EndOfRun, "tests_due", step("tests_due", lambda: due["tests"])), \
                mock.patch.object(Test, "hand_out", step("tester", lambda: "TEST")), \
                mock.patch.object(EndOfRun, "check_acceptance", step("acceptance", lambda: due["accept"])), \
                mock.patch.object(Conductor, "deferred", step("deferred", lambda: [("01", "x")] if due["final"] else [])), \
                mock.patch.object(Final, "hand_out", step("final", lambda: "REVIEW all")):
            lines = []
            for key, off in (("tests", False), ("accept", None), ("final", False), (None, None)):
                lines.append(SerialScheduler(run.c).next(None))
                if key:
                    due[key] = off
        self.assertEqual(lines[0], "TEST")
        self.assertEqual(lines[1], "BUILD acceptance fixes")
        self.assertEqual(lines[2], "REVIEW all")
        self.assertTrue(lines[3].startswith("DONE f is complete"), lines[3])
        self.assertEqual(calls, ["tests_due", "tester",
                                 "tests_due", "acceptance",
                                 "tests_due", "acceptance", "deferred", "final",
                                 "tests_due", "acceptance", "deferred"])

    def test_a_serial_done_clears_the_phase_and_the_owner(self):
        run = Run(self, {"01-a": ()})
        run.repo.resolve(T % "01-a")
        run.c.st.update({"owner": "someone", "phase": "build"})
        with mock.patch.object(lanes, "remove_all") as remove:
            line = SerialScheduler(run.c).end.finish()
        self.assertTrue(line.startswith("DONE "), line)
        self.assertEqual((run.c.all.get("owner"), run.c.all.get("phase")), ("", ""))
        remove.assert_not_called()

    def test_a_lane_done_removes_the_lanes_and_clears_the_owner(self):
        run = Run(self, {"01-a": ()})
        run.repo.resolve(T % "01-a")
        run.c.all.update({"owner": "someone", "lanes": 2})
        sched = run.c.scheduler()
        self.assertNotIsInstance(sched, BatchScheduler)
        with mock.patch.object(lanes, "remove_all") as remove:
            line = sched.end.finish()
        self.assertTrue(line.startswith("DONE "), line)
        self.assertEqual(run.c.all.get("owner"), "")
        remove.assert_called_once_with(run.c.top, "f")


if __name__ == "__main__":
    unittest.main()
