import shutil
import sys
import unittest

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import proof  # the package under test, from this checkout

FENCE = "```"


def ticket(done_when, after="## Answer\n"):
    return "# T\n\nType: task\nStatus: open\n\n## Done when\n\n- prose\n\n" + done_when + "\n" + after


def block(*lines, tag="check"):
    return FENCE + tag + "\n" + "".join(line + "\n" for line in lines) + FENCE + "\n"


class ChecksIn(unittest.TestCase):
    def test_default_exit_is_zero(self):
        checks = proof.checks_in(ticket(block("$ python3 -m unittest")))
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].command, "python3 -m unittest")
        self.assertEqual(checks[0].exit, 0)
        self.assertEqual(list(checks[0].prints), [])

    def test_exit_whole_number(self):
        checks = proof.checks_in(ticket(block("$ false", "exit 3")))
        self.assertEqual(checks[0].exit, 3)

    def test_exit_nonzero(self):
        checks = proof.checks_in(ticket(block("$ false", "exit nonzero")))
        self.assertEqual(checks[0].exit, "nonzero")

    def test_two_prints_lines(self):
        checks = proof.checks_in(ticket(block("$ python3 hello.py Ada", "prints Hello, Ada!", "prints done")))
        self.assertEqual(list(checks[0].prints), ["Hello, Ada!", "done"])

    def test_comment_and_blank_line_are_ignored(self):
        checks = proof.checks_in(ticket(block("# the greeting", "", "$ a", "", "# then b", "$ b", "exit 1")))
        self.assertEqual([(c.command, c.exit) for c in checks], [("a", 0), ("b", 1)])

    def test_several_blocks_in_order(self):
        text = ticket(block("$ a") + "\n- more prose\n\n" + block("$ b"))
        self.assertEqual([c.command for c in proof.checks_in(text)], ["a", "b"])

    def test_block_outside_done_when_is_ignored(self):
        text = "# T\n\n" + block("$ before") + "\n## Done when\n\n" + block("$ inside") + "\n## Answer\n\n" + block("$ after")
        self.assertEqual([c.command for c in proof.checks_in(text)], ["inside"])

    def test_bash_block_is_ignored(self):
        text = ticket(block("$ not a check", "whatever", tag="bash") + "\n" + block("$ real"))
        self.assertEqual([c.command for c in proof.checks_in(text)], ["real"])

    def test_crlf_text_reads_the_same(self):
        text = ticket(block("$ python3 hello.py Ada", "exit 2", "prints Hello, Ada!"))
        lf = proof.checks_in(text)
        crlf = proof.checks_in(text.replace("\n", "\r\n"))
        self.assertEqual(crlf, lf)
        self.assertEqual(crlf[0].command, "python3 hello.py Ada")
        self.assertEqual(list(crlf[0].prints), ["Hello, Ada!"])

    def test_no_block_returns_empty_list(self):
        self.assertEqual(proof.checks_in(ticket("")), [])
        self.assertEqual(proof.checks_in("# T\n\nno sections at all\n"), [])


class ParseErrors(unittest.TestCase):
    def assertParseError(self, text, quoted):
        with self.assertRaises(proof.ParseError) as caught:
            proof.checks_in(text)
        self.assertIsInstance(caught.exception, ValueError)
        self.assertIn(quoted, str(caught.exception))

    def test_unknown_line(self):
        self.assertParseError(ticket(block("$ a", "expect ok")), "expect ok")

    def test_exit_not_a_whole_number(self):
        self.assertParseError(ticket(block("$ a", "exit x")), "exit x")

    def test_prints_before_first_command(self):
        self.assertParseError(ticket(block("prints hi", "$ a")), "prints hi")

    def test_exit_before_first_command(self):
        self.assertParseError(ticket(block("exit 1", "$ a")), "exit 1")

    def test_second_exit_for_one_command(self):
        self.assertParseError(ticket(block("$ a", "exit 1", "exit 2")), "exit 2")

    def test_unclosed_fence(self):
        text = "# T\n\n## Done when\n\n" + FENCE + "check\n$ a\n\n## Answer\n"
        self.assertParseError(text, FENCE + "check")

    def test_unclosed_fence_at_end_of_text(self):
        self.assertParseError("# T\n\n## Done when\n\n" + FENCE + "check\n$ a\n", FENCE + "check")


T1 = "plans/f/tasks/01-a.md"
PY = '"%s"' % sys.executable


def py(code):
    return '%s -c "%s"' % (PY, code)


