import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import evaluate, state  # the package under test, from this checkout

LOG = """2026-10-23T10:00:00Z,-,START
2026-10-23T10:00:10Z,01,BUILD
2026-10-23T10:01:00Z,01,LEVEL-2
2026-10-23T10:01:00Z,01,GUARD-FAIL
2026-10-23T10:02:00Z,01,BUILD
2026-10-23T10:03:00Z,01,REVIEW
2026-10-23T10:04:00Z,01,VERDICT-PASS
2026-10-23T10:05:00Z,02,BUILD
2026-10-23T10:05:30Z,02,ASK
2026-10-23T10:06:00Z,02,ASK-PO-USER
2026-10-23T10:07:00Z,02,STOP a question for you
2026-10-23T10:08:00Z,02,GATE-FAIL
2026-10-23T10:09:00Z,-,HANDOFF
"""


def transcript(cwd):
    def line(ts, mid, model, out_tokens):
        return json.dumps({"cwd": cwd, "timestamp": ts, "requestId": "r" + mid,
                           "message": {"id": mid, "model": model,
                                       "usage": {"input_tokens": 10, "output_tokens": out_tokens,
                                                 "cache_read_input_tokens": 100,
                                                 "cache_creation_input_tokens": 5}}})
    return "\n".join([
        line("2026-10-23T10:00:05.000Z", "m1", "opus", 7),
        line("2026-10-23T10:00:05.000Z", "m1", "opus", 7),  # the same message logged twice
        line("2026-10-23T10:05:10.000Z", "m2", "haiku", 3),
        line("2026-10-23T11:30:00.000Z", "m3", "opus", 1000),  # after the run
        json.dumps({"cwd": "/somewhere/else", "timestamp": "2026-10-23T10:01:00Z",
                    "message": {"id": "m4", "usage": {"output_tokens": 999}}}),
        "not json",
    ]) + "\n"


class ParseTests(unittest.TestCase):
    def test_times_catches_and_people(self):
        rows = evaluate.timed(LOG)
        per, totals, you, window = evaluate.run_summary(rows)
        self.assertEqual(per["01"]["builds"], 2)
        self.assertEqual(per["01"]["level"], 2)
        self.assertEqual(totals["reworked"], ["01"])
        self.assertEqual(totals["catches_by_check"], {"GUARD-FAIL": 1, "GATE-FAIL": 1})
        self.assertEqual(you["questions_to_user"], 1)
        self.assertEqual(you["stops"], [{"ticket": "02", "reason": "a question for you"}])
        self.assertEqual(you["handoffs"], 1)
        self.assertEqual(window[0].hour, 10)
        self.assertEqual(evaluate.catch_ids(rows), ["01 GUARD-FAIL 1", "02 GATE-FAIL 1"])

    def test_an_old_log_has_no_window(self):
        rows = evaluate.timed("10:00:00,-,START\n10:00:01,01,BUILD\n")
        self.assertIsNone(evaluate.run_summary(rows)[3])

    def test_the_verdict_form_reads_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            form = Path(tmp) / "v.md"
            form.write_text(evaluate.verdict_template("f", ["01 GUARD-FAIL 1", "02 GATE-FAIL 1"]), encoding="utf-8")
            self.assertIsNone(evaluate.read_verdict(form))  # untouched
            text = form.read_text(encoding="utf-8")
            text = text.replace("plan: (right", "plan: partly\nx: (right").replace("hand-fixes: (how", "hand-fixes: 2\ny: (how")
            text = text.replace("01 GUARD-FAIL 1: ", "01 GUARD-FAIL 1: real").replace("02 GATE-FAIL 1: ", "02 GATE-FAIL 1: false, flaky")
            form.write_text(text, encoding="utf-8")
            verdict = evaluate.read_verdict(form)
        self.assertEqual(verdict["plan"], "partly")
        self.assertEqual(verdict["hand_fixes"], "2")
        self.assertEqual((verdict["real_catches"], verdict["false_alarms"]), (1, 1))


