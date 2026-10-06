import sys
import tempfile
import unittest
from pathlib import Path

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import state, tickets  # the package under test, from this checkout


class TicketTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "01-a.md"
        self.path.write_text(helpers.ticket_text("A", "Claimed (by me)", "—"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_status_is_the_first_word_lower_case(self):
        self.assertEqual(tickets.status(self.path), "claimed")

    def test_set_open_changes_only_the_status_line(self):
        before = self.path.read_text()
        tickets.set_open(self.path)
        after = self.path.read_text()
        self.assertEqual(tickets.status(self.path), "open")
        self.assertEqual(before.replace("Status: Claimed (by me)", "Status: open"), after)

    def test_name_and_number(self):
        self.assertEqual(tickets.name("plans/f/tasks/01-a.md"), "01-a")
        self.assertEqual(tickets.number("plans/f/tasks/01-a.md"), "01")

    def test_findings_are_appended_under_a_heading(self):
        tickets.append_findings(self.path, 2, "gate", "gate: Test failed\n")
        self.assertTrue(self.path.read_text().endswith("\n## Review findings (round 2, gate)\n\ngate: Test failed\n"))

    def test_commands_value_skips_placeholders(self):
        cmd = Path(self.tmp.name) / "commands.md"
        cmd.write_text("Build: `<command>`\nTest: `bash tests/run.sh`\n")
        self.assertEqual(tickets.commands_value(cmd, "Build"), "")
        self.assertEqual(tickets.commands_value(cmd, "Test"), "bash tests/run.sh")
        self.assertEqual(tickets.commands_value(cmd, "Lint"), "")


class StateTests(unittest.TestCase):
    def test_round_trip_keeps_values_as_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "flow-f.state"
            state.save(path, {"ticket": "plans/f/tasks/01-a.md", "cmd": "$(rm -rf /)", "runs": 3})
            self.assertEqual(state.load(path), {"ticket": "plans/f/tasks/01-a.md", "cmd": "$(rm -rf /)", "runs": "3"})

    def test_missing_file_is_empty(self):
        self.assertEqual(state.load("/nonexistent/flow-f.state"), {})


if __name__ == "__main__":
    unittest.main()
