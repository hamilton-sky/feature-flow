"""Story: a maintainer adds a mode (spec.md § Stories). Each phase, scheduler, guard and rule in its own small module,
found through the names spec.md § Interfaces gives; the pure policy functions return today's level, reason,
decision and notes."""

import dataclasses
import importlib
import inspect
import pkgutil
import sys
import unittest

from support import ROOT

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load(test, name):
    try:
        return importlib.import_module(name)
    except ImportError as err:
        test.fail("cannot import %s: %s" % (name, err))


def find(test, package, name):
    """The object called name in package or one of its modules (the spec names the folder, not the file)."""
    pkg = load(test, package)
    if hasattr(pkg, name):
        return getattr(pkg, name)
    for info in pkgutil.iter_modules(getattr(pkg, "__path__", [])):
        module = load(test, "%s.%s" % (package, info.name))
        if hasattr(module, name):
            return getattr(module, name)
    test.fail("no %s in %s" % (name, package))


class Layout(unittest.TestCase):
    # - [ ] Each phase (build, review, ask, test, final) is a class in `feature_flow/conductor/phases/` (new), found
    #   through one registry; `next`, `prompt`, `verdict`, `scouts`, `pending_phase` and `phase_key` route through it.
    def test_each_phase_is_a_class_in_phases_found_through_one_registry(self):
        registry = find(self, "feature_flow.conductor.phases", "REGISTRY")
        for word in ("build", "review", "ask", "test", "final"):
            self.assertIn(word, registry)
            self.assertTrue(inspect.isclass(registry[word]), "%s is not a class" % word)
            self.assertTrue(registry[word].__module__.startswith("feature_flow.conductor.phases"),
                            registry[word].__module__)
        self.assertTrue(find(self, "feature_flow.conductor.phases", "TRANSITIONS"))

    # - [ ] Serial, batch and lane runs are scheduler classes in `feature_flow/conductor/schedulers/` (new), chosen once
    #   per call; the end of a run (acceptance tests due, the acceptance run, the feature review, `DONE`) is one shared
    #   step.
    def test_serial_batch_and_lane_runs_are_scheduler_classes_with_one_end_of_run(self):
        for name in ("SerialScheduler", "BatchScheduler", "LaneScheduler", "EndOfRun"):
            found = find(self, "feature_flow.conductor.schedulers", name)
            self.assertTrue(inspect.isclass(found), "%s is not a class" % name)
        for name in ("SerialScheduler", "BatchScheduler", "LaneScheduler"):
            cls = find(self, "feature_flow.conductor.schedulers", name)
            for method in ("next", "on_passed", "resume"):
                self.assertTrue(callable(getattr(cls, method, None)), "%s has no %s" % (name, method))

    # - [ ] Which modes may run together is one table in `feature_flow/conductor/settings.py` (new), with a test per row.
    #   (Interfaces: `Settings`, a frozen dataclass; `MODE_RULES`, one table of mode rules: lanes vs relay, batch
    #   preconditions, lanes need the repo top, the `FLOW_LANES` range, `FLOW_DRIVER` and `FLOW_FAST` values.)
    def test_settings_is_a_frozen_dataclass_and_mode_rules_one_table(self):
        settings = load(self, "feature_flow.conductor.settings")
        self.assertTrue(dataclasses.is_dataclass(settings.Settings))
        fields = dataclasses.fields(settings.Settings)
        self.assertTrue(fields)
        blank = object.__new__(settings.Settings)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            setattr(blank, fields[0].name, None)
        self.assertGreaterEqual(len(settings.MODE_RULES), 6)

    # Interfaces: `planning.py`: `Planner` with `plan_prompt`, `plan_review_prompt`, `plan_accept`, `plan_scouts`,
    # `plan_scout_prompt`, `consult_prompt`, `brainstorm_prompt`; the facade forwards each.
    def test_planner_holds_the_planning_commands(self):
        planning = load(self, "feature_flow.conductor.planning")
        for name in ("plan_prompt", "plan_review_prompt", "plan_accept", "plan_scouts", "plan_scout_prompt",
                     "consult_prompt", "brainstorm_prompt"):
            self.assertTrue(callable(getattr(planning.Planner, name, None)), "Planner has no %s" % name)


