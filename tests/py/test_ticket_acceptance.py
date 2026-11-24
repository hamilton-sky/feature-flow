"""A ticket's own acceptance tests gate it: the `Acceptance:` header line names them, the conductor runs them after
the Done when checks, and a failure sends the ticket back before any review. A ticket without the line keeps the
advisory run, which now reaches the spec reviewer and not only a pair review.

In the field two tickets passed both reviews while five of their own acceptance tests failed; the failures surfaced
only after the last ticket, as a new ticket and three more review rounds."""

import sys
import unittest

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow.verify import proof  # noqa: E402
from test_phases import ACCEPT, PASSES_WHEN_BUILT, PYTHON, T1, Session, ticket  # noqa: E402

COMMANDS = ("Smoke: `%s -c \"pass\"`\nTest: `%s -c \"pass\"`\nAcceptance: `%s %s`\n"
            % (PYTHON, PYTHON, PYTHON, ACCEPT))
MAPPED = "Acceptance: `%s %s`" % (PYTHON, ACCEPT)


def write_tests(repo):
    repo.path(ACCEPT).parent.mkdir(parents=True)
    repo.path(ACCEPT).write_text(PASSES_WHEN_BUILT, encoding="utf-8")
    repo.commit("test(f): acceptance tests")


class ParseTheLine(unittest.TestCase):
    def test_the_header_line_is_read_and_a_body_line_is_not(self):
        self.assertEqual(proof.acceptance_line("# T\n\nAcceptance: `pytest a.py -q`\n\n## Done when\n"), "pytest a.py -q")
        self.assertEqual(proof.acceptance_line("# T\nAcceptance: $ pytest a.py\n"), "pytest a.py")
        self.assertEqual(proof.acceptance_line("# T\nAcceptance: —\n"), "")
        self.assertEqual(proof.acceptance_line("# T\n\n## Done when\n\nAcceptance: pytest a.py\n"), "")
        self.assertEqual(proof.acceptance_line("# T\nLevel: 2\n"), "")


class Gate(unittest.TestCase):
    def test_a_ticket_whose_own_tests_fail_goes_back_before_review(self):
        s = Session(self, [(T1, ticket("A", "—", ["Level: 2", MAPPED]))], COMMANDS)
        repo = s.repo
        self.assertTrue(s.next().startswith("TEST plans/f "))
        write_tests(repo)
        self.assertTrue(s.next().startswith("BUILD %s 01 " % T1))
        repo.resolve(T1)  # built, but feature.txt is not "done": its acceptance test fails
        self.assertTrue(s.next().startswith("BUILD %s 01 " % T1))
        text = repo.path(T1).read_text(encoding="utf-8")
        self.assertIn("acceptance tests", text)
        self.assertIn("## Ask: po", text)
        repo.path("feature.txt").write_text("done\n", encoding="utf-8")
        repo.resolve(T1)
        self.assertTrue(s.next().startswith("REVIEW %s 01 " % T1))
        self.assertIn("ACCEPT-TICKET-FAIL", self.log(repo))
        self.assertIn("ACCEPT-TICKET-PASS", self.log(repo))

    def test_without_the_line_the_spec_reviewer_sees_the_failing_run(self):
        full = ["Level: 2", "Review: full"]  # a spec pass, then a quality pass: no pair review
        s = Session(self, [(T1, ticket("A", "—", full))], COMMANDS)
        repo = s.repo
        self.assertTrue(s.next().startswith("TEST plans/f "))
        write_tests(repo)
        self.assertTrue(s.next().startswith("BUILD %s 01 " % T1))
        repo.resolve(T1)
        self.assertTrue(s.next().startswith("REVIEW %s 01 " % T1))  # advisory: not sent back
        notes = repo.state().get("review_notes", "")
        self.assertIn("ran the acceptance tests", notes)
        self.assertIn("they fail", notes)

    def test_a_mapped_ticket_before_the_tests_exist_is_not_blocked(self):
        s = Session(self, [(T1, ticket("A", "—", ["Level: 2", MAPPED]))],
                    "Smoke: `%s -c \"pass\"`\nTest: `%s -c \"pass\"`\n" % (PYTHON, PYTHON))
        self.assertTrue(s.next().startswith("BUILD %s 01 " % T1))
        s.repo.resolve(T1)
        self.assertTrue(s.next().startswith("REVIEW %s 01 " % T1))
        self.assertIn("ACCEPT-TICKET-SKIP", self.log(s.repo))

    @staticmethod
    def log(repo):
        found = sorted(repo.dir.glob(".feature-flow/state/*.log")) + sorted(repo.dir.glob(".feature-flow/**/*.log"))
        return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in found)


if __name__ == "__main__":
    unittest.main()
