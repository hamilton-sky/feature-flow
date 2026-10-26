"""0.21.0: in fast mode one builder builds up to 5 small, ready tickets that touch different files, and the
conductor still checks each ticket on its own commits before the one feature review."""

import shutil
import sys
import unittest

from helpers import ROOT, Repo

PYTHON = '"%s"' % sys.executable
GATE = "%s -c \"import os, sys; sys.exit(1 if os.path.exists('bad.txt') else 0)\"" % PYTHON
COMMANDS = ("# Commands: f\n\nSmoke: `%s -c \"pass\"`\nTest: `%s`\nSensitive: `src/auth/`\n" % (PYTHON, GATE))


def ticket(index, header):
    lines = ["# T%d\n" % index, "Type: task", "Status: open", "Blocked by: —", "Test first: no"] + header
    return "\n".join(lines) + "\n\nbody\n\n## Done when\n\n- x\n\n## Answer\n"


class BatchDrive(unittest.TestCase):
    def setup(self, headers, **env):
        repo = Repo(tickets=())
        self.addCleanup(repo.close)
        for folder in ("agents", "guides"):
            shutil.copytree(str(ROOT / folder), str(repo.path(folder)))
        repo.path("plans/f/commands.md").write_text(COMMANDS, encoding="utf-8")
        self.paths = []
        for index, header in enumerate(headers, 1):
            path = "plans/f/tasks/%02d-t%d.md" % (index, index)
            repo.path(path).write_text(ticket(index, header), encoding="utf-8")
            self.paths.append(path)
        repo.commit("plan")
        env = dict({"FLOW_TICKETS_PER_SESSION": "99", "FLOW_FAST": "1"}, **env)
        rc, out = repo.flow("start", **env)
        self.assertEqual(rc, 0, out)
        env["FLOW_SESSION"] = out.split()[1]
        env.pop("FLOW_FAST")
        self.repo, self.env = repo, env
        return repo

    def flow(self, *args):
        return self.repo.flow(*args, **self.env)

    def build(self, index, name):
        """The batch builder finishes ticket index: its file, its Status, one commit."""
        self.repo.path(name).parent.mkdir(parents=True, exist_ok=True)
        self.repo.path(name).write_text("x\n", encoding="utf-8")
        self.repo.set_status(self.paths[index - 1], "resolved")
        self.repo.commit("feat: %02d" % index)

    def test_three_small_tickets_are_one_build_and_each_is_checked(self):
        self.setup([["Level: 1", "Touches: a/"], ["Level: 2", "Touches: b/"], ["Level: 1", "Touches: c/"]])
        rc, out = self.flow("next")
        self.assertTrue(out.startswith("BUILD %s 01 " % self.paths[0]), out)
        self.assertIn("BATCH 3", self.repo.log())
        prompt = self.flow("prompt")[1]
        self.assertIn("This build is a batch of 3 small tickets: `%s` (above), then `%s`, `%s`"
                      % tuple(self.paths), prompt)
        for index, name in ((1, "a/x.txt"), (2, "b/x.txt"), (3, "c/x.txt")):
            self.build(index, name)
        rc, out = self.flow("next")
        self.assertTrue(out.startswith("REVIEW plans/f all "), out)  # straight to the feature review
        log = self.repo.log()
        self.assertEqual(log.count("REVIEW-DEFERRED"), 3)
        self.assertEqual(log.count("GUARD-PASS"), 3)
        self.assertEqual(log.count("FOOTPRINT-PASS"), 3)
        self.assertEqual(self.repo.git("symbolic-ref", "--short", "HEAD"), self.repo.git("rev-parse", "--abbrev-ref", "HEAD"))
        self.assertEqual(self.repo.porcelain(), "")
        self.assertEqual(self.repo.state().get("batch_restore", ""), "")

    def test_a_ticket_that_strays_from_its_files_goes_back_alone(self):
        self.setup([["Level: 1", "Touches: a/"], ["Level: 1", "Touches: b/"], ["Level: 1", "Touches: c/"]])
        self.flow("next")
        self.build(1, "a/x.txt")
        self.build(2, "elsewhere/x.txt")
        self.build(3, "c/x.txt")
        rc, out = self.flow("next")
        self.assertTrue(out.startswith("BUILD %s 02 " % self.paths[1]), out)
        self.assertNotIn(",BATCH ", self.repo.log().split("BATCH 3", 1)[1])  # built alone this time
        text = self.repo.path(self.paths[1]).read_text(encoding="utf-8")
        self.assertIn("Status: open", text)
        self.assertIn("## Review findings (round 1, footprint check)", text)
        self.assertEqual(self.repo.log().count("REVIEW-DEFERRED"), 2)

    def test_the_gate_blames_the_first_ticket_that_broke_it(self):
        self.setup([["Level: 1", "Touches: a/"], ["Level: 1", "Touches: bad.txt"], ["Level: 1", "Touches: c/"]])
        self.flow("next")
        self.build(1, "a/x.txt")
        self.build(2, "bad.txt")
        self.build(3, "c/x.txt")
        rc, out = self.flow("next")
        self.assertTrue(out.startswith("BUILD %s 02 " % self.paths[1]), out)
        self.assertIn("## Review findings (round 1, gate)", self.repo.path(self.paths[1]).read_text(encoding="utf-8"))
        self.assertIn("Status: resolved", self.repo.path(self.paths[2]).read_text(encoding="utf-8"))

    def test_a_builder_that_stops_leaves_the_rest_for_single_builds(self):
        self.setup([["Level: 1", "Touches: a/"], ["Level: 1", "Touches: b/"]])
        self.flow("next")
        self.build(1, "a/x.txt")
        rc, out = self.flow("next")
        self.assertTrue(out.startswith("BUILD %s 02 " % self.paths[1]), out)
        self.assertEqual(self.repo.log().count(",BATCH "), 1)

    def test_what_is_never_batched(self):
        self.setup([["Level: 1", "Touches: a/"], ["Level: 3", "Touches: b/"], ["Level: 1"],
                    ["Level: 1", "Touches: src/auth/x.py"], ["Level: 2", "Touches: a/y.txt"], ["Level: 2", "Touches: d/"]])
        self.flow("next")
        self.assertIn("BATCH 2", self.repo.log())  # 01 and 06: 02 is level 3, 03 has no Touches, 04 is Sensitive,
        self.assertIn("then `%s`." % self.paths[5], self.flow("prompt")[1])  # and 05 shares a/ with 01

    def test_no_batch_outside_fast_mode_or_with_flow_batch_1(self):
        self.setup([["Level: 1", "Touches: a/"], ["Level: 1", "Touches: b/"]], FLOW_BATCH="1")
        self.flow("next")
        self.assertNotIn("BATCH", self.repo.log())


if __name__ == "__main__":
    unittest.main()
