"""0.20.0: runs an agent drives, the follow-ups a run leaves, and argument mistakes that say what to do."""

import json
import shutil
import subprocess
import sys
import unittest

from helpers import ROOT, Repo

T1 = "plans/f/tasks/01-a.md"
T2 = "plans/f/tasks/02-b.md"
FAILING = "%s -c \"raise SystemExit(1)\"" % sys.executable.replace("\\", "/")


class AgentDriven(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        for folder in ("agents", "guides"):
            shutil.copytree(str(ROOT / folder), str(self.repo.path(folder)))
        self.repo.commit("prompts")

    def tearDown(self):
        self.repo.close()

    def reply(self, text):
        path = self.repo.dir.parent / (self.repo.dir.name + "-reply.txt")
        path.write_text(text, encoding="utf-8")
        self.addCleanup(path.unlink, missing_ok=True)
        return self.repo.flow("verdict", str(path))

    def per_session(self, **env):
        code = ("import os, sys; sys.path.insert(0, %r); os.environ.update(%r)\n"
                "from feature_flow.conductor import Conductor\nprint(Conductor('f', 'scripts').per_session)"
                % (str(ROOT), env))
        out = subprocess.run([sys.executable, "-c", code], cwd=str(self.repo.dir), stdout=subprocess.PIPE,
                             universal_newlines=True, check=True).stdout
        return int(out.strip())

    def test_an_agent_driver_never_hands_off_unless_told_to(self):
        self.assertEqual(self.per_session(), 4)
        self.assertEqual(self.per_session(FLOW_DRIVER="agent"), 0)
        self.assertEqual(self.per_session(FLOW_DRIVER="agent", FLOW_PROFILE="fast"), 0)  # a profile's 6 does not count
        self.assertEqual(self.per_session(FLOW_DRIVER="agent", FLOW_TICKETS_PER_SESSION="2"), 2)

    def test_start_records_the_driver(self):
        rc, out = self.repo.flow("start", FLOW_DRIVER="agent")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.repo.state()["driver"], "agent")
        self.assertIn("DRIVER-AGENT", self.repo.log())
        self.assertEqual(self.per_session(), 0)  # read back from the run state on later calls
        self.assertEqual(self.repo.flow("start", FLOW_DRIVER="robot", FLOW_TAKEOVER="1"),
                         (1, "STOP FLOW_DRIVER must be person or agent, not robot"))

    def test_next_without_a_verdict_changes_nothing_and_says_so(self):
        self.repo.flow("next")
        self.repo.resolve(T1)
        rc, review = self.repo.flow("next")
        self.assertTrue(review.startswith("REVIEW "), review)
        before = self.repo.state()
        result = subprocess.run([sys.executable, self.repo.script, "f", "next"], cwd=str(self.repo.dir),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                                env=dict(__import__("os").environ, FLOW_TRUSTED="1"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("no verdict recorded for the review of 01-a: save the reviewer's whole reply", result.stderr)
        self.assertEqual(self.repo.state()["review_attempt"], before["review_attempt"])
        self.assertEqual(self.reply("fine\nREVIEW: PASS\n"), (0, "OK"))
        self.assertTrue(self.repo.flow("next")[1].startswith("REVIEW "))

    def test_verdict_without_its_file_says_what_it_needs(self):
        result = subprocess.run([sys.executable, self.repo.script, "f", "verdict"], cwd=str(self.repo.dir),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("verdict needs the file the reviewer's whole reply was saved to: verdict <file> [lane]",
                      result.stderr)
        result = subprocess.run([sys.executable, self.repo.script, "f", "next", "--after-build", "x", "y"],
                                cwd=str(self.repo.dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True)
        self.assertIn("--after-build is flow-trust.py's: flow-trust.py --after-build <ticket> <sha> f next",
                      result.stderr)

    def test_minor_findings_of_a_passing_review_go_to_followups(self):
        self.repo.flow("next")
        self.repo.resolve(T1)
        self.repo.flow("next")
        self.assertEqual(self.reply("1. minor work.txt: a nit - tidy it\n\nREVIEW: PASS\n"), (0, "OK"))
        self.assertTrue(self.repo.flow("next")[1].startswith("REVIEW "))  # the quality pass
        self.assertEqual(self.reply("1. minor work.txt: another - later\nREVIEW: PASS\n"), (0, "OK"))
        rc, out = self.repo.flow("next")
        self.assertTrue(out.startswith("BUILD %s 02 " % T2), out)
        text = self.repo.path("plans/f/followups.md").read_text(encoding="utf-8")
        self.assertIn("## 01-a (left for later)", text)
        self.assertIn("- 1. minor work.txt: a nit - tidy it (spec review)", text)
        self.assertIn("- 1. minor work.txt: another - later (quality review)", text)
        self.assertEqual(self.repo.porcelain(), "")
        self.assertIn("FOLLOWUPS 2", self.repo.log())

    def test_a_failed_review_drops_the_minors_of_its_round(self):
        self.repo.flow("next")
        self.repo.resolve(T1)
        self.repo.flow("next")
        self.reply("1. minor work.txt: a nit - tidy it\nREVIEW: PASS\n")
        self.repo.flow("next")
        self.reply("1. blocker work.txt: broken - fix it\nREVIEW: FAIL\n")
        self.assertTrue(self.repo.flow("next")[1].startswith("BUILD %s 01 " % T1))
        self.assertEqual(self.repo.state().get("due_minors", ""), "")

    def test_a_check_that_needs_the_network_is_deferred_not_failed(self):
        ticket = self.repo.path(T1)
        ticket.write_text(ticket.read_text(encoding="utf-8").replace(
            "- x\n", "- x\n\n```check\n$ %s\nneeds network\n```\n" % FAILING), encoding="utf-8")
        self.repo.commit("a check that needs the network")
        self.repo.flow("next")
        self.repo.resolve(T1)
        rc, out = self.repo.flow("next")
        self.assertTrue(out.startswith("REVIEW %s 01 " % T1), out)
        self.assertIn("DONEWHEN-DEFERRED 1", self.repo.log())
        prompt = self.repo.flow("prompt")[1]
        self.assertIn("1 that need what this host lacks did not pass and are deferred, not met", prompt)
        self.reply("fine\nREVIEW: PASS\n")
        self.repo.flow("next")
        self.reply("fine\nREVIEW: PASS\n")
        self.assertTrue(self.repo.flow("next")[1].startswith("BUILD %s 02 " % T2))
        text = self.repo.path("plans/f/followups.md").read_text(encoding="utf-8")
        self.assertIn("- deferred check, needs network: `%s` (here: exit 1)" % FAILING, text)

    def test_a_check_without_needs_still_fails_the_build(self):
        ticket = self.repo.path(T1)
        ticket.write_text(ticket.read_text(encoding="utf-8").replace(
            "- x\n", "- x\n\n```check\n$ %s\n```\n" % FAILING), encoding="utf-8")
        self.repo.commit("a failing check")
        self.repo.flow("next")
        self.repo.resolve(T1)
        self.assertTrue(self.repo.flow("next")[1].startswith("BUILD %s 01 " % T1))


if __name__ == "__main__":
    unittest.main()
