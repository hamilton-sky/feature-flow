"""The pure policy rules: the ticket's level and its reason, the review decision after green checks, the FAIL
branch of a review and the rework rounds. Values in, values out: one row per rule and branch."""

import sys
import types
import unittest

from helpers import ROOT

sys.path.insert(0, str(ROOT))
from feature_flow.conductor.policy import levels, limits, review  # the package under test, from this checkout

TICKET = "# T\n\n%s\nStatus: open\nBlocked by: —\n\nbody\n\n## Done when\n\n- x\n\n## Answer\n"
FLOW_EDIT = "the ticket edits the flow's own code (Floor: allow flow-edit)"
FULL = "the ticket says Review: full"
CONVERT = "the ticket is Type: convert"
NOTE = "this ticket is level 2 (standard)"
ONE = "one review covers the spec and quality passes: do the spec checklist first"
HOSTILE = ", then probe the change as a hostile caller, as the guide says for level 3"
QUALITY = "the spec review passed in an earlier round, so this round has the quality review only"
MAJOR = "QUALITY\n1. major work.txt: could be tidier - tidy it\n\nREVIEW: FAIL\n"
BLOCKER = "QUALITY\n1. blocker work.txt: loses data - keep it\n2. major work.txt: tidy\n\nREVIEW: FAIL\n"


def rounds(n):
    return ("this is round %d: from now on only a blocker finding sends the ticket back. majors and "
            "minors go to the plan's followups.md and the ticket passes" % n)


class Declared(unittest.TestCase):
    # (header lines, flow_edit) -> (level, why)
    ROWS = (
        ("Type: task", False, (0, "")),
        ("Type: task\nLevel: 1", False, (1, "")),
        ("Type: task\nLevel: 2", False, (2, "")),
        ("Type: task\nLevel: 3", False, (3, "")),
        ("Type: task\nLevel: 1\nReview: full", False, (3, FULL)),
        ("Type: task\nReview: full", False, (3, FULL)),
        ("Type: convert\nLevel: 2", False, (3, CONVERT)),
        ("Type: task\nLevel: 1", True, (3, FLOW_EDIT)),
        ("Type: task", True, (3, FLOW_EDIT)),
        ("Type: convert\nReview: full", True, (3, FULL)),  # the first reason wins
        ("Type: convert", True, (3, CONVERT)),
        ("Type: task\nLevel: 3\nReview: full", True, (3, "")),  # already 3: not raised, no reason
        ("Type: task\nLevel: 1\nFloor: allow flow-edit", False, (1, "")),  # the flag comes from the caller only
    )

    def test_rows(self):
        for header, flow_edit, want in self.ROWS:
            self.assertEqual(levels.declared(TICKET % header, flow_edit), want, (header, flow_edit))

    def test_only_the_header_counts(self):
        text = TICKET % "Type: task\nLevel: 1" + "\n## Notes\n\nType: convert\nReview: full\nLevel: 3\n"
        self.assertEqual(levels.declared(text, False), (1, ""))


class Measured(unittest.TestCase):
    # (level, sensitive_hits, files, lines, binary, small_files, small_lines) -> (level, why)
    ROWS = (
        ((1, [], 3, 60, False, 3, 60), (1, "")),
        ((1, [], 4, 10, False, 3, 60), (2, "the diff (4 files, 10 lines) is over the small limits")),
        ((1, [], 1, 61, False, 3, 60), (2, "the diff (1 files, 61 lines) is over the small limits")),
        ((1, [], 1, 1, True, 3, 60), (2, "the diff (1 files, 1 lines, a binary file) is over the small limits")),
        ((0, [], 50, 5000, True, 3, 60), (0, "")),
        ((2, [], 50, 5000, True, 3, 60), (2, "")),
        ((0, ["src/a.py"], 1, 1, False, 3, 60), (3, "the diff touches a Sensitive path in commands.md: src/a.py")),
        ((1, ["a", "b", "c", "d"], 9, 999, True, 3, 60),
         (3, "the diff touches a Sensitive path in commands.md: a, b, c")),
        ((3, ["src/a.py"], 50, 5000, True, 3, 60), (3, "")),  # never raised past 3, never lowered
    )

    def test_rows(self):
        for args, want in self.ROWS:
            self.assertEqual(levels.measured(*args), want, args)


class Describe(unittest.TestCase):
    def test_rows(self):
        for args, want in (((1, ""), "this ticket is level 1 (light)"),
                           ((2, ""), "this ticket is level 2 (standard)"),
                           ((3, ""), "this ticket is level 3 (boundary)"),
                           ((3, FULL), "this ticket is level 3 (boundary), raised because " + FULL)):
            self.assertEqual(levels.describe(*args), want, args)


