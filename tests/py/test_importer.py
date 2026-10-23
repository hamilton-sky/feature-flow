import io
import os
import sys
import unittest
from pathlib import Path

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import importer, status  # the package under test, from this checkout

SPECKIT = """# Tasks: Photo albums

## Phase 1: Setup

- [ ] T001 Create the project structure per the plan
- [ ] T002 [P] Configure linting in pyproject.toml

## Phase 2: Foundational

- [ ] T003 Add the album model in src/models/album.py
- [ ] T004 Add the storage layer in src/storage/

## Phase 3: User Story 1 - Create an album (Priority: P1)

- [ ] T005 [P] [US1] Contract test for POST /albums in tests/contract/test_albums.py
- [ ] T006 [US1] Implement POST /albums in src/api/albums.py

## Phase 4: User Story 2 - Share an album (Priority: P2)

- [ ] T007 [US2] Implement sharing in src/api/share.py

## Phase 5: Polish

- [ ] T008 Update the docs
"""

OPENSPEC = """## 1. Implementation
- [ ] 1.1 Create the database schema
- [x] 1.2 Implement the API endpoint
## 2. Testing
- [ ] 2.1 Write the integration tests
"""


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.repo = helpers.Repo(tickets=(), local=False)
        self.cwd = os.getcwd()
        os.chdir(str(self.repo.dir))

    def tearDown(self):
        os.chdir(self.cwd)
        self.repo.close()

    def speckit(self):
        folder = self.repo.dir / "specs" / "001-albums"
        folder.mkdir(parents=True)
        (folder / "tasks.md").write_text(SPECKIT, encoding="utf-8")
        (folder / "spec.md").write_text("# Feature Specification: Albums\n\nUsers group photos.\n", encoding="utf-8")
        (folder / "plan.md").write_text("# Plan\n\nA REST API.\n", encoding="utf-8")
        return folder

    def run_import(self, *args):
        out, err = io.StringIO(), io.StringIO()
        code = importer.main(list(args), out, err, guides_root=helpers.ROOT)
        return code, out.getvalue(), err.getvalue()

    def ticket(self, feature, name):
        return (self.repo.dir / "plans" / feature / "tasks" / name).read_text(encoding="utf-8")

    def test_speckit_phases_become_tickets_and_stories_run_side_by_side(self):
        code, out, err = self.run_import(str(self.speckit()), "albums")
        self.assertEqual(code, 0, err)
        tasks = sorted(p.name for p in (self.repo.dir / "plans" / "albums" / "tasks").iterdir())
        self.assertEqual(tasks, ["01-setup.md", "02-foundational.md", "03-user-story-1-create-an-album.md",
                                 "04-user-story-2-share-an-album.md", "05-polish.md"])
        self.assertIn("Blocked by: —", self.ticket("albums", "01-setup.md"))
        self.assertIn("Blocked by: 01", self.ticket("albums", "02-foundational.md"))
        self.assertIn("Blocked by: 02", self.ticket("albums", "03-user-story-1-create-an-album.md"))
        self.assertIn("Blocked by: 02", self.ticket("albums", "04-user-story-2-share-an-album.md"))
        self.assertIn("Blocked by: 03, 04", self.ticket("albums", "05-polish.md"))
        story = self.ticket("albums", "03-user-story-1-create-an-album.md")
        self.assertIn("Touches: tests/contract/test_albums.py, src/api/albums.py", story)
        self.assertIn("- Implement POST /albums in src/api/albums.py", story)
        self.assertNotIn("T006", story)
        self.assertIn("Touches: src/models/album.py, src/storage/", self.ticket("albums", "02-foundational.md"))
        self.assertNotIn("Touches:", self.ticket("albums", "05-polish.md"))  # a task with no path
        spec = (self.repo.dir / "plans" / "albums" / "spec.md").read_text(encoding="utf-8")
        self.assertIn("Users group photos.", spec)
        self.assertIn("A REST API.", spec)
        self.assertIn("Test:", (self.repo.dir / "plans" / "albums" / "commands.md").read_text(encoding="utf-8"))
        self.assertIn("next: fill in plans/albums/commands.md", out)

    def test_the_imported_graph_passes_the_check(self):
        self.run_import(str(self.speckit()), "albums")
        out, err = io.BytesIO(), io.BytesIO()
        code = status.run(["albums", "--check"], status._Bytes(out), status._Bytes(err))
        self.assertEqual(code, 0, err.getvalue())

    def test_openspec_sections_and_a_done_task(self):
        folder = self.repo.dir / "openspec" / "changes" / "add-auth"
        folder.mkdir(parents=True)
        (folder / "tasks.md").write_text(OPENSPEC, encoding="utf-8")
        (folder / "proposal.md").write_text("# Proposal\n\nWhy: logins.\n", encoding="utf-8")
        code, _, err = self.run_import(str(folder / "tasks.md"), "auth")
        self.assertEqual(code, 0, err)
        first = self.ticket("auth", "01-implementation.md")
        self.assertIn("- Create the database schema", first)
        self.assertIn("- Implement the API endpoint", first)
        self.assertIn("Blocked by: 01", self.ticket("auth", "02-testing.md"))
        self.assertIn("Why: logins.", (self.repo.dir / "plans" / "auth" / "spec.md").read_text(encoding="utf-8"))

    def test_it_never_overwrites_a_plan_and_dry_run_writes_nothing(self):
        folder = self.speckit()
        code, out, _ = self.run_import(str(folder), "albums", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("would write plans/albums/tasks/01-setup.md", out)
        self.assertFalse((self.repo.dir / "plans" / "albums").exists())
        self.run_import(str(folder), "albums")
        code, _, err = self.run_import(str(folder), "albums")
        self.assertEqual(code, 1)
        self.assertIn("already exists", err)

    def test_bad_input(self):
        self.assertEqual(self.run_import("nowhere", "x")[0], 1)
        self.assertEqual(self.run_import("a", "b/c")[0], 2)
        empty = self.repo.dir / "empty.md"
        empty.write_text("# nothing to do\n", encoding="utf-8")
        code, _, err = self.run_import(str(empty), "x")
        self.assertEqual(code, 1)
        self.assertIn("no checkbox tasks", err)


if __name__ == "__main__":
    unittest.main()
