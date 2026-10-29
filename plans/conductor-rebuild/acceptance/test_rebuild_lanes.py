"""Lane runs (spec.md § Happy path 2 and the lane rows of § Edge cases), driven through the CLI with FLOW_LANES=2 and
compared with the old code."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

from support import World, current_code, twins

LANES = {"FLOW_LANES": "2", "FLOW_TICKETS_PER_SESSION": "99"}
SIDE_BY_SIDE = (("01", "—", ("Level: 2", "Touches: t01/")), ("02", "—", ("Level: 2", "Touches: t02/")),
                ("03", "01", ("Level: 2", "Touches: t03/")))
SPY = """import os, runpy, sys
log = os.environ["CHDIR_SPY_LOG"]
real = os.chdir
def spy(path):
    with open(log, "a") as handle:
        handle.write("%s\\n" % path)
    real(path)
os.chdir = spy
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""


class Lanes(unittest.TestCase):
    # Happy path 2: With `FLOW_LANES=2`, the facade picks the LaneScheduler, which leases, merges, refreshes and
    # rebuilds as `dispatch`, `lease`, `integrate`, `refresh` and `rebuild` do today.
    # Edge case: `pick_ticket` and `dispatch` at the end -> ... `dispatch` [checks tests due] only when no lane is busy;
    # lanes are removed only at the end of a lane run.
    def test_a_lane_run_leases_merges_and_finishes_as_today(self):
        def scenario(w):
            w.start()
            w.last = w.drive()
            w.lanes_left = (w.dir / ".feature-flow" / "lanes" / "f").exists()

        new = twins(self, scenario, tickets=SIDE_BY_SIDE, acceptance=True, env=LANES)
        self.assertTrue(new.last.startswith("DONE f is complete: 3 ticket(s)"), new.last)
        self.assertTrue(any("\nWAIT 1,2" in line for line in new.lines))
        self.assertFalse(new.lanes_left)

    # Edge case: A level 3 lane ticket whose base is behind the feature head -> Refreshed and reviewed again, as
    # `refresh` does now.
    def test_a_level_3_lane_ticket_behind_the_head_is_refreshed_and_reviewed_again(self):
        def scenario(w):
            w.start()
            w.last = w.drive()

        new = twins(self, scenario, env=LANES,
                    tickets=(("01", "—", ("Level: 2", "Touches: t01/")), ("02", "—", ("Level: 3", "Touches: t02/"))))
        reviews = [line for line in new.lines if "\nREVIEW plans/f/tasks/02-t.md 02 " in line]
        self.assertGreaterEqual(len(reviews), 2, new.lines)
        self.assertTrue(new.last.startswith("DONE f is complete: 2 ticket(s)"), new.last)

    # Edge case: The session handoff in `dispatch` with busy lanes -> `WAIT` instead of `HANDOFF`; re-plan check only
    # with no busy lane; budget offer only with no busy lane.
    def test_the_session_handoff_with_busy_lanes_is_a_wait(self):
        def scenario(w):
            w.start()
            w.last = w.drive(limit=80)

        new = twins(self, scenario, tickets=SIDE_BY_SIDE, env={"FLOW_LANES": "2", "FLOW_TICKETS_PER_SESSION": "1"})
        self.assertTrue(any("\nHANDOFF " in line for line in new.lines))
        self.assertTrue(new.last.startswith("DONE f is complete"), new.last)

    # Edge case: Guides and roles while a lane works -> Read from the main worktree, never the lane's copies.
    def test_guides_and_roles_come_from_the_main_worktree(self):
        def mark(where):
            for folder in ("guides", "agents"):
                for path in (Path(where) / folder).rglob("*.md"):
                    with open(str(path), "a", encoding="utf-8") as handle:
                        handle.write("\nLANE-COPY-MARKER\n")

        def scenario(w):
            w.start()
            w.flow("next")  # BUILD in lane 1
            mark(w.lane_dir(1))
            w.git("add", "-A", cwd=w.lane_dir(1))
            w.git("commit", "-qm", "edit the lane's guides", cwd=w.lane_dir(1))
            w.flow("prompt", "1")
            w.resolve("plans/f/tasks/01-t.md", where=w.lane_dir(1))
            w.flow("next", "1")
            w.flow("prompt", "1")

        new = twins(self, scenario, env=LANES,
                    tickets=(("01", "—", ("Level: 2", "Touches: t01/ guides/ agents/")),))
        self.assertFalse(any("LANE-COPY-MARKER" in line for line in new.lines))

    # Edge case: A lane worktree that is gone -> The same `lane N (...) is gone` STOP.
    def test_a_lane_worktree_that_is_gone_stops_as_today(self):
        def scenario(w):
            w.start()
            w.flow("next")
            w.git("worktree", "remove", "--force", str(w.lane_dir(1)))
            w.got = w.flow("next", "1")
            w.path = str(w.lane_dir(1))

        new = twins(self, scenario, env=LANES, tickets=SIDE_BY_SIDE[:1])
        self.assertEqual(new.got[0], 1)
        self.assertTrue(new.got[1].startswith("STOP lane 1 ("), new.got)
        self.assertIn(") is gone. run reset to drop the lanes and start again", new.got[1])

    # Happy path 2: ... working in each lane through a Workspace instead of `os.chdir`.
    # Edge case: Code that runs in a lane after the switch to `cwd=` -> Every git call, check, gate, floor guard, graph
    # read and relative ticket path resolves in the lane folder; the process working folder never changes.
    def test_a_lane_run_never_changes_the_process_working_folder(self):
        side = tempfile.TemporaryDirectory()
        self.addCleanup(side.cleanup)
        spy = Path(side.name) / "spy.py"
        spy.write_text(SPY, encoding="utf-8")
        log = Path(side.name) / "chdir.log"
        w = World(self, current_code(), tickets=SIDE_BY_SIDE, acceptance=True, env=dict(LANES, CHDIR_SPY_LOG=str(log)))
        original = w.run
        w.run = lambda *args, **kw: original(*args, prefix=(str(spy),), **kw)
        w.start()
        last = w.drive()
        self.assertTrue(last.startswith("DONE f is complete: 3 ticket(s)"), last)
        calls = log.read_text(encoding="utf-8") if log.exists() else ""
        self.assertEqual(calls, "", "os.chdir was called during the lane run")


if __name__ == "__main__":
    unittest.main()
