"""Settings and mode rules (spec.md § Edge cases, rows handled in ticket 04) and the compatibility seam a test patches:
each compared with the old code, through the CLI or the public `Conductor` class."""

import unittest

from support import twins

LANES_WITH_RELAY = "STOP FLOW_RELAY hands off after every phase, which lanes cannot do. drop one of them"


class BadLanes(unittest.TestCase):
    # Edge case: A bad `FLOW_LANES` (`9`, `x`) -> Only `start` stops, with the same message as today (`FLOW_LANES must
    # be 1 to 4, not 9`, or `FLOW_LANES must be a whole number, not x`).
    def test_start_stops_on_a_bad_flow_lanes_with_todays_text(self):
        def scenario(w):
            w.got = [w.flow("start", FLOW_LANES="9"), w.flow("start", FLOW_LANES="x")]

        new = twins(self, scenario)
        self.assertEqual(new.got, [(1, "STOP FLOW_LANES must be 1 to 4, not 9"),
                                   (1, "STOP FLOW_LANES must be a whole number, not x")])

    # ... other commands ignore it, as today. Settings must not validate it eagerly.
    def test_other_commands_ignore_a_bad_flow_lanes(self):
        def scenario(w):
            w.start()
            w.got = [w.flow("next", FLOW_LANES="9"), w.flow("prompt", FLOW_LANES="x"),
                     w.flow("budget", FLOW_LANES="x")]

        new = twins(self, scenario)
        self.assertEqual(new.got[0][0], 0, new.got)
        self.assertTrue(new.got[0][1].startswith("BUILD plans/f/tasks/01-t.md 01 "), new.got)
        self.assertEqual([rc for rc, _ in new.got], [0, 0, 0], new.got)


class TwoBadSettings(unittest.TestCase):
    # Edge case: Two bad settings at once (a bad profile and `FLOW_MAX_RETRIES=x`) -> The same first STOP as today:
    # Settings checks in the order `Conductor.__init__` does now (profile, then the `_env_int` values, then the git
    # worktree, then the state folder).
    def test_a_bad_profile_stops_before_a_bad_number(self):
        def scenario(w):
            w.got = [w.flow("start", FLOW_PROFILE="bogus", FLOW_MAX_RETRIES="x"),
                     w.flow("next", FLOW_PROFILE="bogus", FLOW_MAX_RETRIES="x")]

        new = twins(self, scenario)
        self.assertEqual(new.got, [(1, "STOP the profile must be careful, fast, normal, not bogus")] * 2)

    def test_the_numbers_stop_in_todays_order(self):
        def scenario(w):
            w.got = [w.flow("start", FLOW_SMALL_LINES="y", FLOW_MAX_RETRIES="x"),
                     w.flow("start", FLOW_SMALL_LINES="y", FLOW_GATE_TIMEOUT="z")]

        new = twins(self, scenario)
        self.assertEqual(new.got, [(1, "STOP FLOW_MAX_RETRIES must be a whole number, not x"),
                                   (1, "STOP FLOW_GATE_TIMEOUT must be a whole number, not z")])

    def test_a_bad_number_stops_before_the_missing_git_worktree(self):
        def scenario(w):
            import shutil
            shutil.rmtree(str(w.dir / ".git"))
            w.got = [w.flow("start", FLOW_MAX_RETRIES="x"), w.flow("start")]

        new = twins(self, scenario)
        self.assertEqual(new.got, [(1, "STOP FLOW_MAX_RETRIES must be a whole number, not x"),
                                   (1, "STOP not inside a git worktree")])


