"""Story: a user runs the flow (spec.md § Stories), the happy path, and acceptance tests A3 and A4. Every test drives
`python3 scripts/flow.py f <command>` in throwaway repos and compares the current code with the old code."""

import unittest

from support import World, current_code, old_code, put_code, twins, NoOldCode

MAJORS = "1. major: the name is unclear\n2. minor: a nit\n\nREVIEW: FAIL\n"


class Commands(unittest.TestCase):
    # - [ ] The CLI and its 17 commands take the same arguments and print the same lines (BUILD, REVIEW, ASK, TEST,
    #   WAIT, HANDOFF, DONE, OK, RETRY, SCOUT, NONE, PLAN, STOP), byte for byte, with the same exit codes (0, 1 for
    #   STOP, 2 for NoPhase and usage).
    def test_the_17_commands_print_the_same_lines_with_the_same_exit_codes(self):
        def scenario(w):
            brief = w.side_file("brief.md", "# Brief\n\nAdd a thing.\n")
            question = w.side_file("question.md", "Which way?\n")
            empty = w.side_file("empty.txt", "no verdict here\n")
            w.run()  # usage
            w.run("bogus")  # an unknown command
            w.run("verdict")  # a missing argument
            w.run("fast", "maybe", "x")
            w.flow("prompt")  # nothing pending: NoPhase
            w.flow("verdict", empty)
            w.flow("plan-prompt", brief)
            w.flow("plan-scouts", brief)
            w.flow("plan-scout-prompt", "1")
            w.flow("plan-review-prompt")
            w.flow("consult-prompt", "po", question)
            w.flow("brainstorm-prompt", "po", question)
            w.start()
            w.flow("budget")
            w.flow("budget", "30")
            w.flow("budget", "off")
            w.flow("fast", "on")
            w.flow("fast", "off")
            w.flow("replan-prompt")
            w.flow("next")  # BUILD 01
            w.flow("scouts")
            w.flow("scout-prompt", "1")
            w.flow("prompt")
            w.flow("verdict", empty)  # no review pending
            w.resolve("plans/f/tasks/01-t.md")
            w.flow("next")  # REVIEW 01
            w.flow("prompt")
            w.flow("verdict", empty)  # RETRY no review verdict
            w.flow("next")
            w.flow("verdict", w.side_file("reply.txt", "fine\nREVIEW: PASS\n"))
            w.flow("next")  # BUILD 02
            w.flow("reset", "02")
            w.flow("reset")
            w.flow("plan-accept")

        new = twins(self, scenario)
        codes = [line.split("\n", 1)[0].rsplit(" ", 1)[1] for line in new.lines]
        self.assertEqual(codes[:6], ["2", "2", "2", "2", "2", "2"])

    # - [ ] Every `STOP` message is the same text.
    def test_every_stop_message_is_the_same_text(self):
        def scenario(w):
            w.start()
            token = w.env.pop("FLOW_SESSION")
            w.flow("start")  # owned by a session
            w.flow("next")  # no token
            w.env["FLOW_SESSION"] = token
            w.flow("next", "1")  # no lanes
            w.flow("next", FLOW_DIR="nowhere")  # no plan folder
            w.flow("next")  # BUILD 01
            (w.dir / "stray.txt").write_text("x\n", encoding="utf-8")
            w.resolve("plans/f/tasks/01-t.md", commit=False)
            w.flow("next")  # dirty after the build
            w.git("add", "-A")
            w.git("commit", "-qm", "feat: 01")
            w.flow("next", FLOW_MAX_RETRIES="x")
            w.flow("reset")
            w.start(FLOW_TAKEOVER="1")
            w.flow("next", FLOW_MAX_RETRIES="1")  # BUILD 02
            w.flow("next", FLOW_MAX_RETRIES="1")  # still unresolved
            (w.dir / ".feature-flow/state/flow-f.state").write_bytes(b"phase=\xff\xfe\n")
            w.flow("next")  # damaged

        new = twins(self, scenario)
        self.assertTrue(any("\nSTOP " in line for line in new.lines))

    # - [ ] The state file has the same keys and the same `key=value` format; the log has the same events; findings
    #   files, the ticket sections and `followups.md` text the conductor writes are the same.
    # Edge case: A level 2 ticket past `FULL_ROUNDS` with only majors -> Passes with follow-ups, as `judge_review`
    # does now.
    def test_state_log_findings_ticket_sections_and_followups_are_the_same(self):
        def scenario(w):
            w.start()
            w.last = w.drive(verdict=lambda world, n: MAJORS)

        new = twins(self, scenario, tickets=(("01", "—", ("Level: 2", "Touches: t01/")),),
                    env={"FLOW_TICKETS_PER_SESSION": "99"})
        self.assertTrue(new.last.startswith("DONE f is complete: 1 ticket(s) resolved in this run; 1 passed with "
                                            "follow-ups in plans/f/followups.md"), new.last)
        self.assertIn("1. major: the name is unclear", (new.dir / "plans/f/followups.md").read_text(encoding="utf-8"))


