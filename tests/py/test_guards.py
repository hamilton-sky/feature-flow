"""The guards: BEFORE_TICKET, the ordered checks both schedulers run before a ticket starts (the session handoff,
the re-plan check, the budget, the smoke test), where the first one that stops or hands off wins; the lane
variants (WAIT beside busy lanes, the re-plan check and the budget offer only with no lane busy); and AFTER_PHASE,
the relay, which hands off before next judges anything."""

import os
import sys
import unittest
from unittest import mock

import helpers
from test_schedulers import Run, T

sys.path.insert(0, str(helpers.ROOT))
from feature_flow.conductor import budget, guards  # the package under test, from this checkout
from feature_flow.conductor.errors import Stop
from feature_flow.conductor.phases import REGISTRY
from feature_flow.conductor.schedulers import LaneScheduler, SerialScheduler


class Fake:
    """Just enough of a conductor for the guards: the session limit, the tickets done, the relay flag."""

    def __init__(self, per_session=0, session_done=0, relay_handoff=""):
        self.per_session = per_session
        self.settings = mock.Mock(base_gate=False)
        self.values = {"session_done": session_done, "relay_handoff": relay_handoff}
        self.calls = []

    def num(self, key):
        return int(self.values.get(key) or 0)

    def get(self, key, default=""):
        return self.values.get(key, default)

    def handoff(self):
        self.calls.append("handoff")
        return "HANDOFF flow f"

    def emit(self, line):
        self.calls.append("emit")
        return line


class Recorded(unittest.TestCase):
    """The re-plan check, the budget and the smoke test replaced by recorders."""

    def setUp(self):
        self.calls = []
        for target, name in ((guards, "check_replan"), (budget, "check_budget"), (guards, "run_smoke")):
            patcher = mock.patch.object(target, name, side_effect=self.recorder(name))
            patcher.start()
            self.addCleanup(patcher.stop)

    def recorder(self, name):
        def record(c, *args, **kw):
            self.calls.append((name,) + args + tuple(sorted(kw.items())))
        return record


class Order(Recorded):
    def test_five_guards_in_order(self):
        self.assertEqual([g.name for g in guards.BEFORE_TICKET], ["session", "replan", "budget", "base", "smoke"])
        self.assertEqual([g.stage for g in guards.BEFORE_TICKET], ["pick", "pick", "pick", "pick", "start"])

    def test_all_pass_and_run_in_order(self):
        c = Fake()
        self.assertIsNone(guards.before_ticket(c))
        self.assertEqual(self.calls, [("check_replan",), ("check_budget", ("offer", True))])
        self.assertIsNone(guards.before_ticket(c, stage="start"))
        self.assertEqual(self.calls[-1], ("run_smoke",))
        self.assertEqual(c.calls, [])

    def test_the_session_handoff_wins_and_the_later_ones_do_not_run(self):
        c = Fake(per_session=2, session_done=2)
        self.assertEqual(guards.before_ticket(c), "HANDOFF flow f")
        self.assertEqual(c.calls, ["handoff"])
        self.assertEqual(self.calls, [])

    def test_a_replan_stop_wins_over_the_budget(self):
        def stop(c):
            self.calls.append(("check_replan",))
            raise Stop("the re-plan changed x")

        guards.check_replan.side_effect = stop
        with self.assertRaises(Stop):
            guards.before_ticket(Fake())
        self.assertEqual(self.calls, [("check_replan",)])

    def test_only_runs_the_named_guards_in_their_order(self):
        c = Fake(per_session=1, session_done=5)
        self.assertIsNone(guards.before_ticket(c, only=("budget", "replan")))
        self.assertEqual(self.calls, [("check_replan",), ("check_budget", ("offer", True))])
        self.assertEqual(c.calls, [])