class ModeRules(unittest.TestCase):
    """Edge case: `FLOW_LANES=2` with `FLOW_RELAY=1`, lanes from a subfolder, `FLOW_DRIVER=robot`, `FLOW_FAST=2` ->
    The same STOP text, from one rules table."""

    def test_lanes_with_relay(self):
        def scenario(w):
            w.got = w.flow("start", FLOW_LANES="2", FLOW_RELAY="1")

        self.assertEqual(twins(self, scenario).got, (1, LANES_WITH_RELAY))

    def test_lanes_with_relay_on_next(self):
        def scenario(w):
            w.start(FLOW_LANES="2")
            w.got = w.flow("next", FLOW_RELAY="1")

        self.assertEqual(twins(self, scenario).got, (1, LANES_WITH_RELAY))

    def test_lanes_from_a_subfolder(self):
        def scenario(w):
            (w.dir / "sub").mkdir()
            w.got = w.flow("start", cwd=w.dir / "sub", FLOW_LANES="2", FLOW_DIR="../plans")
            w.top = str(w.dir.resolve())

        new = twins(self, scenario)
        self.assertEqual(new.got, (1, "STOP run the conductor from the top of the repo (%s) to use lanes" % new.top))

    def test_flow_driver_robot(self):
        def scenario(w):
            w.got = w.flow("start", FLOW_DRIVER="robot")

        self.assertEqual(twins(self, scenario).got, (1, "STOP FLOW_DRIVER must be person or agent, not robot"))

    def test_flow_fast_2(self):
        def scenario(w):
            w.got = w.flow("start", FLOW_FAST="2")

        self.assertEqual(twins(self, scenario).got, (1, "STOP FLOW_FAST must be 1 or 0, not 2"))

    def test_batch_preconditions(self):
        # a batch needs fast mode with the gate on and no relay: only the last of these runs takes a batch
        def scenario(w):
            for env in ({"FLOW_FAST": "1", "FLOW_GATE": "off"}, {"FLOW_FAST": "1", "FLOW_RELAY": "1"},
                        {"FLOW_FAST": "0"}, {"FLOW_FAST": "1"}):
                w.flow("reset", FLOW_TAKEOVER="1")
                w.start(FLOW_TAKEOVER="1", **env)
                if w.flow("next", **env)[1].startswith("HANDOFF"):
                    w.start(**env)
                    w.flow("next", **env)
                w.flow("prompt", **env)

        new = twins(self, scenario, tickets=(("01", "—", ("Level: 1", "Touches: t01/")),
                                             ("02", "—", ("Level: 1", "Touches: t02/"))))
        log = (new.dir / ".feature-flow/state/flow-f.log").read_text(encoding="utf-8")
        self.assertEqual(log.count(",BATCH "), 1, log)  # only the last run, fast with the gate on and no relay
        self.assertIn(",BATCH ", log.rsplit(",RESET", 1)[1])


PER_SESSION = "from feature_flow.conductor import Conductor\nprint(Conductor('f', 'scripts').per_session)"


class PerSession(unittest.TestCase):
    # Edge case: An agent driver with no `FLOW_TICKETS_PER_SESSION` or one filled by a profile -> `per_session` is 0,
    # as today (`test_agent_driven` reads `Conductor('f', 'scripts').per_session`).
    def test_an_agent_driver_has_no_session_limit_unless_it_sets_one(self):
        def scenario(w):
            w.got = [w.python(PER_SESSION, FLOW_DRIVER="agent")[1],
                     w.python(PER_SESSION, FLOW_DRIVER="agent", FLOW_PROFILE="careful")[1],
                     w.python(PER_SESSION, FLOW_DRIVER="agent", FLOW_TICKETS_PER_SESSION="5")[1],
                     w.python(PER_SESSION)[1],
                     w.python(PER_SESSION, FLOW_PROFILE="fast")[1]]

        self.assertEqual(twins(self, scenario).got, ["0", "0", "5", "4", "6"])


PATCHED_NEXT = """from unittest import mock
from feature_flow import conductor
with mock.patch.object(conductor.Conductor, "check_code", lambda self, *a, **k: None):
    try:
        print(conductor.Conductor('f', 'scripts').next())
    except conductor.Stop as err:
        print("STOP %s" % err)
"""


class CheckCodeSeam(unittest.TestCase):
    # Edge case: A test that patches `Conductor.check_code` (`tests/py/test_proof.py`) -> Still disables the code
    # check: every phase calls `check_code` through the Conductor instance. (Interfaces: `mock.patch.object(
    # conductor.Conductor, "check_code", ...)` still turns it off.)
    def test_patching_check_code_on_the_class_turns_the_code_check_off(self):
        def change_flow_code(where):
            with open(str(where / "feature_flow" / "git.py"), "a", encoding="utf-8") as handle:
                handle.write("# changed mid-ticket\n")

        def scenario(w):
            w.start()
            w.flow("next")
            w.resolve("plans/f/tasks/01-t.md", extra=change_flow_code)
            w.got = w.python(PATCHED_NEXT)[1]

        new = twins(self, scenario)
        self.assertFalse(new.got.startswith("STOP flow code changed"), new.got)
        self.assertTrue(new.got.split(" ", 1)[0] in ("BUILD", "REVIEW"), new.got)


if __name__ == "__main__":
    unittest.main()
