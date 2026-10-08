import os
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import prompts  # the package under test, from this checkout

GUIDE = "Run `python3 scripts/flow-status.py <feature> --next` for <feature>."
ROLE = "Planner: `python3 scripts/flow-status.py <feature> --check`."


class PromptFolderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        self.root = Path(self.tmp.name).resolve()

    def tree(self, base):
        for folder, names in (("guides", ("build.md", "plan.md")), ("agents", ("ticket-builder.md", "feature-planner.md"))):
            (base / folder).mkdir(parents=True)
            for name in names:
                (base / folder / name).write_text(GUIDE if folder == "guides" else ROLE, encoding="utf-8")
        (base / "scripts").mkdir()
        return base / "scripts"

    def build(self, scripts):
        return prompts.build("build", scripts, "demo", "plans/demo/tasks/01-a.md", "01", "abc")

    def test_build_points_at_the_scripts_folder_that_is_running(self):
        scripts = self.tree(self.root / "home")
        repo = self.root / "repo"
        repo.mkdir()
        os.chdir(repo)
        text = self.build(scripts)
        self.assertIn("python3 %s/flow-status.py demo --next" % scripts.as_posix(), text)
        self.assertNotIn("python3 scripts/", text)

    def test_plan_rewrites_the_role_too(self):
        scripts = self.tree(self.root / "home")
        os.chdir(self.root)
        text = prompts.plan("plan", scripts, "demo", "draft", "brief")
        self.assertIn("python3 %s/flow-status.py <feature> --check" % scripts.as_posix(), text)
        self.assertNotIn("python3 scripts/", text)

    def test_a_path_with_a_space_is_quoted(self):
        scripts = self.tree(self.root / "my home")
        os.chdir(self.root)
        text = self.build(scripts)
        self.assertIn('python3 "%s"/flow-status.py demo --next' % scripts.as_posix(), text)

    def test_the_repo_install_keeps_its_text(self):
        repo = self.root / "repo"
        repo.mkdir()
        scripts = self.tree(repo)
        os.chdir(repo)
        text = self.build(scripts)
        self.assertIn("python3 scripts/flow-status.py demo --next", text)
        self.assertIn(ROLE, text)
        self.assertNotIn(self.root.as_posix(), text)


if __name__ == "__main__":
    unittest.main()