FULL_TICKET = "# T\n\nType: task\nStatus: open\nBlocked by: —\n%s\n\nbody\n\n## Done when\n\n- x\n"


class Levels(unittest.TestCase):
    """- [ ] The level rules are the pure functions `policy.levels.declared`, `policy.levels.measured` and
    `policy.levels.describe` ... each returns the same level, reason ... as today's methods for every row of a
    table test."""

    def levels(self):
        return load(self, "feature_flow.conductor.policy.levels")

    def test_declared_returns_todays_level_and_reason(self):
        declared = self.levels().declared
        rows = (
            ("Level: 1", False, (1, "")),
            ("Level: 2", False, (2, "")),
            ("Level: 3", False, (3, "")),
            ("Test first: no", False, (0, "")),
            ("Level: 1\nReview: full", False, (3, "the ticket says Review: full")),
            ("Review: full", False, (3, "the ticket says Review: full")),
            ("Type: convert\nLevel: 2", False, (3, "the ticket is Type: convert")),
            ("Level: 2", True, (3, "the ticket edits the flow's own code (Floor: allow flow-edit)")),
            ("Level: 1\nReview: full", True, (3, "the ticket says Review: full")),
            ("Level: 3\nReview: full", True, (3, "")),
        )
        for header, flow_edit, want in rows:
            text = FULL_TICKET % header
            if "Type: convert" in header:
                text = text.replace("Type: task\n", "")
            self.assertEqual(tuple(declared(text, flow_edit)), want, header)

    # Edge case: A ticket not yet committed at its base -> `base_level` ... counts `Floor: allow flow-edit` only from
    # the committed ticket ... The pure rules take the flag from the caller so these differences stay.
    def test_declared_takes_the_flow_edit_flag_from_the_caller_not_the_text(self):
        declared = self.levels().declared
        text = FULL_TICKET % "Level: 1\nFloor: allow flow-edit"
        self.assertEqual(tuple(declared(text, False)), (1, ""))
        self.assertEqual(tuple(declared(text, True)),
                         (3, "the ticket edits the flow's own code (Floor: allow flow-edit)"))

    def test_measured_raises_never_lowers_with_todays_reasons(self):
        measured = self.levels().measured
        rows = (
            ((1, [], 2, 10, False, 3, 60), (1, "")),
            ((1, [], 3, 60, False, 3, 60), (1, "")),
            ((1, [], 4, 10, False, 3, 60), (2, "the diff (4 files, 10 lines) is over the small limits")),
            ((1, [], 1, 61, False, 3, 60), (2, "the diff (1 files, 61 lines) is over the small limits")),
            ((1, [], 1, 1, True, 3, 60), (2, "the diff (1 files, 1 lines, a binary file) is over the small limits")),
            ((2, [], 50, 5000, True, 3, 60), (2, "")),
            ((0, [], 50, 5000, True, 3, 60), (0, "")),
            ((2, ["src/auth/a.py"], 1, 1, False, 3, 60),
             (3, "the diff touches a Sensitive path in commands.md: src/auth/a.py")),
            ((1, ["a", "b", "c", "d"], 1, 1, False, 3, 60),
             (3, "the diff touches a Sensitive path in commands.md: a, b, c")),
            ((3, ["src/auth/a.py"], 50, 5000, True, 3, 60), (3, "")),
        )
        for args, want in rows:
            self.assertEqual(tuple(measured(*args)), want, args)

    def test_describe_gives_todays_text(self):
        describe = self.levels().describe
        self.assertEqual(describe(1, ""), "this ticket is level 1 (light)")
        self.assertEqual(describe(2, ""), "this ticket is level 2 (standard)")
        self.assertEqual(describe(3, "a reviewer raised it"),
                         "this ticket is level 3 (boundary), raised because a reviewer raised it")


ONE_REVIEW = "one review covers the spec and quality passes: do the spec checklist first"
HOSTILE = ", then probe the change as a hostile caller, as the guide says for level 3"
QUALITY_ONLY = "the spec review passed in an earlier round, so this round has the quality review only"


def round_note(n):
    return ("this is round %d: from now on only a blocker finding sends the ticket back. majors and "
            "minors go to the plan's followups.md and the ticket passes" % n)