class LaneVariants(Recorded):
    def test_with_busy_lanes_the_session_limit_waits(self):
        c = Fake(per_session=3, session_done=1)
        self.assertEqual(guards.before_ticket(c, busy=[1, 3]), "WAIT 1,3")
        self.assertEqual(c.calls, ["emit"])
        self.assertEqual(self.calls, [])

    def test_with_no_lane_busy_the_session_limit_hands_off(self):
        c = Fake(per_session=1, session_done=1)
        self.assertEqual(guards.before_ticket(c, busy=[]), "HANDOFF flow f")

    def test_busy_lanes_count_towards_the_session_limit(self):
        self.assertIsNone(guards.before_ticket(Fake(per_session=3, session_done=1), busy=[2], only=("session",)))
        self.assertEqual(guards.before_ticket(Fake(per_session=3, session_done=1), busy=[1, 2], only=("session",)),
                         "WAIT 1,2")

    def test_with_busy_lanes_no_replan_check_and_no_budget_offer(self):
        self.assertIsNone(guards.before_ticket(Fake(), busy=[2]))
        self.assertEqual(self.calls, [("check_budget", ("offer", False))])

    def dispatch(self, tickets, busy):
        """dispatch in a run of 2 lanes, busy mapping a lane to a ticket slug in build, with lease recorded."""
        run = Run(self, tickets, FLOW_TICKETS_PER_SESSION="4")
        run.c.all["lanes"] = 2
        for k, slug in busy.items():
            run.c.all.update({"L%d.ticket" % k: T % slug, "L%d.num" % k: slug[:2], "L%d.phase" % k: "build"})
        leased = []

        def lease(sched, k, path):
            leased.append((k, os.path.basename(path)[:-3]))
            return "LEASED %d" % k

        with mock.patch.object(LaneScheduler, "lease", autospec=True, side_effect=lease):
            return run.c.scheduler().dispatch(), leased

    def test_dispatch_beside_a_busy_lane(self):
        one = ["Level: 1"]
        line, leased = self.dispatch({"01-a": one + ["Touches: a/"], "02-b": one + ["Touches: b/"]}, {1: "01-a"})
        self.assertEqual((line, leased), ("LEASED 2", [(2, "02-b")]))
        self.assertEqual(self.calls, [("check_budget", ("offer", False))])

    def test_dispatch_with_no_lane_busy(self):
        line, leased = self.dispatch({"01-a": ["Level: 1", "Touches: a/"]}, {})
        self.assertEqual((line, leased), ("LEASED 1", [(1, "01-a")]))
        self.assertEqual(self.calls, [("check_replan",), ("check_budget", ("offer", True))])


class Serial(Recorded):
    def test_pick_ticket_runs_the_guards_then_the_smoke_after_the_snapshot(self):
        run = Run(self, {"01-a": ()})
        seen = []
        guards.run_smoke.side_effect = lambda c: seen.append(c.get("code_sha"))
        line = SerialScheduler(run.c).next(None)
        self.assertTrue(line.startswith("BUILD %s 01 " % (T % "01-a")), line)
        self.assertEqual(self.calls, [("check_replan",), ("check_budget", ("offer", True))])
        self.assertEqual(len(seen), 1)
        self.assertTrue(seen[0])

    def test_pick_ticket_hands_off_at_the_session_limit_before_the_other_guards(self):
        run = Run(self, {"01-a": ()}, FLOW_TICKETS_PER_SESSION="1")
        run.c.st["session_done"] = 1
        line = SerialScheduler(run.c).next(None)
        self.assertTrue(line.startswith("HANDOFF "), line)
        self.assertEqual(self.calls, [])


class Relay(unittest.TestCase):
    def test_after_phase_hands_off_when_the_relay_flag_is_set(self):
        c = Fake(relay_handoff="1")
        self.assertEqual(guards.after_phase(c), "HANDOFF flow f")
        self.assertIsNone(guards.after_phase(Fake()))

    def test_handing_out_a_phase_sets_the_flag_only_with_the_relay_on(self):
        for relay, want in ((True, "1"), (False, "")):
            view = {"relay_handoff": "x"}
            guards.mark_relay(mock.Mock(relay=relay), view)
            self.assertEqual(view["relay_handoff"], want)

    def judged(self, phase, **env):
        run = Run(self, {"01-a": ()}, **env)
        run.c.all.update({"phase": phase, "ticket": T % "01-a", "num": "01", "relay_handoff": "1"})
        run.c.save()
        judge = mock.Mock(side_effect=AssertionError("judged before the relay handoff"))
        with mock.patch.object(REGISTRY[phase], "judge", judge):
            line = run.c.next()
        return run, line, judge

    def test_next_hands_off_before_it_judges_a_ticket_phase(self):
        run, line, judge = self.judged("build", FLOW_RELAY="1")
        self.assertTrue(line.startswith("HANDOFF "), line)
        self.assertEqual(judge.call_count, 0)
        self.assertEqual(run.c.get("relay_handoff"), "")

    def test_next_hands_off_before_it_judges_a_run_wide_phase(self):
        run, line, judge = self.judged("test", FLOW_RELAY="1")
        self.assertTrue(line.startswith("HANDOFF "), line)
        self.assertEqual(judge.call_count, 0)

    def test_a_build_handed_out_under_relay_hands_off_on_the_next_call(self):
        run = Run(self, {"01-a": ()}, FLOW_RELAY="1")
        with mock.patch.object(guards, "run_smoke"):
            line = run.c.next()
        self.assertTrue(line.startswith("BUILD "), line)
        self.assertEqual(run.c.get("relay_handoff"), "1")
        self.assertTrue(run.c.next().startswith("HANDOFF "))


if __name__ == "__main__":
    unittest.main()
