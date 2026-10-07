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


class MoreSkipTests(unittest.TestCase):
    def found(self, path, line):
        return floorguard.diff_findings(diff((path, [line])), b"")

    def test_new_skip_patterns_are_caught(self):
        for path, line in [(b"t.py", b'self.skipTest("x")'), (b"t.py", b"pytest.importorskip('numpy')"),
                           (b"t.py", b"@unittest.expectedFailure"), (b"a_test.go", b't.Skipf("x %d", 1)'),
                           (b"a_test.go", b"t.SkipNow()"), (b"a.rs", b'#[ignore = "slow"]')]:
            with self.subTest(line=line):
                self.assertEqual(self.found(path, line), b"skip: " + path + b": " + line + b"\n")

    def test_skip_look_alikes_are_clean(self):
        for path, line in [(b"t.py", b"self.skipTestCase = 1"), (b"t.py", b"importorskip_later = 1"),
                           (b"t.py", b"expectedFailures = []"), (b"a_test.go", b"t.Skipfoo(x)"),
                           (b"a_test.go", b"t.SkipNowhere()"), (b"a.rs", b"#[ignore_me = 1]")]:
            with self.subTest(line=line):
                self.assertEqual(self.found(path, line), b"")

    def test_focused_patterns_are_caught_on_test_paths(self):
        for path, line in [(b"a.test.js", b"it.only('x', f)"), (b"a.test.js", b"describe.only('x', f)"),
                           (b"a.test.js", b"test.only('x', f)"), (b"a.spec.js", b"fit('x', f)"),
                           (b"a.spec.js", b"  fdescribe('x', f)"), (b"tests/a.js", b"x; fit('x', f)")]:
            with self.subTest(line=line):
                self.assertEqual(self.found(path, line), b"skip: " + path + b": " + line.strip() + b"\n")

    def test_focused_look_alikes_are_clean(self):
        for path, line in [(b"train.py", b"model.fit(x)"), (b"a.spec.js", b"model.fit(x)"),
                           (b"test_a.py", b"def fit(self):"), (b"a.spec.js", b"outfit(x)"),
                           (b"a.spec.js", b"outfdescribe(x)"), (b"a.spec.js", b"x.fdescribe(y)"),
                           (b"a.test.js", b"it.onlyChild(x)"), (b"app/models.py", b'qs.only("a")'),
                           (b"app/models.py", b"fit(x)"), (b"app/models.py", b"fdescribe(x)")]:
            with self.subTest(path=path, line=line):
                self.assertEqual(self.found(path, line), b"")


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


