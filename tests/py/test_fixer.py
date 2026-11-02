import io
import os
import sys
import unittest

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import fixer, status  # the package under test, from this checkout

DIAGNOSIS = """# Fix: CSV export drops the last row

Repro: `python -c "import sys; sys.exit(0)"`
Touches: app/export/csv.py, tests/test_csv.py
Cause: write_rows stops one short: range(len(rows) - 1) in app/export/csv.py.
Fix: loop over every row, and add a regression test with a three-row report.

## Evidence

$ python -m pytest tests/test_csv.py
1 failed: expected 3 lines, got 2
"""


class FixPlanTests(unittest.TestCase):
    def setUp(self):
        self.repo = helpers.Repo(tickets=(), local=False)
        self.cwd = os.getcwd()
        os.chdir(str(self.repo.dir))
        self.diag = self.repo.dir / "diag.md"
        self.diag.write_text(DIAGNOSIS, encoding="utf-8")

    def tearDown(self):
        os.chdir(self.cwd)
        self.repo.close()

    def run_fix(self, *args):
        out, err = io.StringIO(), io.StringIO()
        code = fixer.main(list(args), out, err, guides_root=helpers.ROOT)
        return code, out.getvalue(), err.getvalue()

    def plan(self, feature, rel):
        return (self.repo.dir / "plans" / feature / rel).read_text(encoding="utf-8")

    def test_fix_writes_one_fix_ticket_from_the_diagnosis(self):
        code, out, err = self.run_fix(str(self.diag), "fix-last-row")
        self.assertEqual(code, 0, err)
        tasks = sorted(p.name for p in (self.repo.dir / "plans" / "fix-last-row" / "tasks").iterdir())
        self.assertEqual(tasks, ["01-fix-csv-export-drops-the-last-row.md"])
        t = self.plan("fix-last-row", "tasks/" + tasks[0])
        for line in ("Type: fix", "Status: open", "Blocked by: —", "Test first: yes", "Level: 2",
                     "Touches: app/export/csv.py, tests/test_csv.py", "```check",
                     '$ python -c "import sys; sys.exit(0)"', "exit 0", "## Answer"):
            self.assertIn(line, t)
        self.assertIn("range(len(rows) - 1)", t)
        spec = self.plan("fix-last-row", "spec.md")
        self.assertIn("1 failed: expected 3 lines, got 2", spec)
        self.assertIn("Profile: `normal`", self.plan("fix-last-row", "commands.md"))
        self.assertIn("no other plan has commands", out)

    def test_fix_carries_the_newest_plans_commands_but_not_its_choices(self):
        other = self.repo.dir / "plans" / "older" / "commands.md"
        other.parent.mkdir(parents=True)
        other.write_text("# Commands: older\n\nBuild: `make`\nTest: `make test`\nLint: `<command>`\n"
                         "Acceptance: `make acc`\nProfile: `fast`\nGate: `end`\nSmoke: `true`\n", encoding="utf-8")
        code, out, err = self.run_fix(str(self.diag), "fix-last-row")
        self.assertEqual(code, 0, err)
        cmds = self.plan("fix-last-row", "commands.md")
        for line in ("Build: `make`", "Test: `make test`", "Smoke: `true`", "Profile: `normal`"):
            self.assertIn(line, cmds)
        for word in ("Acceptance:", "fast", "Gate:", "Lint:"):
            self.assertNotIn(word, cmds)
        self.assertIn("commands from plans/older/commands.md", out)

    def test_fix_level_and_expect(self):
        self.diag.write_text(DIAGNOSIS.replace("Touches:", "Expect: prints 3 rows\nLevel: 3\nTouches:"), encoding="utf-8")
        code, _, err = self.run_fix(str(self.diag), "bug")
        self.assertEqual(code, 0, err)
        t = self.plan("bug", "tasks/01-fix-csv-export-drops-the-last-row.md")
        self.assertIn("Level: 3", t)
        self.assertIn("prints 3 rows", t)
        self.assertNotIn("exit 0", t)

    def test_fix_refuses_a_diagnosis_without_a_cause_or_a_command(self):
        self.diag.write_text(DIAGNOSIS.replace("Cause:", "Why:"), encoding="utf-8")
        code, _, err = self.run_fix(str(self.diag), "bug")
        self.assertEqual(code, 1)
        self.assertIn("Cause:", err)
        self.diag.write_text(DIAGNOSIS.replace('`python -c "import sys; sys.exit(0)"`', "run the tests"), encoding="utf-8")
        code, _, err = self.run_fix(str(self.diag), "bug")
        self.assertEqual(code, 1)
        self.assertIn("backticks", err)
        self.assertFalse((self.repo.dir / "plans" / "bug").exists())

    def test_fix_never_overwrites_and_dry_run_writes_nothing(self):
        code, out, _ = self.run_fix(str(self.diag), "bug", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("would write plans/bug/tasks/01-fix-csv-export-drops-the-last-row.md", out)
        self.assertFalse((self.repo.dir / "plans" / "bug").exists())
        self.run_fix(str(self.diag), "bug")
        code, _, err = self.run_fix(str(self.diag), "bug")
        self.assertEqual(code, 1)
        self.assertIn("already exists", err)

    def test_the_fix_plan_passes_the_check_through_flow_status(self):
        sys.stdout.flush()
        code = status.main(["fix-last-row", "--fix", str(self.diag)])
        self.assertEqual(code, 0)
        out, err = io.BytesIO(), io.BytesIO()
        code = status.run(["fix-last-row", "--check"], status._Bytes(out), status._Bytes(err))
        self.assertEqual(code, 0, err.getvalue())


if __name__ == "__main__":
    unittest.main()