class AfterChecks(unittest.TestCase):
    # (level, fast, gate_on, checks_ran, small_note, review_mode, spec_ok, round_no, level_note)
    #   -> (decision, review_pass, notes, events)
    ROWS = (
        ((2, True, True, True, "", "auto", "", 0, NOTE), ("defer", "", [], [])),
        ((0, True, True, True, "S", "auto", "", 0, ""), ("defer", "", [], [])),
        ((3, True, True, True, "", "auto", "", 0, NOTE), ("review", "single", [NOTE, ONE + HOSTILE], ["REVIEW-SINGLE"])),
        ((2, True, False, True, "", "auto", "", 0, NOTE), ("review", "single", [NOTE, ONE], ["REVIEW-SINGLE"])),
        ((0, False, True, True, "", "auto", "", 0, ""), ("review", "spec", [], [])),
        ((0, False, True, True, "S", "auto", "", 0, ""), ("review", "single", ["S"], ["REVIEW-SMALL"])),
        ((0, False, True, False, "S", "auto", "", 0, ""), ("review", "spec", [], [])),
        ((0, False, False, True, "S", "auto", "", 0, ""), ("review", "spec", [], [])),
        ((0, False, True, True, "", "auto", "1", 0, ""), ("review", "quality", [QUALITY], [])),
        ((1, False, True, True, "", "auto", "", 0, NOTE), ("review", "single", [NOTE, ONE], ["REVIEW-SINGLE"])),
        ((3, False, True, True, "", "full", "", 0, NOTE), ("review", "spec", [NOTE], [])),
        ((3, False, True, True, "", "full", "1", 0, NOTE), ("review", "quality", [NOTE, QUALITY], [])),
        ((2, False, True, True, "", "auto", "1", 2, NOTE),
         ("review", "single", [NOTE, ONE, rounds(3)], ["REVIEW-SINGLE"])),  # single never turns into quality
        ((2, False, True, True, "", "full", "1", 3, NOTE), ("review", "quality", [NOTE, QUALITY, rounds(4)], [])),
        ((2, False, True, True, "", "full", "", 1, NOTE), ("review", "spec", [NOTE], [])),
        ((3, False, True, True, "", "full", "", 2, NOTE), ("review", "spec", [NOTE], [])),  # the round note is level 2's
    )

    def test_rows(self):
        for args, want in self.ROWS:
            decision, review_pass, notes, events = review.after_checks(*args)
            self.assertEqual((decision, review_pass, list(notes), list(events)), want, args)


class OnFail(unittest.TestCase):
    # (level, round_no, review_pass, findings) -> decision
    ROWS = (
        ((2, 2, "single", MAJOR), "followups"),
        ((2, 3, "quality", MAJOR), "followups"),
        ((2, 1, "single", MAJOR), "send_back"),
        ((2, 2, "spec", MAJOR), "send_back"),
        ((2, 2, "single", BLOCKER), "send_back"),
        ((2, 2, "single", "- AC 1: NOT MET\n" + MAJOR), "send_back"),
        ((2, 2, "single", "- scope: src/extra.py\n" + MAJOR), "send_back"),
        ((2, 2, "single", "- test first: MISSING\n" + MAJOR), "send_back"),
        ((2, 2, "single", "no findings\nREVIEW: FAIL\n"), "send_back"),
        ((1, 2, "single", MAJOR), "send_back"),
        ((3, 2, "single", MAJOR), "send_back"),
    )

    def test_rows(self):
        for args, want in self.ROWS:
            self.assertEqual(review.on_fail(*args), want, args)

    def test_followups_only_is_still_the_packages(self):
        from feature_flow import conductor
        self.assertIs(conductor.followups_only, review.followups_only)


class RoundCap(unittest.TestCase):
    def test_rows(self):
        for args, want in (((1, 3), 1), ((1, 0), 0), ((0, 3), 3), ((2, 3), 3), ((3, 5), 5), ((2, 1), 1)):
            self.assertEqual(limits.round_cap(*args), want, args)


class Pure(unittest.TestCase):
    def test_no_module_reaches_git_state_files_or_os(self):
        for module in (levels, review, limits):
            names = [v.__name__ for v in vars(module).values() if isinstance(v, types.ModuleType)]
            self.assertEqual([n for n in names if n.split(".")[-1] in
                              ("git", "checks", "state", "codehash", "os", "subprocess", "proof", "store")], [],
                             module.__name__)


if __name__ == "__main__":
    unittest.main()
