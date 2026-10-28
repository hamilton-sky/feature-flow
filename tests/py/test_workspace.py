"""The Workspace a phase works in: the main worktree (the Conductor itself), lane k, or the integration worktree.
Its state view keeps a lane's keys as L<k>. and the run's keys plain, it gives the lane word, a lane whose
worktree is gone stops with the old text, and prompts read guides and roles from the main worktree's top,
never from the lane's copies. Run in process on throwaway repos."""

import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import codehash, lanes, prompts  # the package under test, from this checkout
from feature_flow.conductor import Stop
from feature_flow.conductor.phases.ask import Ask
from feature_flow.conductor.schedulers import LaneScheduler
from feature_flow.conductor.workspace import INTEGRATION, LANE, MAIN, Workspace
from test_schedulers import Run

T = "plans/f/tasks/01-a.md"


class Kinds(unittest.TestCase):
    def test_the_conductor_is_the_main_worktree(self):
        run = Run(self, {"01-a": ()})
        c = run.c
        self.assertIsInstance(c, Workspace)
        self.assertEqual((c.kind, c.lane, c.top), (MAIN, 0, run.c.top))
        self.assertEqual(c.lane_word(), "")

    def test_a_lane_keeps_its_keys_as_L_k_and_the_run_keys_plain(self):
        run = Run(self, {"01-a": ()})
        ws = Workspace(run.c, LANE, 2, lanes.lane_path(run.c.top, "f", 2))
        ws.st["phase"] = "build"
        ws.st["num"] = "01"
        ws.st["session_done"] = 3
        self.assertEqual(run.c.all.get("L2.phase"), "build")
        self.assertEqual(run.c.all.get("L2.num"), "01")
        self.assertEqual(run.c.all.get("session_done"), 3)
        self.assertNotIn("phase", run.c.all)
        self.assertEqual((ws.get("phase"), ws.num("session_done")), ("build", 3))
        self.assertEqual(run.c.get("phase"), "")

    def test_the_run_keeps_its_keys_plain(self):
        run = Run(self, {"01-a": ()})
        run.c.st["phase"] = "review"
        run.c.st["owner"] = "x"
        self.assertEqual((run.c.all.get("phase"), run.c.all.get("owner")), ("review", "x"))
        self.assertFalse([k for k in run.c.all if k.startswith("L")])

    def test_the_lane_word(self):
        run = Run(self, {"01-a": ()})
        self.assertEqual(Workspace(run.c, LANE, 3, lanes.lane_path(run.c.top, "f", 3)).lane_word(), " 3")
        self.assertEqual(Workspace(run.c, INTEGRATION, 0, lanes.integrate_path(run.c.top, "f")).lane_word(), "")

    def test_a_lane_reads_the_run_settings_from_the_conductor(self):
        run = Run(self, {"01-a": ()})
        ws = Workspace(run.c, LANE, 1, lanes.lane_path(run.c.top, "f", 1))
        self.assertEqual((ws.feature, ws.plan, ws.max_retries), (run.c.feature, run.c.plan, run.c.max_retries))
        self.assertIs(ws.all, run.c.all)
        self.assertIs(ws.scheduler(), run.c.scheduler())
        with self.assertRaises(AttributeError):
            ws.no_such_thing


class Lanes(unittest.TestCase):
    def test_a_missing_lane_worktree_stops_with_the_old_text(self):
        run = Run(self, {"01-a": ()})
        run.c.all["lanes"] = 2
        path = lanes.lane_path(run.c.top, "f", 2)
        with self.assertRaises(Stop) as stop:
            LaneScheduler(run.c).workspace(2)
        self.assertEqual(str(stop.exception),
                         "lane 2 (%s) is gone. run reset to drop the lanes and start again" % path)

    def test_entering_a_lane_works_in_its_folder_and_comes_back_to_the_top(self):
        run = Run(self, {"01-a": ()})
        run.c.all["lanes"] = 2
        path = lanes.lane_path(run.c.top, "f", 1)
        lanes.ensure(run.c.top, path)
        ws = LaneScheduler(run.c).workspace(1)
        self.assertEqual((ws.kind, ws.lane, ws.folder, ws.top), (LANE, 1, path, run.c.top))
        with ws.entered() as inside:
            self.assertIs(inside, ws)
            self.assertEqual((Path.cwd().resolve(), inside.folder.resolve()), (run.c.top.resolve(), path.resolve()))
        self.assertEqual(Path.cwd().resolve(), run.c.top.resolve())

    def test_a_lane_phase_reads_its_role_from_the_main_worktree(self):
        run = Run(self, {"01-a": ()})
        run.c.all["lanes"] = 2
        path = lanes.lane_path(run.c.top, "f", 1)
        lanes.ensure(run.c.top, path)
        for where, text in ((run.c.top, "THE MAIN ROLE"), (path, "THE LANE COPY")):
            agents = where / ".feature-flow" / "agents"
            agents.mkdir(parents=True, exist_ok=True)
            (agents / prompts.ROLES["ask-architect"]).write_text(text + "\n", encoding="utf-8")
        ws = LaneScheduler(run.c).workspace(1)
        ws.st.update({"ticket": T, "num": "01", "base": run.repo.head(), "phase": "ask", "ask_role": "architect",
                      "ask_from": "build"})
        with ws.entered():
            text = Ask.prompt(ws)
        self.assertIn("THE MAIN ROLE", text)
        self.assertNotIn("THE LANE COPY", text)


