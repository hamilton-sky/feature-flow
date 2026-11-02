import io
import os
import sys
import unittest

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import reality, report  # the package under test, from this checkout

T1 = "plans/f/tasks/01-a.md"


def touches(repo, rel, line, level=None):
    path = repo.path(rel)
    text = path.read_text(encoding="utf-8").replace("Test first: no\n", "Test first: no\n%s\n%s" % (
        line, "Level: %s\n" % level if level else ""))
    path.write_text(text, encoding="utf-8")


class RealityFromRows(unittest.TestCase):
    def setUp(self):
        self.repo = helpers.Repo(local=False)
        touches(self.repo, T1, "Touches: app/, tests/test_a.py", level=2)

    def tearDown(self):
        self.repo.close()

    def test_differences_come_from_the_log(self):
        rows = report.parse("\n".join([
            "t,01,BUILD", "t,01,CHANGED [\"app/a.py\", \"docs/x.md\", \"plans/f/tasks/01-a.md\"]",
            "t,01,FOOTPRINT-FAIL", "t,01,BUILD", "t,01,CHANGED [\"app/a.py\"]", "t,01,LEVEL-3", "t,01,DECISION",
            "t,01,FOLLOWUPS 2", "t,-,REPLAN"]))
        items, run = reality.collect(self.repo.path("plans/f"), rows)
        first = items[0]
        self.assertEqual(first["changed"], ["app/a.py"])  # the last build counts
        self.assertEqual(first["unplanned"], [])
        self.assertEqual(first["untouched"], ["tests/test_a.py"])
        said = reality.notes(first)
        for phrase in ("sent back 1 time for leaving Touches", "planned but not changed: tests/test_a.py",
                       "level raised 2 to 3", "built 2 times", "1 question decided", "2 findings left for later"):
            self.assertTrue(any(phrase in s for s in said), (phrase, said))
        self.assertEqual(run["replan"], 1)
        self.assertIsNone(items[1]["changed"])
        out = reality.text(items, run)
        self.assertIn("02 B (open)", out)
        self.assertIn("changed: not built yet", out)
        self.assertIn("re-planned 1 time", out)
        md = reality.markdown(items, run)
        self.assertIn("| 01 A | app/, tests/test_a.py | app/a.py |", md)

    def test_a_change_outside_touches_is_named(self):
        rows = report.parse('t,01,CHANGED ["app/a.py", "web/b.js"]')
        items, _ = reality.collect(self.repo.path("plans/f"), rows)
        self.assertEqual(items[0]["unplanned"], ["web/b.js"])
        self.assertIn("changed outside Touches: web/b.js", reality.notes(items[0]))

    def test_no_touches_line_still_shows_what_changed(self):
        rows = report.parse('t,02,CHANGED ["x.py"]')
        items, _ = reality.collect(self.repo.path("plans/f"), rows)
        self.assertIsNone(items[1]["touches"])
        self.assertEqual(reality.notes(items[1]), [])
        self.assertIn("planned: no Touches line", reality.text(items, {"replan": 0, "repair": 0}))


class RealityOnTheBuildTab(unittest.TestCase):
    def setUp(self):
        self.repo = helpers.Repo(local=False)
        touches(self.repo, T1, "Touches: app/")

    def tearDown(self):
        self.repo.close()

    def test_the_build_tab_adds_plan_vs_reality_once_a_ticket_is_built(self):
        from feature_flow import flow_plan
        _, _, found = flow_plan.build_section(self.repo.path("plans/f"))
        self.assertEqual([s["title"] for s in found], ["Build"])
        log = self.repo.path(".feature-flow/state/flow-f.log")
        log.parent.mkdir(parents=True)
        log.write_text('t,01,CHANGED ["app/a.py", "web/b.js"]\n', encoding="utf-8")
        _, _, found = flow_plan.build_section(self.repo.path("plans/f"))
        self.assertEqual([s["title"] for s in found], ["Build", "Plan vs reality"])
        self.assertIn("changed outside Touches: web/b.js", found[1]["markdown"])
        self.assertTrue(all(s["step"] == "Build" for s in found))


class RealityDrive(unittest.TestCase):
    def setUp(self):
        self.repo = helpers.Repo()
        touches(self.repo, T1, "Touches: work-01-a.txt, plans/f/tasks/01-a.md")
        self.repo.commit("touches")

    def tearDown(self):
        self.repo.close()

    def test_the_footprint_check_logs_what_changed_and_report_shows_it(self):
        self.repo.flow("next")
        self.repo.resolve(T1)
        self.repo.flow("next")
        self.assertIn('CHANGED ["work-01-a.txt"]', self.repo.log())
        cwd = os.getcwd()
        os.chdir(str(self.repo.dir))
        try:
            out, err = io.StringIO(), io.StringIO()
            self.assertEqual(report.main(["f"], out, err), 0, err.getvalue())
        finally:
            os.chdir(cwd)
        text = out.getvalue()
        self.assertIn("plan vs reality", text)
        self.assertIn("changed: work-01-a.txt", text)


if __name__ == "__main__":
    unittest.main()
