"""flow-status.py <feature> --clean (feature_flow/clean.py): the brainstorm's spent files go once the plan exists;
the final page and the brainstorm stay, and without --yes it only lists."""

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import clean  # the module under test, from this checkout


class Clean(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        self.state = Path(".feature-flow/state")
        (self.state / "brainstorm-csv-live").mkdir(parents=True)
        for name in ("brainstorm-csv.md", "brainstorm-csv.html", "brainstorm-csv.helpers", "brainstorm-csv-scout-1.txt",
                     "ask-csv-brainstorm.md", "brainstorm-other-scout-1.txt", "brainstorm-csv-live/index.html"):
            (self.state / name).write_text("x\n", encoding="utf-8")

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def run_clean(self, *args):
        out, err = io.StringIO(), io.StringIO()
        return clean.main(["csv"] + list(args), out, err), out.getvalue(), err.getvalue()

    def test_it_waits_for_the_plan_then_lists_then_deletes(self):
        rc, _, err = self.run_clean()
        self.assertEqual(rc, 1)
        self.assertIn("no plan for csv yet", err)
        Path("plans/csv").mkdir(parents=True)
        rc, out, _ = self.run_clean()
        self.assertEqual(rc, 0)
        self.assertIn("would delete .feature-flow/state/brainstorm-csv-scout-1.txt\n", out)
        self.assertTrue((self.state / "brainstorm-csv.html").is_file())
        rc, out, _ = self.run_clean("--yes")
        self.assertEqual(sorted(p.name for p in self.state.iterdir()),
                         ["brainstorm-csv-live", "brainstorm-csv.md", "brainstorm-other-scout-1.txt"])
        self.assertEqual(self.run_clean("--yes")[1], "nothing to clean for csv\n")
        self.assertEqual(self.run_clean("--now")[0], 2)


if __name__ == "__main__":
    unittest.main()