class Review(unittest.TestCase):
    """- [ ] ... the review decision tree is `policy.review.after_checks` and `policy.review.on_fail`, and the round
    limit is `policy.limits.round_cap` ... each returns the same level, reason, decision and notes as today's
    methods for every row of a table test."""

    def test_after_checks_decides_and_writes_todays_notes(self):
        after_checks = load(self, "feature_flow.conductor.policy.review").after_checks
        note = "this ticket is level 2 (standard)"
        # (level, fast, gate_on, checks_ran, small_note, review_mode, spec_ok, round_no, level_note) -> want
        rows = (
            ((0, False, True, True, "", "auto", "", 0, ""), ("review", "spec", [], [])),
            ((0, False, True, True, "SMALL", "auto", "", 0, ""), ("review", "single", ["SMALL"], ["REVIEW-SMALL"])),
            ((0, False, True, False, "SMALL", "auto", "", 0, ""), ("review", "spec", [], [])),
            ((2, False, True, True, "", "auto", "", 0, note), ("review", "single", [note, ONE_REVIEW], ["REVIEW-SINGLE"])),
            ((3, False, True, True, "", "auto", "", 0, note),
             ("review", "single", [note, ONE_REVIEW + HOSTILE], ["REVIEW-SINGLE"])),
            ((3, False, True, True, "", "full", "", 0, note), ("review", "spec", [note], [])),
            ((3, False, True, True, "", "full", "1", 0, note), ("review", "quality", [note, QUALITY_ONLY], [])),
            ((2, False, True, True, "", "auto", "", 2, note),
             ("review", "single", [note, ONE_REVIEW, round_note(3)], ["REVIEW-SINGLE"])),
            ((2, False, True, True, "", "full", "1", 3, note),
             ("review", "quality", [note, QUALITY_ONLY, round_note(4)], [])),
        )
        for args, want in rows:
            got = after_checks(*args)
            self.assertEqual((got[0], got[1], list(got[2]), list(got[3])), want, args)

    def test_after_checks_defers_below_level_3_in_fast_mode_with_the_gate_on(self):
        after_checks = load(self, "feature_flow.conductor.policy.review").after_checks
        self.assertEqual(after_checks(2, True, True, True, "", "auto", "", 0, "n")[0], "defer")
        self.assertEqual(after_checks(0, True, True, True, "", "auto", "", 0, "")[0], "defer")
        self.assertEqual(after_checks(3, True, True, True, "", "auto", "", 0, "n")[0], "review")
        self.assertEqual(after_checks(2, True, False, True, "", "auto", "", 0, "n")[0], "review")
        self.assertEqual(after_checks(2, False, True, True, "", "auto", "", 0, "n")[0], "review")

    # Edge case: A level 2 ticket past `FULL_ROUNDS` with only majors -> Passes with follow-ups, as `judge_review` does.
    def test_on_fail_passes_a_level_2_ticket_past_its_full_rounds_with_only_majors(self):
        on_fail = load(self, "feature_flow.conductor.policy.review").on_fail
        majors = "1. major: a thing\n2. minor: a nit\nREVIEW: FAIL\n"
        blocker = "1. blocker: broken\n2. major: a thing\nREVIEW: FAIL\n"
        rows = (
            ((2, 2, "single", majors), "followups"),
            ((2, 3, "quality", majors), "followups"),
            ((2, 1, "single", majors), "send_back"),
            ((2, 2, "spec", majors), "send_back"),
            ((2, 2, "single", blocker), "send_back"),
            ((2, 2, "single", "- AC 1: NOT MET\n1. major: x\n"), "send_back"),
            ((2, 2, "single", "no findings\n"), "send_back"),
            ((1, 2, "single", majors), "send_back"),
            ((3, 2, "single", majors), "send_back"),
        )
        for args, want in rows:
            self.assertEqual(on_fail(*args), want, args)

    def test_round_cap_gives_todays_rounds(self):
        round_cap = load(self, "feature_flow.conductor.policy.limits").round_cap
        for args, want in (((1, 3), 1), ((1, 0), 0), ((0, 3), 3), ((2, 3), 3), ((3, 5), 5), ((2, 1), 1)):
            self.assertEqual(round_cap(*args), want, args)


if __name__ == "__main__":
    unittest.main()
