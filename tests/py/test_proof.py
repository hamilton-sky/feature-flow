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


if __name__ == "__main__":
    unittest.main()
