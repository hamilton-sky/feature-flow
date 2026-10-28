"""The store: RunState (the whole run state) and TicketState (one ticket's view of it) over the same dict
and the same key=value file, with lanes.Scoped and lanes.RUN_KEYS now the store's."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import lanes  # the package under test, from this checkout
from feature_flow.conductor import store
from feature_flow.conductor.errors import Stop
from feature_flow.conductor.store import RunState, TicketState

# a state file as the old code wrote it: run keys, a ticket's keys, lane keys, an empty value, tabs and "="
OLD = (b"owner=3f2a\nlimit=3\nruns=2\nnum=05\nphase=build\nbase=f9d716ac\nnotes=a\tb\nempty=\n"
       b"L1.phase=review\nL1.round=2\nL2.phase=merge\nformula=a=b\ndone=1\n")


class Folder(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(self.dir))
        self.path = self.dir / "flow-f.state"


class RunStateFile(Folder):
    def test_a_state_file_in_the_old_format_is_read_and_written_back_byte_for_byte(self):
        self.path.write_bytes(OLD)
        run = RunState.load(self.path)
        self.assertEqual(run["formula"], "a=b")
        self.assertEqual(run["L1.round"], "2")
        self.assertEqual(run.get("empty"), "")
        run.save()
        self.assertEqual(self.path.read_bytes(), OLD)

    def test_no_file_is_an_empty_state_and_save_writes_the_same_format(self):
        run = RunState.load(self.path)
        self.assertEqual(dict(run), {})
        self.assertEqual(run.num("done"), 0)
        run["done"] = 1
        run["note"] = "two\nlines"
        run.save()
        self.assertEqual(self.path.read_bytes(), b"done=1\nnote=two lines\n")

    def test_the_run_state_is_the_dict_state_load_returns(self):
        self.path.write_bytes(OLD)
        run = RunState.load(self.path)
        self.assertIsInstance(run, dict)
        self.assertEqual(list(run), ["owner", "limit", "runs", "num", "phase", "base", "notes", "empty",
                                     "L1.phase", "L1.round", "L2.phase", "formula", "done"])
        self.assertEqual(run.num("limit"), 3)
        self.assertEqual(run.get("missing", "x"), "x")

    def test_a_damaged_number_stops_with_the_same_text(self):
        self.path.write_bytes(b"done=x\nL1.round=two\n")
        run = RunState.load(self.path)
        with self.assertRaises(Stop) as caught:
            run.num("done")
        self.assertEqual(str(caught.exception), "the state file %s is damaged: done is not a number" % self.path)
        with self.assertRaises(Stop) as caught:
            TicketState(run, 1).num("round")
        self.assertEqual(str(caught.exception), "the state file %s is damaged: round is not a number" % self.path)

    def test_a_state_file_that_is_not_utf8_stops_with_the_same_text(self):
        self.path.write_bytes(b"owner=\xff\n")
        with self.assertRaises(Stop) as caught:
            RunState.load(self.path)
        self.assertEqual(str(caught.exception), "the state file %s is damaged: it is not UTF-8 text" % self.path)


class TicketView(Folder):
    def test_lane_keys_go_to_the_lane_prefix_and_run_keys_do_not(self):
        run = RunState(self.path, {"owner": "o", "L1.phase": "build", "L2.phase": "review"})
        one = TicketState(run, 1)
        self.assertEqual(one.get("phase"), "build")
        self.assertEqual(one["owner"], "o")
        one["round"] = 2
        one["done"] = 5
        one.update({"base": "abc"})
        one.setdefault("runs", 0)
        self.assertEqual(run["L1.round"], 2)
        self.assertEqual(run["done"], 5)
        self.assertEqual(run["L1.base"], "abc")
        self.assertIn("runs", run)
        self.assertNotIn("round", run)
        self.assertIn("round", one)
        self.assertEqual(one.num("round"), 2)
        self.assertEqual(one.num("done"), 5)
        for key in store.RUN_KEYS:
            self.assertEqual(one.key(key), key)
        self.assertEqual(one.key("phase"), "L1.phase")

    def test_clear_drops_only_the_lanes_keys(self):
        run = RunState(self.path, {"owner": "o", "L1.phase": "build", "L1.round": "2", "L12.phase": "x",
                                   "L2.phase": "review", "done": "5"})
        TicketState(run, 1).clear()
        self.assertEqual(dict(run), {"owner": "o", "L12.phase": "x", "L2.phase": "review", "done": "5"})

    def test_outside_lanes_every_key_passes_through(self):
        run = RunState(self.path, {"owner": "o", "phase": "build"})
        ticket = TicketState(run)
        self.assertEqual(ticket.get("phase"), "build")
        ticket["round"] = 1
        self.assertEqual(run["round"], 1)
        self.assertEqual(ticket.num("round"), 1)
        ticket.clear()
        self.assertEqual(dict(run), {})

    def test_the_views_write_to_the_same_file(self):
        self.path.write_bytes(OLD)
        run = RunState.load(self.path)
        TicketState(run, 2)["phase"] = "build"
        TicketState(run)["phase"] = "review"
        run.save()
        self.assertEqual(self.path.read_bytes(),
                         OLD.replace(b"L2.phase=merge", b"L2.phase=build").replace(b"\nphase=build", b"\nphase=review"))


class LanesReexport(unittest.TestCase):
    def test_lanes_scoped_and_run_keys_are_the_stores(self):
        self.assertIs(lanes.Scoped, store.Scoped)
        self.assertIs(lanes.RUN_KEYS, store.RUN_KEYS)
        self.assertTrue(issubclass(TicketState, store.Scoped))


if __name__ == "__main__":
    unittest.main()
