import os
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import proof, status  # the package under test, from this checkout


class Out:
    def __init__(self):
        self.text = ""

    def write(self, text):
        self.text += text


def ticket(review_line=""):
    return "# T\n\nType: task\n%sStatus: open\nBlocked by: —\n\n## Done when\n\n- x\n" % review_line


class ReviewModeTests(unittest.TestCase):
    def test_review_mode_full(self):
        self.assertEqual(proof.review_mode(ticket("Review: full\n")), "full")

    def test_review_mode_is_case_insensitive(self):
        self.assertEqual(proof.review_mode(ticket("Review: FULL\n")), "full")

    def test_review_mode_auto(self):
        self.assertEqual(proof.review_mode(ticket("Review: auto\n")), "auto")

    def test_review_mode_defaults_to_auto_without_a_line(self):
        self.assertEqual(proof.review_mode(ticket()), "auto")

    def test_review_mode_ignores_a_line_below_a_heading(self):
        self.assertEqual(proof.review_mode(ticket() + "\nReview: full\n"), "auto")

    def test_review_mode_other_value_is_auto(self):
        self.assertEqual(proof.review_mode(ticket("Review: maybe\n")), "auto")


class ReviewCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        Path("plans/f/tasks").mkdir(parents=True)

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def check(self, review_line):
        Path("plans/f/tasks/01-a.md").write_text(ticket(review_line), encoding="utf-8")
        out, err = Out(), Out()
        code = status.run(["f", "--check"], out, err)
        return code, out.text + err.text

    def test_maybe_fails_the_plan_check(self):
        code, text = self.check("Review: maybe\n")
        self.assertNotEqual(code, 0)
        self.assertIn("01: Review must be full or auto", text)

    def test_full_passes_the_plan_check(self):
        code, text = self.check("Review: full\n")
        self.assertEqual(code, 0, text)

    def test_auto_passes_the_plan_check(self):
        code, text = self.check("Review: auto\n")
        self.assertEqual(code, 0, text)


if __name__ == "__main__":
    unittest.main()
