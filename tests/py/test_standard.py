"""The standard profile and the 0.30.0 run fixes, driven through the CLI the way the skill does: the gate once at
the base, two reviewers side by side on each ticket, one review of the whole round at the end, prompts written to a
file, an install refused while a run is open, and where the run's time went.
"""

import datetime
import hashlib
import io
import json
import shutil
import sys
import unittest
from pathlib import Path

from helpers import ROOT, Repo

sys.path.insert(0, str(ROOT))
from feature_flow import evaluate, install  # noqa: E402

PYTHON = '"%s"' % sys.executable
CHECK = "```check\n$ %s -c \"print('fine')\"\nprints fine\n```\n\n" % PYTHON
T1 = "plans/f/tasks/01-t.md"
T2 = "plans/f/tasks/02-u.md"


def ticket(title, blocked):
    return ("# %s\n\nType: task\nStatus: open\nBlocked by: %s\nTest first: no\nLevel: 2\n\nbody\n\n"
            "## Done when\n\n- x\n\n%s## Answer\n" % (title, blocked, CHECK))


class StandardDrive(unittest.TestCase):
    def setup(self, test="pass", two=False, **env):
        repo = Repo(tickets=())
        self.addCleanup(repo.close)
        env = dict({"FLOW_TICKETS_PER_SESSION": "99", "FLOW_SCOUTS": "off"}, **env)
        for folder in ("agents", "guides"):
            shutil.copytree(str(ROOT / folder), str(repo.path(folder)))
        repo.path("plans/f/commands.md").write_text(
            "# Commands: f\n\nSmoke: `%s -c \"pass\"`\nTest: `%s -c \"%s\"`\n" % (PYTHON, PYTHON, test),
            encoding="utf-8")
        repo.path(T1).write_text(ticket("T1", "—"), encoding="utf-8")
        if two:
            repo.path(T2).write_text(ticket("T2", "01"), encoding="utf-8")
        repo.commit("plan")
        rc, out = repo.flow("start", **env)
        self.assertEqual(rc, 0, out)
        env["FLOW_SESSION"] = out.split()[1]
        self.reply = repo.dir.parent / (repo.dir.name + "-reply.txt")
        self.addCleanup(self.reply.unlink, missing_ok=True)
        self.repo, self.env = repo, env
        return repo

    def flow(self, *args):
        return self.repo.flow(*args, **self.env)

    def verdict(self, text):
        self.reply.write_text(text, encoding="utf-8")
        return self.flow("verdict", str(self.reply))

    def test_a_red_base_stops_before_the_first_ticket(self):
        repo = self.setup(test="import sys; sys.exit(1)", FLOW_BASE_GATE="on")
        rc, out = self.flow("next")
        self.assertEqual(rc, 1)
        self.assertIn("the base is already red", out)
        self.assertTrue(repo.path(".feature-flow/state/f.base-gate.log").exists())
        self.assertIn("BASE-GATE-FAIL", repo.log())

    def test_a_green_base_is_checked_once(self):
        repo = self.setup(FLOW_BASE_GATE="on", two=True)
        self.assertTrue(self.flow("next")[1].startswith("BUILD %s" % T1))
        repo.resolve(T1)
        self.assertTrue(self.flow("next")[1].startswith("REVIEW"))
        self.assertEqual(self.verdict("fine\nREVIEW: PASS\n"), (0, "OK"))
        self.assertTrue(self.flow("next")[1].startswith("BUILD %s" % T2))
        self.assertEqual(repo.log().count("BASE-GATE-PASS"), 1)

    def test_without_the_setting_no_base_gate_runs(self):
        repo = self.setup(test="import sys; sys.exit(1)")
        self.assertTrue(self.flow("next")[1].startswith("BUILD"))
        self.assertNotIn("BASE-GATE", repo.log())

    def pair(self):
        repo = self.setup(FLOW_PROFILE="standard")
        self.flow("next")
        repo.resolve(T1)
        rc, line = self.flow("next")
        self.assertTrue(line.startswith("REVIEW %s 01 " % T1) and line.endswith(" pair"), line)
        self.assertIn("REVIEW-PAIR", repo.log())
        return repo

    def test_two_reviewers_get_one_prompt_each_side_by_side(self):
        self.pair()
        prompt = self.flow("prompt")[1]
        self.assertEqual(prompt.count("=== SECOND REVIEWER ==="), 1)
        first, second = prompt.split("=== SECOND REVIEWER ===")
        self.assertIn("do the quality review only", first)
        self.assertIn("do the spec checklist only", second)

    def test_a_blocker_from_either_reviewer_sends_the_ticket_back(self):
        repo = self.pair()
        self.assertEqual(self.verdict("fine\nREVIEW: PASS\n\n=== SECOND REVIEWER ===\n\n"
                                      "1. blocker: the export drops the header row\n\nREVIEW: FAIL\n"), (0, "OK"))
        rc, line = self.flow("next")
        self.assertTrue(line.startswith("BUILD %s" % T1), line)
        self.assertIn("drops the header row", repo.path(T1).read_text(encoding="utf-8")
                      + self.flow("prompt")[1])

    def test_only_majors_pass_the_ticket_with_follow_ups(self):
        repo = self.pair()
        self.assertEqual(self.verdict("1. major: a long function\n\nREVIEW: FAIL\n\n=== SECOND REVIEWER ===\n\n"
                                      "fine\nREVIEW: PASS\n"), (0, "OK"))
        rc, line = self.flow("next")
        self.assertFalse(line.startswith("BUILD"), line)
        self.assertIn("a long function", repo.path("plans/f/followups.md").read_text(encoding="utf-8"))

    def test_one_reply_of_two_is_not_a_verdict(self):
        self.pair()
        self.verdict("fine\nREVIEW: PASS\n")
        rc, line = self.flow("next")
        self.assertNotEqual(line.split()[0], "BUILD")
        self.assertNotIn("DONE", line)

    def test_the_whole_round_is_reviewed_once_at_the_end(self):
        repo = self.pair()
        self.assertEqual(self.verdict("fine\nREVIEW: PASS\n\n=== SECOND REVIEWER ===\n\nfine\nREVIEW: PASS\n"),
                         (0, "OK"))
        rc, line = self.flow("next")
        self.assertTrue(line.startswith("REVIEW plans/f all "), line)
        self.assertIn("this review is of the whole round", self.flow("prompt")[1])
        self.assertEqual(self.verdict("fine\nREVIEW: PASS\n"), (0, "OK"))
        rc, out = self.flow("next")
        self.assertTrue(out.startswith("DONE f is complete"), out)
        self.assertIn("FEATURE-PASS", repo.log())

    def test_a_prompt_can_be_written_to_a_file(self):
        repo = self.setup()
        self.flow("next")
        text = self.flow("prompt")[1]
        rc, out = self.flow("prompt", "file")
        self.assertEqual(rc, 0, out)
        lines = out.splitlines()
        self.assertTrue(lines and all(line.startswith("PROMPT-FILE ") for line in lines), out)
        _, path, sha = lines[0].split()
        data = Path(path).read_bytes() if Path(path).is_absolute() else repo.path(path).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), sha)
        self.assertEqual(data.decode("utf-8").strip(), text.strip())
        self.assertEqual(repo.porcelain(), "")

    def test_a_done_when_check_that_is_the_gate_command_is_not_run_twice(self):
        repo = self.setup()
        text = repo.path(T1).read_text(encoding="utf-8")
        repo.path(T1).write_text(text.replace(CHECK, "```check\n$ %s -c \"pass\"\n```\n\n" % PYTHON),
                                 encoding="utf-8")
        repo.commit("plan: the check is the test command")
        self.flow("next")
        repo.resolve(T1)
        self.assertTrue(self.flow("next")[1].startswith("REVIEW"))
        self.assertIn("DONEWHEN-GATE", repo.log())
        self.assertIn("MET (conductor)", self.flow("prompt")[1])

    def test_a_repair_re_plan_reopens_the_stopped_ticket(self):
        repo = self.setup(two=True)
        self.assertTrue(self.flow("next")[1].startswith("BUILD %s" % T1))
        rc, prompt = self.flow("replan-prompt", "repair")
        self.assertEqual(rc, 0, prompt)
        self.assertIn("01", prompt)
        repo.path(T1).write_text(ticket("T1 as it can be built", "—"), encoding="utf-8")
        repo.commit("plan(f): repair 01")
        rc, line = self.flow("next")
        self.assertTrue(line.startswith("BUILD %s" % T1), line)
        self.assertIn("REPAIR", repo.log())

    def test_a_repair_after_the_ticket_has_code_stops(self):
        repo = self.setup(two=True)
        self.flow("next")
        self.assertEqual(self.flow("replan-prompt", "repair")[0], 0)
        repo.path("work.txt").write_text("half done\n", encoding="utf-8")
        repo.commit("feat: half")
        repo.path(T1).write_text(ticket("T1 again", "—"), encoding="utf-8")
        repo.commit("plan(f): repair 01")
        rc, out = self.flow("next")
        self.assertEqual(rc, 1, out)