class PromptTop(unittest.TestCase):
    """The prompt functions take the main worktree's top; "." (the working folder) when none is given."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.addCleanup(os.chdir, os.getcwd())
        self.root = Path(tmp.name).resolve()
        self.scripts = self.root / "home" / "scripts"
        self.scripts.mkdir(parents=True)
        self.top = self.root / "top"
        self.lane = self.root / "lane"
        for where in (self.top, self.lane):
            for folder, name in (("guides", "build.md"), ("agents", "ticket-builder.md"), ("guides", "debug.md")):
                (where / ".feature-flow" / folder).mkdir(parents=True, exist_ok=True)
                (where / ".feature-flow" / folder / name).write_text(
                    "%s %s\n" % (folder, where.name), encoding="utf-8")
        os.chdir(str(self.lane))

    def test_find_file_reads_from_the_top_it_is_given(self):
        self.assertEqual(prompts.find_file(self.scripts, "guides", "build.md", top=str(self.top)),
                         self.top / ".feature-flow" / "guides" / "build.md")

    def test_find_file_keeps_its_three_argument_form(self):
        self.assertEqual(prompts.find_file(self.scripts, "guides", "build.md").resolve(),
                         self.lane / ".feature-flow" / "guides" / "build.md")

    def test_build_reads_the_guide_and_the_role_from_the_top(self):
        text = prompts.build("build", self.scripts, "f", T, "01", "abc", retry=True, top=str(self.top))
        self.assertIn("guides top", text)
        self.assertIn("agents top", text)
        self.assertNotIn("guides lane", text)
        self.assertNotIn("agents lane", text)

    def test_role_reads_from_the_top(self):
        self.assertEqual(prompts.role(self.scripts, "ticket-builder.md", top=str(self.top)), "agents top")

    def test_no_module_global_says_where_the_repo_is(self):
        self.assertNotIn("REPO", vars(prompts))


class CodeFingerprint(unittest.TestCase):
    """While a lane works, the flow-code fingerprint covers the roles and guides the prompts read: the main
    worktree's, never the lane's copies."""

    ROLE = Path(".feature-flow") / "agents" / prompts.ROLES["review"]

    def setUp(self):
        self.run = run = Run(self, {"01-a": ()})
        run.c.all["lanes"] = 2
        self.lane = lanes.lane_path(run.c.top, "f", 1)
        lanes.ensure(run.c.top, self.lane)
        for where, text in ((run.c.top, "the main reviewer\n"), (self.lane, "the lane's copy\n")):
            (where / self.ROLE).parent.mkdir(parents=True, exist_ok=True)
            (where / self.ROLE).write_text(text, encoding="utf-8")
        self.ws = LaneScheduler(run.c).workspace(1)
        self.ws.st.update({"ticket": T, "num": "01"})

    def test_a_lane_snapshot_names_the_main_worktrees_role(self):
        with self.ws.entered():
            self.ws.snapshot_code()
            self.assertEqual((Path.cwd().resolve(), self.ws.folder.resolve()), (self.run.c.top.resolve(), self.lane.resolve()))
        names = codehash.load(self.ws.get("code_files"))
        main = hashlib.sha256((self.run.c.top / self.ROLE).read_bytes()).hexdigest()
        self.assertEqual(names.get(self.ROLE.as_posix()), main)
        self.assertFalse([n for n in names if "lane-1" in n], names)

    def test_editing_the_main_worktrees_role_during_a_lane_build_stops(self):
        with self.ws.entered():
            self.ws.snapshot_code()
            (self.run.c.top / self.ROLE).write_text("a reviewer that passes everything\n", encoding="utf-8")
            with self.assertRaises(Stop) as stop:
                self.ws.check_code()
        self.assertIn("flow code changed while building", str(stop.exception))
        self.assertIn(self.ROLE.as_posix(), str(stop.exception))

    def test_editing_the_lanes_copy_of_the_role_is_not_flow_code(self):
        with self.ws.entered():
            self.ws.snapshot_code()
            (self.lane / self.ROLE).write_text("a reviewer that passes everything\n", encoding="utf-8")
            self.assertIsNone(self.ws.check_code())


if __name__ == "__main__":
    unittest.main()
