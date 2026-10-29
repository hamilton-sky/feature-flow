"""The build check pipeline: stub checks for the order, the first failure and the notes, and each real
check class once against a throwaway repo."""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import git  # the package under test, from this checkout
from feature_flow.conductor import buildchecks
from feature_flow.conductor.errors import Stop

T1 = "plans/f/tasks/01-a.md"
FENCE = "```"


def py(code):
    return '"%s" -c "%s"' % (sys.executable, code)


class Stub:
    def __init__(self, name, source=None, notes=(), ran=None):
        self.name, self.source, self.notes, self.ran = name, source, list(notes), ran

    def run(self, c):
        self.ran.append(self.name)
        if self.source:
            return self.source, "report of %s" % self.name, []
        return None, "", list(self.notes)


class Handle:
    """The parts of the conductor a check reads, over a throwaway repo."""

    def __init__(self, base, gate_on=True, quick=False):
        self.scripts = Path("scripts")
        self.feature = "f"
        self.plan = Path("plans") / "f"
        self.commands = self.plan / "commands.md"
        self.gate_timeout = 1
        self.gate_on = gate_on
        self.quick = quick
        self.checks_ran = False
        self.st = {"ticket": T1, "num": "01", "base": base}
        self.events = []
        self.saved = []

    def get(self, key, default=""):
        return self.st.get(key, default)

    def log(self, event):
        self.events.append(event)

    def save(self):
        self.saved.append(self.st.get("restore"))

    def ticket_name(self):
        return "01-a"

    def gate_quick(self):
        return self.quick

    def ticket_at_base(self):
        return git.show_text("%s:%s" % (self.get("base"), T1))


class Pipeline(unittest.TestCase):
    def test_runs_in_order_and_collects_notes(self):
        ran = []
        checks = [Stub("a", notes=["n1"], ran=ran), Stub("b", ran=ran), Stub("c", notes=["n2", "n3"], ran=ran)]
        self.assertEqual(buildchecks.run(object(), checks), (None, "", ["n1", "n2", "n3"]))
        self.assertEqual(ran, ["a", "b", "c"])

    def test_stops_at_the_first_failure_without_notes(self):
        ran = []
        checks = [Stub("a", notes=["n1"], ran=ran), Stub("b", source="floor guard", ran=ran),
                  Stub("c", source="done when", ran=ran)]
        self.assertEqual(buildchecks.run(object(), checks), ("floor guard", "report of b", []))
        self.assertEqual(ran, ["a", "b"])

    def names(self, gate_on, gate=True):
        c = Handle("HEAD", gate_on=gate_on)
        return [type(check).__name__ for check in buildchecks.pipeline(c, gate=gate)]

    def test_the_full_pipeline(self):
        self.assertEqual(self.names(True), ["Gate", "FloorGuard", "Footprint", "DoneWhen", "TestFirst"])

    def test_the_batch_pipeline_has_no_gate(self):
        self.assertEqual(self.names(True, gate=False), ["FloorGuard", "Footprint", "DoneWhen", "TestFirst"])

    def test_gate_off_runs_only_the_guard_and_the_footprint(self):
        self.assertEqual(self.names(False), ["FloorGuard", "Footprint"])
        self.assertEqual(self.names(False, gate=False), ["FloorGuard", "Footprint"])


