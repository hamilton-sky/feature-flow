import os
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import status, tickets  # the package under test, from this checkout


class Out:
    def __init__(self):
        self.text = ""

    def write(self, text):
        self.text += text


class StatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        self.tasks = Path("plans/f/tasks")
        self.tasks.mkdir(parents=True)

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def ticket(self, slug, title, state, blocked, body="body"):
        text = helpers.ticket_text(title, state, blocked).replace("body", body)
        (self.tasks / ("%s.md" % slug)).write_text(text)

    def run_status(self, *args):
        out, err = Out(), Out()
        code = status.run(list(args), out, err)
        return code, out.text, err.text

    def test_next_prints_the_lowest_ready_ticket(self):
        self.ticket("01-a", "A", "resolved", "—")
        self.ticket("02-b", "B", "open", "01")
        self.ticket("03-c", "C", "open", "—")
        self.assertEqual(self.run_status("f", "--next"), (0, "plans/f/tasks/02-b.md\n", ""))

    def test_next_exit_codes_for_done_and_stuck(self):
        self.ticket("01-a", "A", "done", "—")
        self.assertEqual(self.run_status("f", "--next"), (10, "", "COMPLETE\n"))
        self.ticket("02-b", "B", "claimed", "—")
        code, _, err = self.run_status("f", "--next")
        self.assertEqual(code, 11)
        self.assertEqual(err, "stuck: 1 claimed, 0 waiting, 0 open but blocked, 0 unknown status\n")

    def test_table_and_counts(self):
        self.ticket("01-a", "A", "open", "—")
        self.ticket("02-b", "B", "open", "01")
        self.assertEqual(self.run_status("f")[1],
                         "01  open      READY               A\n02  open      -      after 01     B\n")
        self.assertEqual(self.run_status("f", "--counts")[1],
                         "total=2 resolved=0 open=2 claimed=0 waiting=0 parked=0 unknown=0 ready=1\n")

    def test_check_reports_a_cycle_and_a_mention(self):
        self.ticket("01-a", "A", "open", "02")
        self.ticket("02-b", "B", "open", "01")
        self.ticket("03-c", "C", "open", "—", body="uses ticket 01")
        code, out, _ = self.run_status("f", "--check")
        self.assertEqual(code, 1)
        self.assertIn("warning: 03: mentions ticket 01 but is not ordered against it", out)
        self.assertIn("01: part of a dependency cycle\n02: part of a dependency cycle\n", out)

    def test_usage_and_missing_folder(self):
        self.assertEqual(self.run_status()[0], 2)
        self.assertEqual(self.run_status("nope"), (2, "", "no ticket folder: plans/nope/tasks\n"))

    def test_json_escapes_like_awk(self):
        self.assertEqual(status.jstr('a"b\\c\td\x01e\x02'), '"a\\"b\\\\c\\td\\ne"')

    def test_records_keep_carriage_returns_and_skip_the_final_newline(self):
        path = Path("x.md")
        path.write_bytes(b"a\r\nb\n")
        self.assertEqual(tickets.records(path), ["a\r", "b"])
        path.write_bytes(b"")
        self.assertEqual(tickets.records(path), [])

    def test_status_words(self):
        self.assertEqual(tickets.norm_status(" Ready-for-agent (by me)"), "open")
        self.assertEqual(tickets.norm_status("wontfix"), "parked")
        self.assertEqual(tickets.norm_status("open\r"), "unknown")


if __name__ == "__main__":
    unittest.main()