class AssertionWarningTests(unittest.TestCase):
    def diff(self, path, removed, added):
        return (b"--- a/" + path + b"\n+++ b/" + path + b"\n@@ -1 +1 @@\n"
                + b"".join(b"-" + l + b"\n" for l in removed) + b"".join(b"+" + l + b"\n" for l in added))

    def test_removed_asserts_in_a_test_file_count(self):
        d = self.diff(b"tests/test_x.py", [b"    assert 1", b"    assert 2"], [b"    assert 3"])
        self.assertEqual(floorguard.count_assertions(d), (2, 1))

    def test_the_same_text_in_a_readme_does_not_count(self):
        d = self.diff(b"README.md", [b"use assert here", b"expect(x)"], [])
        self.assertEqual(floorguard.count_assertions(d), (0, 0))

    def test_warning_line_for_test_x_py_but_none_for_readme(self):
        for path, expect in (("test_x.py", True), ("README.md", False)):
            with self.subTest(path=path):
                repo = helpers.Repo()
                cwd = os.getcwd()
                os.chdir(str(repo.dir))
                try:
                    repo.path(path).write_text("assert 1\n", encoding="utf-8")
                    repo.commit("add")
                    base = repo.head()
                    repo.path(path).write_text("pass\n", encoding="utf-8")
                    repo.commit("weaken")
                    out = []
                    floorguard.run(["f", "01", base], out.append, lambda t: None, {})
                    self.assertEqual("warning: 1 assertion line(s) removed, 0 added." in "".join(out), expect)
                finally:
                    os.chdir(cwd)
                    repo.close()


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.repo = helpers.Repo()
        self.cwd = os.getcwd()
        os.chdir(str(self.repo.dir))

    def tearDown(self):
        os.chdir(self.cwd)
        self.repo.close()

    def write(self, rel, text):
        path = self.repo.path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def change(self, rel, before, after, allow=""):
        """Commit `before`, then `after`; returns the guard result for the second commit."""
        ticket = self.repo.path("plans/f/tasks/01-a.md")
        text = ticket.read_text(encoding="utf-8")
        text = "".join(l for l in text.splitlines(True) if not l.startswith("Floor:"))
        if allow:
            text = text.replace("Test first: no\n", "Test first: no\nFloor: allow %s\n" % allow)
        ticket.write_text(text, encoding="utf-8")
        self.write(rel, before)
        self.repo.git("add", "-A")
        self.repo.git("commit", "--allow-empty", "-qm", "before")
        base = self.repo.head()
        self.write(rel, after)
        self.repo.commit("after")
        out, err = [], []
        code = floorguard.run(["f", "01", base], out.append, err.append, {})
        return code, "".join(out)

    def assertCaught(self, rel, before, after, allow="config"):
        code, out = self.change(rel, before, after)
        self.assertEqual(code, 1, out)
        self.assertIn("config: %s\n" % rel, out)
        code, out = self.change(rel, after, before, allow=allow)
        self.assertEqual((code, out), (0, "floor guard: clean\n"))

    def assertClean(self, rel, before, after):
        code, out = self.change(rel, before, after)
        self.assertEqual((code, out), (0, "floor guard: clean\n"))

    def test_whole_file_configs_are_caught(self):
        for rel in (".coveragerc", ".flake8", ".pylintrc", ".golangci.yml", ".golangci.yaml", "karma.conf.js",
                    "playwright.config.ts", "cypress.config.js", "codecov.yml", ".nycrc", ".nycrc.json"):
            with self.subTest(rel=rel):
                self.assertCaught(rel, "a\n", "b\n")

    def test_a_similar_name_is_clean(self):
        self.assertClean("notcodecov.yml.txt", "a\n", "b\n")

    def test_pyproject_coverage_threshold_is_caught(self):
        before = "[project]\nversion = '1'\n\n[tool.coverage.report]\nfail_under = 90\n"
        self.assertCaught("pyproject.toml", before, before.replace("90", "10"), allow="config, threshold")

    def test_pyproject_poetry_dependency_is_clean(self):
        before = "[tool.poetry.dependencies]\nrequests = '1'\n\n[tool.coverage.report]\nx = 1\n"
        self.assertClean("pyproject.toml", before, before.replace("'1'", "'2'"))

    def test_pyproject_project_version_is_clean(self):
        self.assertClean("pyproject.toml", "[project]\nversion = '1'\n", "[project]\nversion = '2'\n")

    def test_pyproject_deleted_lines_and_headers_count(self):
        before = "[tool.ruff]\nline-length = 80\n\n[tool.poetry]\nname = 'x'\n"
        self.assertCaught("pyproject.toml", before, before.replace("line-length = 80\n", ""))
        self.assertCaught("pyproject.toml", before, before.replace("[tool.ruff]\nline-length = 80\n\n", ""))

    def test_setup_cfg_sections(self):
        before = "[metadata]\nversion = 1\n\n[flake8]\nmax-line-length = 80\n"
        self.assertCaught("setup.cfg", before, before.replace("80", "200"))
        self.assertClean("setup.cfg", before, before.replace("version = 1", "version = 2"))

    def test_package_json_scripts_are_caught_and_version_is_clean(self):
        before = '{"version": "1", "scripts": {"test": "jest"}, "dependencies": {"a": "1"}}'
        self.assertCaught("package.json", before, before.replace('"jest"', '"true"'))
        self.assertClean("package.json", before, before.replace('"version": "1"', '"version": "2"')
                         .replace('"a": "1"', '"a": "2"'))

    def test_package_json_not_valid_json_is_judged_by_bytes(self):
        self.assertCaught("package.json", "{", "{ ")

    def test_conftest_only_collection_changes_are_caught(self):
        self.assertClean("conftest.py", "import pytest\n", "import pytest\n\n@pytest.fixture\ndef x():\n    return 1\n")
        self.assertCaught("conftest.py", "import pytest\n", 'import pytest\ncollect_ignore = ["x"]\n')

    def test_makefile_depends_on_commands_md(self):
        self.assertClean("Makefile", "test:\n\ttrue\n", "test:\n\tfalse\n")
        self.write("plans/f/commands.md", "# Commands: f\n\nTest: `make test`\n")
        self.repo.commit("commands")
        self.assertCaught("Makefile", "test:\n\ttrue\n", "test:\n\tfalse\n")


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
        self.repo.path("tests/test_x.py").write_text("def test_x():\n    assert 1\n", encoding="utf-8")
        self.repo.commit("tests")
        base = self.repo.head()
        self.repo.path("tests/test_x.py").write_text("@pytest.mark.skip\ndef test_x():\n    pass\n", encoding="utf-8")
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
