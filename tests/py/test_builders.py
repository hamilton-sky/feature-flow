"""Builder notes (ticket 13 of the guided flow): a ticket's `Builder:` line adds guides/builders/<name>.md to its
build prompt, the planner's check refuses an unknown name, and the plan's page suggests one from the paths and
writes the user's switch into the draft ticket."""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import builders, flow_plan, prompts, status  # the modules under test, from this checkout
from test_lanes_width import CSV, write_plan

SCRIPTS = helpers.ROOT / "scripts"
TICKET = "# A\n\nType: task\nStatus: open\n%sBlocked by: —\n\n## Done when\n\n- x\n"


class Out:
    def __init__(self):
        self.text = ""

    def write(self, text):
        self.text += text


class Suggest(unittest.TestCase):
    def test_one_kind_of_path_suggests_that_builder(self):
        self.assertEqual(builders.suggest(["app/web/", "src/components/Button.tsx", "tests/test_button.py"]), "frontend")
        self.assertEqual(builders.suggest(["docs/export.md", "README.md"]), "docs")
        self.assertEqual(builders.suggest(["src/model/", "tests/"]), "backend")

    def test_mixed_missing_or_only_tests_suggest_none(self):
        self.assertIsNone(builders.suggest(["src/model/", "app/web/"]))
        self.assertIsNone(builders.suggest([]))
        self.assertIsNone(builders.suggest(None))
        self.assertIsNone(builders.suggest(["tests/test_a.py"]))

    def test_every_name_has_its_notes(self):
        shipped = {p.stem for p in (helpers.ROOT / "guides" / "builders").iterdir() if p.is_file()}
        self.assertEqual(shipped, set(builders.NAMES))


class InTheRepo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        self.dir = Path(self.tmp.name).resolve()
        os.chdir(str(self.dir))
        Path("plans/f/tasks").mkdir(parents=True)

    def ticket(self, line):
        Path("plans/f/tasks/01-a.md").write_text(TICKET % line, encoding="utf-8")

    def prompt(self, phase="build", workdir=None):
        return prompts.build(phase, SCRIPTS, "f", "plans/f/tasks/01-a.md", "01", "abc", workdir=workdir)

    def test_the_build_prompt_carries_the_named_notes_before_the_task(self):
        self.ticket("Builder: `frontend`\n")
        text = self.prompt()
        self.assertIn("The ticket names the `frontend` builder. Its notes follow.", text)
        self.assertIn("# Frontend builder notes", text)
        self.assertLess(text.index("# Frontend builder notes"), text.index("Your task: build ticket 01"))

    def test_no_line_and_the_review_add_nothing(self):
        self.ticket("")
        self.assertNotIn("builder. Its notes follow", self.prompt())
        self.ticket("Builder: backend\n")
        self.assertNotIn("# Backend builder notes", self.prompt("review"))

    def test_an_unknown_name_builds_with_the_guide_alone(self):
        self.ticket("Builder: robots\n")
        self.assertIn("names the `robots` builder, which has no notes in guides/builders/", self.prompt())

    def test_a_lane_reads_the_ticket_in_its_own_folder(self):
        lane = self.dir / "lane"
        (lane / "plans/f/tasks").mkdir(parents=True)
        (lane / "plans/f/tasks/01-a.md").write_text(TICKET % "Builder: docs\n", encoding="utf-8")
        self.ticket("")
        self.assertIn("# Docs builder notes", self.prompt(workdir=(str(lane), "lane-01")))

    def test_the_plan_check_refuses_an_unknown_builder(self):
        Path("plans/f/commands.md").write_text("Test: `true`\n", encoding="utf-8")
        for line, ok in (("Builder: robots\n", False), ("Builder: docs\n", True)):
            self.ticket(line)
            out, err = Out(), Out()
            code = status.run(["f", "--check"], out, err)
            if ok:
                self.assertEqual(code, 0, out.text + err.text)
            else:
                self.assertNotEqual(code, 0)
                self.assertIn("01: Builder must be frontend, backend, docs", out.text + err.text)


class OnThePage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name).resolve()
        write_plan(root, CSV)
        self.draft = root / "plans" / "csv"

    def flow(self):
        return flow_plan.sections(self.draft, True)[1][1]

    def test_each_ticket_gets_a_builder_choice_with_its_paths_suggestion(self):
        choices = {c["key"]: c for c in self.flow()["choices"]}
        self.assertEqual(choices["builder-04"]["note"], "Its paths suggest frontend.")
        self.assertEqual(choices["builder-05"]["note"], "Its paths suggest docs.")
        self.assertEqual(choices["builder-01"]["value"], "none")
        self.assertEqual([o["value"] for o in choices["builder-01"]["options"]], ["none", "frontend", "backend", "docs"])

    def test_a_pick_writes_and_none_removes_the_line(self):
        said = flow_plan.apply_picks(self.draft, {"builder-04": "frontend"})
        self.assertEqual(said, ["Builder: frontend on 04"])
        path = next((self.draft / "tasks").glob("04-*.md"))
        self.assertIn("Builder: frontend", path.read_text(encoding="utf-8"))
        self.assertEqual({c["key"]: c for c in self.flow()["choices"]}["builder-04"]["value"], "frontend")
        flow_plan.apply_picks(self.draft, {"builder-04": "none"})
        self.assertNotIn("Builder:", path.read_text(encoding="utf-8"))

    def test_a_bad_pick_writes_nothing(self):
        before = {p: p.read_text(encoding="utf-8") for p in (self.draft / "tasks").glob("*.md")}
        for picks, says in (({"builder-99": "docs"}, "no ticket 99"), ({"builder-01": "robots"}, "must be none or"),
                            ({"profile": "careful", "builder-01": "robots"}, "must be none or")):
            with self.assertRaises(ValueError) as caught:
                flow_plan.apply_picks(self.draft, picks)
            self.assertIn(says, str(caught.exception))
        self.assertEqual(before, {p: p.read_text(encoding="utf-8") for p in (self.draft / "tasks").glob("*.md")})
        self.assertNotIn("careful", (self.draft / "commands.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