class HappyPath(unittest.TestCase):
    # Happy path 1: `python3 scripts/flow.py f next` -> ... the session sees the same `BUILD ...` / `REVIEW ...` line
    # as before. Happy path 3: When no ticket is left, the shared EndOfRun step runs the acceptance tests, the feature
    # review for deferred tickets, and prints the same `DONE` line.
    def test_a_serial_run_with_acceptance_tests_ends_with_the_same_done_line(self):
        def scenario(w):
            w.start()
            w.last = w.drive()

        new = twins(self, scenario, acceptance=True, env={"FLOW_TICKETS_PER_SESSION": "99"})
        self.assertTrue(new.last.startswith("DONE f is complete: 2 ticket(s) resolved in this run"), new.last)
        self.assertTrue(any("\nTEST plans/f " in line for line in new.lines))
        self.assertTrue(any("\nBUILD plans/f/tasks/01-t.md 01 " in line for line in new.lines))
        self.assertTrue(any("\nREVIEW plans/f/tasks/02-t.md 02 " in line for line in new.lines))

    def test_a_fast_run_defers_reviews_to_one_feature_review_then_done(self):
        def scenario(w):
            w.start(FLOW_FAST="1")
            w.last = w.drive()

        new = twins(self, scenario, acceptance=True, env={"FLOW_TICKETS_PER_SESSION": "99"},
                    tickets=(("01", "—", ("Level: 1", "Touches: t01/")), ("02", "01", ("Level: 2", "Touches: t02/"))))
        self.assertTrue(any("\nREVIEW plans/f all " in line for line in new.lines))
        self.assertTrue(new.last.startswith("DONE f is complete"), new.last)

    # Edge case: A batch -> Its tickets go through the same check pipeline without the gate, as `judge_batch` does now.
    def test_a_batch_is_judged_as_today(self):
        def scenario(w):
            w.start(FLOW_FAST="1")
            w.last = w.drive()

        new = twins(self, scenario, env={"FLOW_TICKETS_PER_SESSION": "99"},
                    tickets=(("01", "—", ("Level: 1", "Touches: t01/")), ("02", "—", ("Level: 1", "Touches: t02/")),
                             ("03", "—", ("Level: 2", "Touches: t03/"))))
        self.assertIn("BATCH", (new.dir / ".feature-flow/state/flow-f.log").read_text(encoding="utf-8"))
        self.assertTrue(new.last.startswith("DONE f is complete: 3 ticket(s)"), new.last)

    # Edge case: `FLOW_RELAY=1` -> `HANDOFF` after each phase, checked before any judging, as `next` does now.
    def test_relay_hands_off_after_each_phase(self):
        def scenario(w):
            w.start(FLOW_RELAY="1")
            w.last = w.drive(FLOW_RELAY="1", limit=80)

        new = twins(self, scenario, acceptance=True, env={"FLOW_TICKETS_PER_SESSION": "99"})
        self.assertGreaterEqual(sum("\nHANDOFF " in line for line in new.lines), 4)
        self.assertTrue(new.last.startswith("DONE f is complete"), new.last)

    # Edge case: `pick_ticket` and `dispatch` at the end -> Their differences stay: `pick_ticket` checks tests due
    # before `--next` (serial half; the lane half is in test_rebuild_lanes.py).
    def test_serial_run_hands_out_the_tests_before_the_first_ticket(self):
        def scenario(w):
            w.start()
            w.flow("next")

        new = twins(self, scenario, acceptance=True)
        self.assertIn("\nTEST plans/f ", new.lines[-1])