class RealChecks(unittest.TestCase):
    def setUp(self):
        self.repo = helpers.Repo(local=False)
        self.here = os.getcwd()
        os.chdir(str(self.repo.dir))
        env = {k: v for k, v in os.environ.items() if not k.startswith("FLOW_")}
        self.env = mock.patch.dict(os.environ, env, clear=True)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        os.chdir(self.here)
        self.repo.close()

    def ticket(self, header="", done_when=""):
        path = self.repo.path(T1)
        text = path.read_text(encoding="utf-8").replace("Test first: no\n", "Test first: no\n" + header)
        text = text.replace("- x\n", "- x\n\n" + done_when)
        path.write_text(text, encoding="utf-8")

    def test_first_yes(self):
        path = self.repo.path(T1)
        path.write_text(path.read_text(encoding="utf-8").replace("Test first: no", "Test first: yes"),
                        encoding="utf-8")

    def commands(self, test=None, quick=None):
        lines = ["# Commands: f", ""]
        if test:
            lines.append("Test: `%s`" % test)
        if quick:
            lines.append("Quick: `%s`" % quick)
        self.repo.path("plans/f/commands.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def base(self):
        if self.repo.porcelain():
            self.repo.commit("plan")
        return Handle(self.repo.head())

    def work(self, rel, message="work"):
        self.repo.path(rel).parent.mkdir(parents=True, exist_ok=True)
        self.repo.path(rel).write_text("x\n", encoding="utf-8")
        self.repo.commit(message)

    def test_gate_full_and_quick(self):
        self.commands(test=py("import sys; sys.exit(1)"), quick=py("pass"))
        c = self.base()
        source, report, notes = buildchecks.Gate().run(c)
        self.assertEqual((source, notes), ("gate (full)", []))
        self.assertIn("Test failed", report)
        self.assertEqual(c.events, ["GATE-FULL", "GATE-FAIL"])
        c.quick, c.events = True, []
        self.assertEqual(buildchecks.Gate().run(c), (None, "", []))
        self.assertEqual(c.events, ["GATE-QUICK", "GATE-PASS"])

    def test_floor_guard(self):
        c = self.base()
        self.work("work.txt")
        self.assertEqual(buildchecks.FloorGuard().run(c)[0], None)
        self.assertEqual(c.events, ["GUARD-PASS"])
        self.repo.path("plans/f/tasks/02-b.md").write_text("changed\n", encoding="utf-8")
        self.repo.commit("edit another ticket")
        c.events = []
        source, report, notes = buildchecks.FloorGuard().run(c)
        self.assertEqual((source, notes), ("floor guard", []))
        self.assertIn("02-b.md", report)
        self.assertEqual(c.events, ["GUARD-FAIL"])

    def test_footprint(self):
        self.ticket("Touches: src/\n")
        c = self.base()
        self.work("src/a.txt")
        self.assertEqual(buildchecks.Footprint().run(c), (None, "", []))
        self.assertEqual(c.events, ["FOOTPRINT-PASS"])
        self.work("other.txt")
        c.events = []
        source, report, notes = buildchecks.Footprint().run(c)
        self.assertEqual(source, "footprint check")
        self.assertIn("outside the ticket's `Touches:` line (src/): other.txt", report)
        self.assertEqual(c.events, ["FOOTPRINT-FAIL"])

    def test_footprint_without_touches_logs_nothing(self):
        c = self.base()
        self.work("other.txt")
        self.assertEqual(buildchecks.Footprint().run(c), (None, "", []))
        self.assertEqual(c.events, [])

    def test_done_when(self):
        self.ticket(done_when=FENCE + "check\n$ " + py("print('hi')") + "\nprints hi\n" + FENCE + "\n")
        c = self.base()
        self.assertEqual(buildchecks.DoneWhen().run(c),
                         (None, "", ["the conductor ran 1 Done when check(s) and all passed"]))
        self.assertTrue(c.checks_ran)
        self.assertEqual(c.events, ["DONEWHEN-PASS"])

    def test_done_when_fails_and_skips(self):
        self.ticket(done_when=FENCE + "check\n$ " + py("print('no')") + "\nprints hi\n" + FENCE + "\n")
        c = self.base()
        source, report, notes = buildchecks.DoneWhen().run(c)
        self.assertEqual((source, notes), ("done when", []))
        self.assertTrue(report)
        self.assertEqual(c.events, ["DONEWHEN-FAIL"])
        self.repo.path(T1).write_text(helpers.ticket_text("A", "open", "—"), encoding="utf-8")
        c = self.base()
        self.assertEqual(buildchecks.DoneWhen().run(c),
                         (None, "", ["the conductor ran no Done when checks: the ticket has no check block"]))
        self.assertFalse(c.checks_ran)
        self.assertEqual(c.events, ["DONEWHEN-SKIP"])

    def test_done_when_defers_a_check_this_host_cannot_run(self):
        self.ticket(done_when=FENCE + "check\n$ " + py("import sys; sys.exit(1)") + "\nneeds a robot\n"
                    + FENCE + "\n")
        c = self.base()
        source, _, notes = buildchecks.DoneWhen().run(c)
        self.assertIsNone(source)
        self.assertIn("deferred, not met", notes[0])
        self.assertEqual(c.events, ["DONEWHEN-PASS", "DONEWHEN-DEFERRED 1"])
        self.assertIn("deferred check, needs a robot", c.st["due_checks"])

    def test_done_when_stops_on_a_dirty_tree(self):
        self.ticket(done_when=FENCE + "check\n$ " + py("open('dirt.txt', 'w').write('x')") + "\n" + FENCE + "\n")
        c = self.base()
        with self.assertRaises(Stop):
            buildchecks.DoneWhen().run(c)

    def test_test_first(self):
        self.test_first_yes()
        self.commands(test=py("import os,sys; sys.exit(0 if os.path.exists('code.txt') else 1)"))
        c = self.base()
        branch = self.repo.git("symbolic-ref", "--short", "HEAD")
        self.work("tests/t.txt", "test")
        self.work("code.txt", "code")
        source, report, notes = buildchecks.TestFirst().run(c)
        self.assertIsNone(source)
        self.assertIn("fail the Test command before the code", notes[0])
        self.assertEqual(c.events, ["TESTFIRST-PASS"])
        self.assertEqual(c.saved[-1], "")
        self.assertIn(branch, c.saved)
        self.assertEqual(self.repo.git("symbolic-ref", "--short", "HEAD"), branch)

    def test_test_first_fails_skips_and_is_off(self):
        c = self.base()
        self.assertEqual(buildchecks.TestFirst().run(c), (None, "", []))
        self.assertEqual(c.events, [])
        self.test_first_yes()
        c = self.base()
        self.assertEqual(buildchecks.TestFirst().run(c),
                         (None, "", ["the conductor did not check test first: commands.md has no Test command"]))
        self.assertEqual(c.events, ["TESTFIRST-SKIP"])
        self.commands(test=py("pass"))
        c = self.base()
        self.work("code.txt")
        source, report, notes = buildchecks.TestFirst().run(c)
        self.assertEqual((source, notes), ("test first", []))
        self.assertIn("no commit between base and HEAD changes only test files", report)
        self.assertEqual(c.events, ["TESTFIRST-FAIL"])

    def test_the_pipeline_stops_at_the_footprint(self):
        self.ticket("Touches: src/\n", FENCE + "check\n$ " + py("pass") + "\n" + FENCE + "\n")
        c = self.base()
        self.work("other.txt")
        source, _, notes = buildchecks.run(c, buildchecks.pipeline(c, gate=False))
        self.assertEqual((source, notes), ("footprint check", []))
        self.assertEqual(c.events, ["GUARD-PASS", "FOOTPRINT-FAIL"])
        self.assertFalse(c.checks_ran)


if __name__ == "__main__":
    unittest.main()
