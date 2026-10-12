import os
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import floorguard, status  # the package under test, from this checkout

CHECKED = "\n```check\n$ true\n```\n"


class Out:
    def __init__(self):
        self.text = ""

    def write(self, text):
        self.text += text


class LintTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        self.plan = Path("plans/f")
        (self.plan / "tasks").mkdir(parents=True)
        self.commands("Test: `python3 -c pass`\n")

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def commands(self, text):
        (self.plan / "commands.md").write_text("# Commands: f\n\n" + text, encoding="utf-8")

    def ticket(self, slug, extra_header="", body="", kind="task"):
        text = ("# T\n\nType: %s\nStatus: open\nBlocked by: —\nTest first: no\n%s\n%s\n\n## Done when\n\n- x\n%s"
                % (kind, extra_header, "body", body))
        (self.plan / "tasks" / ("%s.md" % slug)).write_text(text, encoding="utf-8")

    def lint(self, mode="--lint"):
        out, err = Out(), Out()
        code = status.run(["f", mode], out, err)
        return code, out.text

    def test_a_ticket_with_a_check_block_passes(self):
        self.ticket("01-a", body=CHECKED)
        self.assertEqual(self.lint()[0], 0)

    def test_a_ticket_without_a_check_block_fails_lint_but_not_check(self):
        self.ticket("01-a")
        code, out = self.lint()
        self.assertEqual(code, 1)
        self.assertIn("01: no check block", out)
        self.assertEqual(self.lint("--check")[0], 0)

    def test_check_none_needs_a_reason(self):
        self.ticket("01-a", extra_header="Check: none\n")
        self.assertIn("must read `Check: none <why>`", self.lint()[1])
        self.ticket("01-a", extra_header="Check: none a pure rename, the tests cover it\n")
        self.assertEqual(self.lint()[0], 0)

    def test_a_settle_ticket_needs_no_check(self):
        self.ticket("01-a", kind="settle")
        self.assertEqual(self.lint()[0], 0)

    def test_commands_must_have_a_test(self):
        self.ticket("01-a", body=CHECKED)
        self.commands("Build: `true`\n")
        code, out = self.lint()
        self.assertEqual(code, 1)
        self.assertIn("commands.md has no Test command", out)
        self.commands("Test: `<command>`\n")
        self.assertEqual(self.lint()[0], 1)

    def test_a_test_command_not_on_path_only_warns(self):
        self.ticket("01-a", body=CHECKED)
        self.commands("Test: `no-such-tool-xyz --all`\n")
        code, out = self.lint()
        self.assertEqual(code, 0)
        self.assertIn("warning: commands.md Test starts with `no-such-tool-xyz`", out)

    def test_a_missing_referenced_file_warns_unless_marked_new(self):
        self.ticket("01-a", body=CHECKED + "\n## Reference\n\n- `src/gone.py`\n- `src/later.py` (new)\n")
        code, out = self.lint()
        self.assertEqual(code, 0)
        self.assertIn("names `src/gone.py`", out)
        self.assertNotIn("later.py", out)


def added(path, lines):
    return ("diff --git a/%s b/%s\n--- a/%s\n+++ b/%s\n@@ -1 +1 @@\n" % (path, path, path, path)
            + "".join("+" + line + "\n" for line in lines))


class TrivialAssertTests(unittest.TestCase):
    def found(self, line, path="tests/test_a.py", allow=""):
        return floorguard.diff_findings(added(path, [line]), allow)

    def test_asserts_that_cannot_fail_are_found(self):
        for line in ("    assert True", "self.assertTrue(True)", "self.assertEqual(x, x)", "assert a.b == a.b",
                     "assert 1 == 1", "expect(true).toBe(true)", "expect(v).toBe(v)"):
            self.assertIn("trivial-assert: tests/test_a.py", self.found(line), line)

    def test_real_asserts_are_not(self):
        for line in ("    assert x == 3", "self.assertEqual(x, y)", "self.assertTrue(ok)", "expect(v).toBe(3)",
                     "assert foo(True) == 2", "self.assertEqual(x, x2)"):
            self.assertEqual(self.found(line), "", line)

    def test_only_test_files_count_and_allow_overrides(self):
        self.assertEqual(self.found("assert True", path="src/a.py"), "")
        self.assertEqual(self.found("assert True", allow="trivial-assert"), "")


if __name__ == "__main__":
    unittest.main()