class Resume(unittest.TestCase):
    def old(self):
        try:
            return old_code()
        except NoOldCode as err:
            why = str(err)
        self.fail(why)

    # - [ ] A run paused between tickets (at a `HANDOFF`) on the old code goes on with the new code: `start` then
    #   `next` print the same lines (shas, tokens and paths replaced) as a twin run that stayed on the old code
    #   (acceptance test A3).
    # Edge case: A run paused between tickets (at a `HANDOFF`) on the old code -> `start` and `next` on the new code
    # print what the old code would have.
    def test_a3_a_run_paused_at_a_handoff_on_the_old_code_goes_on_with_the_new_code(self):
        old = self.old()
        worlds = []
        for _ in range(2):
            w = World(self, old, env={"FLOW_TICKETS_PER_SESSION": "1"})
            w.start()
            self.assertTrue(w.flow("next")[1].startswith("BUILD plans/f/tasks/01-t.md 01 "))
            w.resolve("plans/f/tasks/01-t.md")
            self.assertTrue(w.flow("next")[1].startswith("REVIEW plans/f/tasks/01-t.md 01 "))
            self.assertEqual(w.flow("verdict", w.side_file("reply.txt", "fine\nREVIEW: PASS\n")), (0, "OK"))
            self.assertTrue(w.flow("next")[1].startswith("HANDOFF "))
            worlds.append(w)
        moved, stayed = worlds
        put_code(moved.dir, current_code())
        moved.git("add", "-A")
        moved.git("commit", "-q", "--allow-empty", "-m", "upgrade")  # empty only when the code did not change
        stayed.git("commit", "-q", "--allow-empty", "-m", "upgrade")
        moved.lines, stayed.lines = [], []
        for w in worlds:
            w.start()
            w.flow("next")
        self.assertEqual(moved.lines, stayed.lines)
        self.assertTrue(moved.lines[-1].split("\n")[1].startswith("BUILD plans/f/tasks/02-t.md 02 "), moved.lines)

    # - [ ] A run paused mid-ticket keeps today's behaviour, with nothing built for it: `Conductor.check_code` stops
    #   `next` with `STOP flow code changed while building <ticket>: ...` ... Acceptance test A4 checks that this STOP,
    #   and not an `is damaged` STOP, is what such a run meets.
    # Edge case: A run paused mid-ticket on the old code (any phase, any lane) -> `check_code` stops with today's
    # `flow code changed while building ...` text.
    def test_a4_a_run_paused_mid_ticket_meets_the_flow_code_changed_stop(self):
        w = World(self, self.old())
        w.start()
        self.assertTrue(w.flow("next")[1].startswith("BUILD plans/f/tasks/01-t.md 01 "))
        w.resolve("plans/f/tasks/01-t.md", extra=lambda where: put_code(where, current_code()))
        self.assertEqual(w.git("status", "--porcelain"), "")
        rc, out = w.flow("next")
        self.assertEqual(rc, 1, out)
        self.assertTrue(out.startswith("STOP flow code changed while building"), out)
        self.assertNotIn("is damaged", out)


if __name__ == "__main__":
    unittest.main()