class RunChecks(unittest.TestCase):
    def test_a_check_that_sleeps_past_the_timeout_is_reported_as_timed_out(self):
        ok, report = proof.run_checks([proof.Check(py("import time; time.sleep(30)"))], 0.02)
        self.assertFalse(ok)
        self.assertIn("timed out after 0.02 minutes", report)

    def test_every_failure_is_reported_with_want_and_got(self):
        found = [proof.Check(py("print('hi'); raise SystemExit(1)"), 0, ("zzz",)),
                 proof.Check(py("pass"), "nonzero"),
                 proof.Check(py("print('ok')"), 0, ("ok",))]
        ok, report = proof.run_checks(found, 1)
        self.assertFalse(ok)
        self.assertIn("raise SystemExit(1)", report)
        self.assertIn("exit 1", report)
        self.assertIn("zzz", report)
        self.assertIn("hi", report)
        self.assertEqual(report.count("$ "), 2)

    def test_passing_checks(self):
        found = [proof.Check(py("raise SystemExit(3)"), 3), proof.Check(py("raise SystemExit(2)"), "nonzero"),
                 proof.Check(py("print('a')"), 0, ("a",))]
        self.assertEqual(proof.run_checks(found, 1), (True, ""))


class Conducted(unittest.TestCase):
    def setUp(self):
        self.repo = helpers.Repo()
        for folder in ("agents", "guides"):
            shutil.copytree(str(helpers.ROOT / folder), str(self.repo.path(folder)))
        self.repo.path("plans/f/commands.md").write_text(
            "# Commands: f\n\nTest: `%s`\nSmoke: `<the quickest command>`\n" % py("pass"), encoding="utf-8")
        self.repo.commit("setup")

    def tearDown(self):
        self.repo.close()

    def plan(self, done_when=""):
        path = self.repo.path(T1)
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("- x\n", "- x\n\n" + done_when), encoding="utf-8")
        self.repo.commit("plan")

    def build(self, **env):
        rc, out = self.repo.flow("next", **env)
        self.assertEqual(rc, 0, out)
        self.assertTrue(out.startswith("BUILD %s 01 " % T1), out)
        self.repo.resolve(T1)
        return self.repo.flow("next", **env)

    def test_a_failing_check_is_sent_back_before_review(self):
        self.plan(block("$ " + py("raise SystemExit(1)")))
        rc, out = self.build()
        self.assertEqual(rc, 0, out)
        self.assertTrue(out.startswith("BUILD %s 01 " % T1), out)
        self.assertIn("## Review findings (round 1, done when)", self.repo.path(T1).read_text(encoding="utf-8"))
        self.assertIn("raise SystemExit(1)", self.repo.path(T1).read_text(encoding="utf-8"))
        self.assertIn("DONEWHEN-FAIL", self.repo.log())
        self.assertNotIn("REVIEW", self.repo.log())

    def test_a_passing_check_reaches_review(self):
        self.plan(block("$ " + py("print('hello')"), "prints hello"))
        rc, out = self.build()
        self.assertTrue(out.startswith("REVIEW %s 01 " % T1), out)
        self.assertIn("DONEWHEN-PASS", self.repo.log())
        self.assertIn("The conductor notes: the conductor ran 1 Done when check(s) and all passed",
                      self.repo.flow("prompt")[1])

    def test_no_block_reaches_review_with_a_note(self):
        rc, out = self.build()
        self.assertTrue(out.startswith("REVIEW %s 01 " % T1), out)
        self.assertIn("DONEWHEN-SKIP", self.repo.log())
        self.assertIn("ran no Done when checks", self.repo.flow("prompt")[1])

    def test_a_block_the_parser_rejects_is_a_single_stop_line(self):
        self.plan(block("$ " + py("pass"), "exit x"))
        rc, out = self.build()
        self.assertEqual(rc, 1)
        self.assertEqual(len(out.splitlines()), 1, out)
        self.assertTrue(out.startswith("STOP "), out)
        self.assertIn("cannot read", out)

    def test_a_check_that_writes_a_file_is_a_stop_naming_it(self):
        self.plan(block("$ " + py("open('made-by-check.txt', 'w').write('x')")))
        rc, out = self.build()
        self.assertEqual(rc, 1)
        self.assertTrue(out.startswith("STOP "), out)
        self.assertIn("made-by-check.txt", out)

    def test_gate_off_skips_the_checks(self):
        self.plan(block("$ " + py("raise SystemExit(1)")))
        rc, out = self.build(FLOW_GATE="off")
        self.assertTrue(out.startswith("REVIEW %s 01 " % T1), out)
        self.assertNotIn("DONEWHEN-", self.repo.log())


if __name__ == "__main__":
    unittest.main()
