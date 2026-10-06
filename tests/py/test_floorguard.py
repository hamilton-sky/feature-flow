import os
import sys
import unittest

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import checks, floorguard  # the package under test, from this checkout


def diff(*files):
    """A --unified=0 diff with the given (path, [added lines]) pairs."""
    out = []
    for path, lines in files:
        out += [b"diff --git a/" + path + b" b/" + path, b"--- a/" + path, b"+++ b/" + path, b"@@ -1 +1 @@"]
        out += [b"+" + line for line in lines]
    return b"\n".join(out) + b"\n"


class AllowLineTests(unittest.TestCase):
    def test_categories_are_lower_case_and_space_separated(self):
        src = b"# T\n\nType: task\nFloor: Allow Skip,suppress\n"
        self.assertEqual(floorguard.allow_line(src), b"skip suppress")

    def test_only_the_first_twenty_lines_count(self):
        self.assertEqual(floorguard.allow_line(b"x\n" * 20 + b"Floor: allow skip\n"), b"")
        self.assertEqual(floorguard.allow_line(b"x\n" * 19 + b"Floor: allow skip\n"), b"skip")

    def test_without_allow_the_prefix_stays_like_in_bash(self):
        self.assertEqual(floorguard.allow_line(b"Floor: skip, config\n"), b"floor: skip  config")

    def test_no_line_is_empty(self):
        self.assertEqual(floorguard.allow_line(b""), b"")


class AwkAssignTests(unittest.TestCase):
    def test_escapes_follow_mawk(self):
        self.assertEqual(floorguard._awk_assign(b"a\\tb\\\\c\\qd\\101\\x414\\"), b"a\tb\\c\\qdAA4\\")


class DiffFindingsTests(unittest.TestCase):
    def test_each_category_in_order(self):
        d = diff((b"t.py", [b"@pytest.mark.skip", b"x = 1  # noqa", b"except Exception: pass", b"fail_under = 1"]))
        self.assertEqual(floorguard.diff_findings(d, b""),
                         b"skip: t.py: @pytest.mark.skip\nsuppress: t.py: x = 1  # noqa\n"
                         b"empty-catch: t.py: except Exception: pass\nthreshold: t.py: fail_under = 1\n")

    def test_one_line_can_be_reported_twice(self):
        d = diff((b"a.js", [b"  it.skip(x) // eslint-disable-line"]))
        self.assertEqual(floorguard.diff_findings(d, b""),
                         b"skip: a.js: it.skip(x) // eslint-disable-line\nsuppress: a.js: it.skip(x) // eslint-disable-line\n")

    def test_a_word_before_it_is_not_a_skip(self):
        self.assertEqual(floorguard.diff_findings(diff((b"a.js", [b"my_it.skip(x)", b"split.skip("])), b""), b"")

    def test_allowed_categories_are_quiet(self):
        d = diff((b"t.py", [b"@pytest.mark.skip  # noqa"]))
        self.assertEqual(floorguard.diff_findings(d, b"skip"), b"suppress: t.py: @pytest.mark.skip  # noqa\n")

    def test_text_is_cut_at_100_bytes(self):
        line = b"# noqa " + b"x" * 92 + "é".encode() + b"tail"
        out = floorguard.diff_findings(diff((b"a.py", [line])), b"")
        self.assertEqual(out, b"suppress: a.py: " + line[:100] + b"\n")

    def test_removed_lines_are_ignored(self):
        self.assertEqual(floorguard.diff_findings(b"+++ b/a.py\n-@pytest.mark.skip\n", b""), b"")


class FrozenTests(unittest.TestCase):
    def test_status_and_answer_are_left_out(self):
        text = b"# A\nStatus: open\nbody\n## Answer\nanything\n"
        self.assertEqual(floorguard.frozen(text), b"# A\nbody\n")

    def test_a_missing_last_newline_is_the_same(self):
        self.assertEqual(floorguard.frozen(b"a\nb"), floorguard.frozen(b"a\nb\n"))

    def test_review_findings_end_it_too(self):
        self.assertEqual(floorguard.frozen(b"a\n## Review findings (round 1, gate)\nx\n"), b"a\n")


class RemovedLinesTests(unittest.TestCase):
    def test_placeholders_and_blank_lines_do_not_count(self):
        d = b"--- a/map.md\n+++ b/map.md\n-<One line per resolved ticket.>\n-- <fog>\n-   \n+01 - x\n"
        self.assertEqual(floorguard.count_removed_real_lines(d), 0)

    def test_real_lines_count(self):
        self.assertEqual(floorguard.count_removed_real_lines(b"-## Decisions so far\n-real\n"), 2)


class RunTests(unittest.TestCase):
    def setUp(self):
        self.repo = helpers.Repo()
        self.cwd = os.getcwd()
        os.chdir(str(self.repo.dir))
        self.base = self.repo.head()

    def tearDown(self):
        os.chdir(self.cwd)
        self.repo.close()

    def guard(self, *args, **env):
        out, err = [], []
        code = floorguard.run(list(args), out.append, err.append, env)
        return code, "".join(out), "".join(err)

    def test_usage(self):
        self.assertEqual(self.guard("f", **{}), (2, "", floorguard.USAGE + "\n"))

    def test_missing_ticket(self):
        self.assertEqual(self.guard("f", "99"), (2, "", "no ticket 99 in plans/f/tasks\n"))
        self.assertEqual(self.guard("f", "01", FLOW_DIR="x", FLOW_TICKETS="y"), (2, "", "no ticket 01 in x/f/y\n"))

    def test_clean(self):
        self.repo.resolve("plans/f/tasks/01-a.md")
        self.assertEqual(self.guard("f", "01", self.base), (0, "floor guard: clean\n", ""))

    def test_findings_and_assert_warning(self):
        self.repo.path("tests").mkdir()
        self.repo.path("tests/test_x.py").write_text("def test_x():\n    assert 1\n")
        self.repo.commit("tests")
        base = self.repo.head()
        self.repo.path("tests/test_x.py").write_text("@pytest.mark.skip\ndef test_x():\n    pass\n")
        with open(str(self.repo.path("plans/f/spec.md")), "a") as f:
            f.write("more\n")
        self.repo.commit("weaken")
        code, out, err = self.guard("f", "01", base)
        self.assertEqual(code, 1)
        self.assertEqual(err, "")
        self.assertEqual(out, "warning: 1 assertion line(s) removed, 0 added. check that no test got weaker.\n"
                              "floor guard: the diff weakens the bar instead of meeting it\n"
                              "skip: tests/test_x.py: @pytest.mark.skip\n"
                              "ticket-edit: plans/f/spec.md: only your own ticket, map.md and learnings.md may change\n"
                              "if a finding is intended, the ticket needs a line like: Floor: allow <category>\n")

    def test_a_bad_base_passes_on_git_s_exit_code(self):
        code, out, err = self.guard("f", "01", "no-such-commit")
        self.assertEqual((code, out), (128, ""))
        self.assertIn("no-such-commit", err)

    def test_checks_runs_it_in_process_with_one_output(self):
        self.repo.resolve("plans/f/tasks/01-a.md")
        result = checks.floor_guard("unused", "f", "01", self.base)
        self.assertTrue(result.ok)
        self.assertEqual(result.out, "floor guard: clean\n")
        self.assertEqual(checks.floor_guard("unused", "f", "99", self.base).code, 2)


if __name__ == "__main__":
    unittest.main()