class EvalCommandTests(unittest.TestCase):
    def setUp(self):
        self.repo = helpers.Repo(local=False)
        self.cwd = os.getcwd()
        os.chdir(str(self.repo.dir))
        self.home = tempfile.TemporaryDirectory()
        folder = state.state_dir(self.repo.dir)
        (folder / "flow-f.log").write_text(LOG, encoding="utf-8")
        (folder / "flow-f.state").write_text("spent=725\n", encoding="utf-8")
        project = Path(self.home.name) / "projects" / "-tmp-x"
        project.mkdir(parents=True)
        (project / "s.jsonl").write_text(transcript(str(self.repo.dir.resolve() / "sub")), encoding="utf-8")

    def tearDown(self):
        os.chdir(self.cwd)
        self.home.cleanup()
        self.repo.close()

    def run_eval(self, *args):
        out, err = io.StringIO(), io.StringIO()
        code = evaluate.main(list(args) + ["--claude-home", self.home.name], out, err)
        return code, out.getvalue(), err.getvalue()

    def test_it_writes_the_record_and_the_form(self):
        code, out, err = self.run_eval("f")
        self.assertEqual(code, 0, err)
        plan = self.repo.dir / "plans" / "f"
        record = json.loads((plan / "eval.json").read_text(encoding="utf-8"))
        self.assertTrue((plan / "eval-verdict.md").is_file())
        self.assertEqual(record["active_minutes"], 12)
        self.assertEqual(record["totals"]["catches"], 2)
        tok = record["tokens"]
        self.assertEqual(tok["total"], {"input": 20, "output": 10, "cache_read": 200, "cache_write": 10})
        self.assertEqual(tok["by_model"]["haiku"]["output"], 3)
        self.assertEqual(tok["by_ticket"]["-"]["output"], 7)  # between START and ticket 01's first line
        self.assertEqual(tok["by_ticket"]["02"]["output"], 3)
        self.assertIsNone(record["verdict"])
        self.assertIn("2 catch(es)", out)
        self.assertIn("fill in", out)

    def test_it_records_the_driver_the_followups_and_the_settled_tickets(self):
        folder = state.state_dir(self.repo.dir)
        (folder / "flow-f.log").write_text(LOG.replace("START\n", "START\n2026-10-23T10:00:01Z,-,DRIVER-AGENT\n", 1)
                                           + "2026-10-23T10:09:30Z,02,DONEWHEN-DEFERRED 2\n", encoding="utf-8")
        plan = self.repo.dir / "plans" / "f"
        (plan / "tasks" / "03-c.md").write_text(helpers.ticket_text("C", "resolved", "—"), encoding="utf-8")
        (plan / "followups.md").write_text("# Follow-ups: f\n\n## 01-a (left for later)\n\n- one\n- two\n",
                                           encoding="utf-8")
        code, out, err = self.run_eval("f")
        self.assertEqual(code, 0, err)
        record = json.loads((plan / "eval.json").read_text(encoding="utf-8"))
        self.assertEqual(record["driver"], "agent")
        self.assertEqual(record["totals"]["settled_at_plan"], ["03"])
        self.assertEqual(record["totals"]["followups"], 2)
        self.assertEqual(record["totals"]["deferred_checks"], 2)
        self.assertIn("settled at plan approval (never built): 03", out)
        self.assertIn("follow-ups: 2 in followups.md, 2 deferred check(s)", out)
        self.assertIn("needed the driving agent (not you): 1 stop(s)", out)
        self.assertIn("an agent drove this run", (plan / "eval-verdict.md").read_text(encoding="utf-8"))

    def test_a_person_drives_by_default(self):
        code, out, err = self.run_eval("f")
        record = json.loads((self.repo.dir / "plans" / "f" / "eval.json").read_text(encoding="utf-8"))
        self.assertEqual(record["driver"], "person")
        self.assertIn("needed you: 1 stop(s)", out)

    def test_a_filled_form_lands_in_the_record(self):
        self.run_eval("f")
        form = self.repo.dir / "plans" / "f" / "eval-verdict.md"
        form.write_text(form.read_text(encoding="utf-8").replace("would-use-again: (yes | no)", "would-use-again: yes"),
                        encoding="utf-8")
        code, out, _ = self.run_eval("f")
        self.assertEqual(code, 0)
        record = json.loads((self.repo.dir / "plans" / "f" / "eval.json").read_text(encoding="utf-8"))
        self.assertEqual(record["verdict"]["would_use_again"], "yes")
        self.assertIn("your verdict", out)

    def test_later_finds_fix_commits_on_touched_paths(self):
        ticket = self.repo.dir / "plans" / "f" / "tasks" / "01-a.md"
        ticket.write_text(ticket.read_text(encoding="utf-8").replace("Test first: no", "Test first: no\nTouches: src/"),
                          encoding="utf-8")
        self.repo.commit("touches")
        (self.repo.dir / "src").mkdir()
        (self.repo.dir / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
        self.repo.commit("fix: the off by one in a")
        code, out, err = self.run_eval("f", "--later")
        self.assertEqual(code, 0, err)
        record = json.loads((self.repo.dir / "plans" / "f" / "eval.json").read_text(encoding="utf-8"))
        self.assertEqual(list(record["later"]["fix_commits"]), ["01"])
        self.assertIn("fixes since the run: 01 x1", out)

    def test_no_log_says_so_with_a_hint(self):
        code, _, err = self.run_eval("g")
        self.assertEqual(code, 2)
        self.assertIn("no run log for g", err)

    def test_bad_arguments_are_a_usage_error(self):
        self.assertEqual(self.run_eval("f", "--nope")[0], 2)
        self.assertEqual(self.run_eval()[0], 2)


if __name__ == "__main__":
    unittest.main()
