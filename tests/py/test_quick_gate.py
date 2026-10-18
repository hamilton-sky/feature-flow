import sys
import tempfile
import unittest
from pathlib import Path

from helpers import Repo

T = ["plans/f/tasks/01-a.md", "plans/f/tasks/02-b.md", "plans/f/tasks/03-c.md"]
PLAN = (("01-a", "A", "—"), ("02-b", "B", "01"), ("03-c", "C", "02"))


class QuickGateTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repo(PLAN)
        self.aux = tempfile.TemporaryDirectory()
        self.logger = Path(self.aux.name) / "logger.py"
        self.logfile = Path(self.aux.name) / "ran.log"
        self.logger.write_text(
            "import sys\n"
            "open(sys.argv[2], 'a').write(sys.argv[1] + '\\n')\n"
            "if len(sys.argv) > 3:\n"
            "    sys.stderr.write('quick broke\\n')\n"
            "    sys.exit(3)\n", encoding="utf-8")

    def tearDown(self):
        self.repo.close()
        self.aux.cleanup()

    def cmd(self, name, fail=False):
        return '"%s" "%s" %s "%s"%s' % (sys.executable, self.logger, name, self.logfile, " fail" if fail else "")

    def commands(self, quick=True, fail=False):
        path = self.repo.path("plans/f/commands.md")
        text = path.read_text(encoding="utf-8") + "Test: `%s`\n" % self.cmd("test")
        if quick:
            text += "Quick: `%s`\n" % self.cmd("quick", fail)
        path.write_text(text, encoding="utf-8")
        self.repo.commit("commands")

    def ran(self):
        return self.logfile.read_text(encoding="utf-8").split() if self.logfile.exists() else []

    def gate_of(self, index, **env):
        """Build ticket index (0 based) and return what the gate ran for it."""
        self.logfile.write_text("", encoding="utf-8")
        rc, out = self.repo.flow("next", **env)
        self.assertEqual(rc, 0, out)
        self.assertTrue(out.startswith("BUILD %s " % T[index]), out)
        self.repo.resolve(T[index])
        rc, out = self.repo.flow("next", **env)
        self.assertEqual(rc, 0, out)
        ran = self.ran()
        self.assertTrue(out.startswith("REVIEW"), out)
        return ran

    def finish(self, **env):
        verdict = Path(self.aux.name) / "verdict.txt"
        verdict.write_text("fine\nREVIEW: PASS\n", encoding="utf-8")
        self.repo.flow("verdict", str(verdict), **env)
        self.repo.flow("next", **env)
        self.repo.flow("verdict", str(verdict), **env)

    def drive(self, **env):
        """The gate's run for each of the three tickets, in order."""
        result = []
        for index in range(3):
            result.append(self.gate_of(index, **env))
            if index < 2:
                self.finish(**env)
        return result

    def test_first_ticket_runs_only_quick(self):
        self.commands()
        self.assertEqual(self.gate_of(0), ["quick"])
        self.assertIn("GATE-QUICK", self.repo.log())
        self.assertNotIn("GATE-FULL", self.repo.log())

    def test_middle_quick_and_last_ticket_runs_test(self):
        self.commands()
        self.assertEqual(self.drive(), [["quick"], ["quick"], ["test"]])
        log = self.repo.log()
        self.assertEqual(log.count("GATE-QUICK"), 2)
        self.assertEqual(log.count("GATE-FULL"), 1)

    def test_handoff_ticket_runs_test(self):
        self.commands()
        self.assertEqual(self.gate_of(0, FLOW_TICKETS_PER_SESSION="2"), ["quick"])
        self.finish(FLOW_TICKETS_PER_SESSION="2")
        self.assertEqual(self.gate_of(1, FLOW_TICKETS_PER_SESSION="2"), ["test"])
        self.assertIn("GATE-FULL", self.repo.log())

    def test_a_gate_full_ticket_runs_test(self):
        self.commands()
        path = self.repo.path(T[0])
        path.write_text(path.read_text(encoding="utf-8").replace("Test first: no\n", "Test first: no\nGate: full\n"),
                        encoding="utf-8")
        self.repo.commit("01 is a phase ticket")
        self.assertEqual(self.drive(), [["test"], ["quick"], ["test"]])

    def test_full_gate_env_runs_test_for_every_ticket(self):
        self.commands()
        self.assertEqual(self.drive(FLOW_GATE_FULL="1"), [["test"], ["test"], ["test"]])
        self.assertNotIn("GATE-QUICK", self.repo.log())

    def test_no_quick_line_runs_test_every_time(self):
        self.commands(quick=False)
        self.assertEqual(self.drive(), [["test"], ["test"], ["test"]])
        self.assertNotIn("GATE-QUICK", self.repo.log())

    def test_gate_off_runs_neither(self):
        self.commands()
        self.assertEqual(self.gate_of(0, FLOW_GATE="off"), [])
        self.assertNotIn("GATE-", self.repo.log())

    def test_failing_quick_sends_the_ticket_back(self):
        self.commands(fail=True)
        self.repo.flow("next")
        self.repo.resolve(T[0])
        rc, out = self.repo.flow("next")
        self.assertEqual(rc, 0, out)
        self.assertTrue(out.startswith("BUILD %s " % T[0]), out)
        text = self.repo.path(T[0]).read_text(encoding="utf-8")
        self.assertIn("## Review findings (round 1, gate (quick))", text)
        self.assertIn("quick broke", text)
        self.assertIn("GATE-FAIL", self.repo.log())


if __name__ == "__main__":
    unittest.main()