class InstallWhileRunning(unittest.TestCase):
    def test_an_install_into_a_repo_with_an_open_run_is_refused(self):
        repo = Repo()
        self.addCleanup(repo.close)
        repo.flow("start")
        out, err = io.StringIO(), io.StringIO()
        self.assertEqual(install.run([str(repo.dir)], ROOT, out.write, err.write), 2)
        self.assertIn("a feature-flow run is open", err.getvalue())
        self.assertIn("(f)", err.getvalue())

    def test_no_open_run_finds_nothing(self):
        repo = Repo()
        self.addCleanup(repo.close)
        self.assertEqual(install.open_runs(str(repo.dir)), [])


class Timing(unittest.TestCase):
    def rows(self):
        start = datetime.datetime(2026, 10, 29, 10, 0)
        events = [(0, "-", "START"), (1, "01", "BUILD"), (11, "01", "CHECKS"), (11, "01", "GATE-FULL"),
                  (13, "01", "REVIEW"), (18, "02", "BUILD"), (20, "02", "CHECKS"), (21, "02", "REVIEW"),
                  (24, "-", "DONE")]
        return [(start + datetime.timedelta(minutes=m), n, e, "") for m, n, e in events]

    def test_the_wall_clock_is_split_by_phase_ticket_and_level(self):
        result = evaluate.timing(self.rows(), {"01": {"level": 2}, "02": {"level": 1}})
        self.assertEqual(result["wall_minutes"], 24)
        self.assertEqual(result["by_phase"]["build"], 12)
        self.assertEqual(result["by_phase"]["checks"], 3)
        self.assertEqual(result["by_phase"]["review"], 8)
        self.assertEqual(result["by_ticket"]["01"], {"build": 10, "checks": 2, "review": 5})
        self.assertEqual(result["by_level"], {"1": 6, "2": 17})
        self.assertEqual(result["slowest"], {"ticket": "01", "minutes": 17, "most_in": "build"})
        self.assertEqual(result["full_test_runs"], {"01": 1})

    def test_a_log_without_dates_has_no_timing(self):
        self.assertIsNone(evaluate.timing([(None, "01", "BUILD", "")], {}))

    def test_compare_puts_earlier_runs_beside_this_one(self):
        earlier = Path(self.id().replace(".", "-") + ".json")
        tmp = Path(__file__).resolve().parent / earlier
        self.addCleanup(tmp.unlink, missing_ok=True)
        tmp.write_text(json.dumps({"feature": "old", "timing": {"wall_minutes": 90, "by_phase": {"build": 50}},
                                   "totals": {"tickets": 4}}), encoding="utf-8")
        err = io.StringIO()
        text = evaluate.compare({"feature": "f", "timing": {"wall_minutes": 30}, "totals": {"tickets": 4}},
                                [str(tmp), str(tmp) + ".missing"], err)
        self.assertIn("this run: f, 30 min wall", text)
        self.assertIn("old, 90 min wall (build 50", text)
        self.assertIn("cannot read", err.getvalue())


if __name__ == "__main__":
    unittest.main()
