import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import report  # the package under test, from this checkout

LOG = """10:00:00,-,START
10:00:01,01,BUILD
10:00:02,01,GATE-FULL
10:00:03,01,GATE-FAIL
10:00:04,01,STOP the gate failed: Test exited 1
10:00:05,01,BUILD
10:00:06,01,GATE-QUICK
10:00:07,01,GATE-PASS
10:00:08,01,REVIEW-SMALL
10:00:09,01,REVIEW
10:00:10,01,VERDICT-PASS
10:00:11,02,BUILD
10:00:12,02,VERDICT-FAIL
10:00:13,-,HANDOFF
garbage line
10:00:14,-,RESET
"""


class ReportTests(unittest.TestCase):
    def test_parse_skips_bad_lines_and_keeps_the_stop_reason(self):
        rows = report.parse(LOG)
        self.assertEqual(len(rows), 15)
        self.assertIn(("01", "STOP", "the gate failed: Test exited 1"), rows)

    def test_summary_counts_per_ticket_and_run(self):
        tickets, run, stops = report.summarize(report.parse(LOG))
        self.assertEqual(tickets["01"]["BUILD"], 2)
        self.assertEqual(tickets["01"]["GATE-FAIL"], 1)
        self.assertEqual(tickets["02"]["VERDICT-FAIL"], 1)
        self.assertEqual((run["START"], run["HANDOFF"], run["RESET"], run["STOP"]), (1, 1, 1, 1))
        self.assertEqual(stops, [("01", "the gate failed: Test exited 1")])

    def test_render_names_the_reworked_ticket_and_the_stop(self):
        text = report.render("f", report.parse(LOG))
        self.assertIn("tickets built more than once (reworked): 01", text)
        self.assertIn("STOP at ticket 01: the gate failed: Test exited 1", text)
        self.assertIn("GATE-FAIL x1", text)
        self.assertIn("trust-runner STOPs are not in this log", text)

    def test_an_empty_log_says_so(self):
        self.assertIn("no ticket events yet", report.render("f", []))


class ReportCommandTests(unittest.TestCase):
    def setUp(self):
        self.repo = helpers.Repo(local=False)
        self.cwd = os.getcwd()
        os.chdir(str(self.repo.dir))

    def tearDown(self):
        os.chdir(self.cwd)
        self.repo.close()

    def run_report(self, *args):
        out, err = io.StringIO(), io.StringIO()
        code = report.main(list(args), out, err)
        return code, out.getvalue(), err.getvalue()

    def test_no_log_is_a_usage_style_error_with_a_hint(self):
        folder = self.repo.dir / ".feature-flow" / "state"
        folder.mkdir(parents=True)
        (folder / "flow-feature.log").write_text(LOG, encoding="utf-8")
        code, _, err = self.run_report("featur")
        self.assertEqual(code, 2)
        self.assertIn("no run log for featur", err)
        self.assertIn("did you mean: feature?", err)

    def test_reads_the_log_in_the_state_folder(self):
        folder = self.repo.dir / ".feature-flow" / "state"
        folder.mkdir(parents=True)
        (folder / "flow-f.log").write_text(LOG, encoding="utf-8")
        code, out, _ = self.run_report("f")
        self.assertEqual(code, 0)
        self.assertIn("report for f: 15 log line(s)", out)

    def test_usage(self):
        self.assertEqual(self.run_report()[0], 2)
        self.assertEqual(self.run_report("--bad")[0], 2)

    def test_the_command_is_wired_in(self):
        from feature_flow import command
        self.assertIn("report", command.COMMANDS)
        self.assertIn("feature-flow report <feature>", command.USAGE)


if __name__ == "__main__":
    unittest.main()
