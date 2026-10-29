"""0.23.0: with an `Acceptance:` line in commands.md, a tester writes acceptance tests from the spec before the
first ticket, the conductor checks them (only the acceptance folder changed, the gate still passes, the tests fail
now), the floor guard keeps builders out of them, and they run once every ticket is resolved. A failure becomes a
fix ticket, whose builder may dispute a test with the product owner; a test ruled wrong goes back to a tester.
"""

import shutil
import sys
import unittest

from helpers import ROOT, Repo

PYTHON = '"%s"' % sys.executable
CHECK = "```check\n$ %s -c \"print('fine')\"\nprints fine\n```\n\n" % PYTHON
T1 = "plans/f/tasks/01-t.md"
TEST_FILE = "plans/f/acceptance/check.py"
# passes once feature.txt says done, as a builder's work makes it
PASSES_WHEN_BUILT = ("import sys\ntry:\n    text = open('feature.txt').read().strip()\nexcept OSError:\n"
                     "    text = ''\nsys.exit(0 if text == 'done' else 1)\n")
# the test of round 2: it asks for 'done!', which the product owner rules wrong
ASKS_TOO_MUCH = PASSES_WHEN_BUILT.replace("== 'done'", "== 'done!'")


class TesterDrive(unittest.TestCase):
    def setup(self, acceptance=True, test=None, **env):
        repo = Repo(tickets=())
        self.addCleanup(repo.close)
        env = dict({"FLOW_TICKETS_PER_SESSION": "99", "FLOW_SCOUTS": "off"}, **env)
        for folder in ("agents", "guides"):
            shutil.copytree(str(ROOT / folder), str(repo.path(folder)))
        commands = "# Commands: f\n\nSmoke: `%s -c \"pass\"`\nTest: `%s`\n" % (PYTHON, test or "%s -c \"pass\"" % PYTHON)
        if acceptance:
            commands += "Acceptance: `%s %s`\n" % (PYTHON, TEST_FILE)
        repo.path("plans/f/commands.md").write_text(commands, encoding="utf-8")
        repo.path("plans/f/spec.md").write_text("# Spec\n\n## Stories\n\n- [ ] feature.txt says done\n",
                                                encoding="utf-8")
        repo.path(T1).write_text("# T1\n\nType: task\nStatus: open\nBlocked by: —\nTest first: no\nLevel: 2\n\nbody\n\n"
                                 "## Done when\n\n- x\n\n" + CHECK + "## Answer\n", encoding="utf-8")
        repo.commit("plan")
        rc, out = repo.flow("start", **env)
        env["FLOW_SESSION"] = out.split()[1]
        self.reply = repo.dir.parent / (repo.dir.name + "-reply.txt")
        self.addCleanup(self.reply.unlink, missing_ok=True)
        self.repo, self.env = repo, env
        return repo

    def flow(self, *args):
        return self.repo.flow(*args, **self.env)

    def write_tests(self, text=PASSES_WHEN_BUILT, name=TEST_FILE, message="test(f): acceptance tests"):
        path = self.repo.path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.repo.commit(message)

    def build(self, rel, content="done"):
        self.repo.path("feature.txt").write_text(content + "\n", encoding="utf-8")
        self.repo.set_status(rel, "resolved")
        self.repo.commit("feat: work")
        return self.flow("next")

    def verdict(self, text):
        self.reply.write_text(text, encoding="utf-8")
        return self.flow("verdict", str(self.reply))

    def review_passes(self):
        self.assertEqual(self.verdict("fine\nREVIEW: PASS\n"), (0, "OK"))
        return self.flow("next")

    def test_the_tester_writes_the_tests_first_and_they_run_once_every_ticket_is_resolved(self):
        repo = self.setup()
        base = repo.head()
        self.assertEqual(self.flow("next"), (0, "TEST plans/f %s" % base))
        prompt = self.flow("prompt")[1]
        self.assertIn("You are the tester", prompt)
        self.assertIn("Never read `plans/f/tasks/`", prompt)
        self.assertIn("write the acceptance tests of the feature `f`", prompt)
        self.assertIn("plans/f/acceptance/", prompt)
        self.assertNotIn("01-t", prompt)  # no ticket reaches the tester
        self.assertEqual(self.flow("verdict", "x")[0], 2)  # the conductor judges the tests, not a verdict
        self.write_tests()
        rc, line = self.flow("next")
        self.assertTrue(line.startswith("BUILD %s 01 " % T1), line)
        self.assertIn("TEST-WRITTEN", repo.log())
        self.assertTrue(self.build(T1)[1].startswith("REVIEW "))
        rc, out = self.review_passes()
        self.assertTrue(out.startswith("DONE f is complete"), out)
        self.assertIn("ACCEPT-PASS", repo.log())

    def test_no_acceptance_line_means_no_tester(self):
        repo = self.setup(acceptance=False)
        self.assertTrue(self.flow("next")[1].startswith("BUILD %s 01 " % T1))
        self.assertTrue(self.build(T1)[1].startswith("REVIEW "))
        self.assertTrue(self.review_passes()[1].startswith("DONE"))
        self.assertNotIn("TEST-", repo.log())
        self.assertNotIn("ACCEPT-", repo.log())

    def test_tests_that_already_pass_go_back_to_a_fresh_tester_then_stop(self):
        repo = self.setup()
        self.flow("next")
        self.write_tests("import sys\nsys.exit(0)\n")
        rc, line = self.flow("next")
        self.assertTrue(line.startswith("TEST plans/f "), line)
        self.assertIn("they cannot fail", self.flow("prompt")[1])
        rc, out = self.flow("next")
        self.assertEqual(rc, 1)
        self.assertIn("STOP the tester of f did not finish after 2 attempt(s)", out)

    def test_tests_the_gate_runs_go_back_to_the_tester(self):
        test = "%s -c \"import os,sys; sys.exit(1 if os.path.exists('plans/f/acceptance/check.py') else 0)\"" % PYTHON
        repo = self.setup(test=test)
        self.flow("next")
        self.write_tests()
        rc, line = self.flow("next")
        self.assertTrue(line.startswith("TEST plans/f "), line)
        self.assertIn("the gate fails", self.flow("prompt")[1])
        self.assertIn("TEST-GATE-FAIL", repo.log())

    def test_a_tester_that_changes_files_outside_its_folder_stops_the_run(self):
        repo = self.setup()
        self.flow("next")
        repo.path("src.py").write_text("x = 1\n", encoding="utf-8")
        self.write_tests()
        rc, out = self.flow("next")
        self.assertEqual(rc, 1)
        self.assertIn("the tester of f changed src.py, outside plans/f/acceptance/", out)
        self.assertIn("git reset --hard", out)

    def test_a_builder_may_not_change_the_acceptance_tests(self):
        repo = self.setup(FLOW_MAX_RETRIES="3")
        self.flow("next")
        self.write_tests()
        self.flow("next")
        repo.path(TEST_FILE).write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
        rc, line = self.build(T1)
        self.assertTrue(line.startswith("BUILD %s 01 " % T1), line)
        ticket = repo.path(T1).read_text(encoding="utf-8")
        self.assertIn("acceptance-edit: %s" % TEST_FILE, ticket)

    def test_a_failing_run_becomes_a_fix_ticket_built_like_any_other(self):
        repo = self.setup()
        self.flow("next")
        self.write_tests()
        self.flow("next")
        self.build(T1, content="half")  # the builder missed what the spec asked
        rc, line = self.review_passes()
        fix = "plans/f/tasks/02-acceptance-fixes-1.md"
        self.assertTrue(line.startswith("BUILD %s 02 " % fix), line)
        self.assertIn("ACCEPT-FAIL", repo.log())
        text = repo.path(fix).read_text(encoding="utf-8")
        self.assertIn("Make the acceptance tests pass, round 1", text)
        self.assertIn("## Ask: po", text)
        self.assertEqual(repo.porcelain(), "")
        self.assertTrue(self.build(fix)[1].startswith("REVIEW "))
        rc, out = self.review_passes()
        self.assertTrue(out.startswith("DONE f is complete"), out)
        self.assertEqual(repo.log().count("ACCEPT-PASS"), 1)

    def test_a_test_the_product_owner_rules_wrong_goes_back_to_the_tester(self):
        repo = self.setup()
        self.flow("next")
        self.write_tests(ASKS_TOO_MUCH)
        self.flow("next")
        self.build(T1)
        rc, line = self.review_passes()
        fix = "plans/f/tasks/02-acceptance-fixes-1.md"
        self.assertTrue(line.startswith("BUILD %s 02 " % fix), line)
        with open(str(repo.path(fix)), "a", encoding="utf-8") as handle:
            handle.write("\n## Ask: po\n\ncheck.py wants 'done!', but the spec says 'done'.\n")
        repo.commit("ask")
        rc, line = self.flow("next")
        self.assertEqual(line.split()[:2], ["ASK", "po"])
        self.assertIn("RULING: TEST WRONG", self.flow("prompt")[1])
        self.assertEqual(self.verdict("## Answer\n\nThe spec says done.\n\nRULING: TEST WRONG\n\nANSWER: GIVEN\n"),
                         (0, "OK"))
        rc, line = self.flow("next")
        self.assertTrue(line.startswith("BUILD %s 02 " % fix), line)
        text = repo.path(fix).read_text(encoding="utf-8")
        self.assertIn("The product owner ruled the test wrong", text)
        self.assertNotIn("RULING:", text)
        self.assertIn("RULING-TEST", repo.log())
        repo.set_status(fix, "resolved")
        repo.commit("feat: nothing to fix in the code")
        line = self.flow("next")[1]
        self.assertTrue(line.startswith("REVIEW "), (line, repo.log()[-1500:]))
        rc, line = self.review_passes()
        self.assertTrue(line.startswith("TEST plans/f "), line)
        prompt = self.flow("prompt")[1]
        self.assertIn("the product owner ruled some acceptance tests of the feature `f` wrong", prompt)
        self.assertIn("check.py wants 'done!', but the spec says 'done'.", prompt)
        self.assertIn("The spec says done.", prompt)
        self.write_tests(PASSES_WHEN_BUILT, message="test(f): acceptance tests changed as the product owner ruled")
        rc, out = self.flow("next")
        self.assertTrue(out.startswith("DONE f is complete"), out)
        self.assertIn("TEST-FIXED", repo.log())
        self.assertIn("ACCEPT-PASS", repo.log())

    def test_a_code_wrong_ruling_changes_no_test(self):
        repo = self.setup()
        self.flow("next")
        self.write_tests()
        self.flow("next")
        self.build(T1, content="half")
        fix = "plans/f/tasks/02-acceptance-fixes-1.md"
        self.review_passes()
        with open(str(repo.path(fix)), "a", encoding="utf-8") as handle:
            handle.write("\n## Ask: po\n\nMust it say done?\n")
        repo.commit("ask")
        self.flow("next")
        self.verdict("## Answer\n\nYes, the spec says done.\n\nRULING: CODE WRONG\n\nANSWER: GIVEN\n")
        self.assertTrue(self.flow("next")[1].startswith("BUILD %s 02 " % fix))
        self.assertIn("RULING-CODE", repo.log())
        self.assertEqual(repo.state().get("accept_rulings", ""), "")

    def test_the_acceptance_run_stops_after_the_rounds(self):
        repo = self.setup(FLOW_MAX_REVIEW_ROUNDS="1")
        self.flow("next")
        self.write_tests()
        self.flow("next")
        self.build(T1, content="half")
        rc, line = self.review_passes()
        fix = "plans/f/tasks/02-acceptance-fixes-1.md"
        self.build(fix, content="still half")
        rc, out = self.review_passes()
        self.assertEqual(rc, 1)
        self.assertIn("STOP the acceptance tests of f still fail after 1 round(s) of fixes", out)

    def test_the_tester_has_no_lane(self):
        repo = self.setup(FLOW_LANES="2")
        rc, line = self.flow("next")
        self.assertTrue(line.startswith("TEST plans/f "), line)
        self.assertEqual(self.flow("prompt", "1")[0], 1)
        self.write_tests()
        rc, line = self.flow("next")
        self.assertTrue(line.startswith("BUILD %s 01 " % T1) and line.endswith(" 1"), line)


if __name__ == "__main__":
    unittest.main()
