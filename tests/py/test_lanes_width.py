"""The plan's width (lanes.plan_width, flow-status.py --width): how many tickets can build at once, worked out from
their Touches:, Level: and Blocked by: lines the way the lanes lease them, and why the others wait."""

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import lanes, status  # the modules under test, from this checkout

TICKET = "# %(n)s %(title)s\n\nStatus: %(status)s\nLevel: %(level)s\n%(touches)s%(blocked)s\n## Done when\n\n- it works\n"


def write_plan(root, tickets, shared=""):
    folder = Path(root) / "plans" / "csv" / "tasks"
    folder.mkdir(parents=True)
    (Path(root) / "plans" / "csv" / "commands.md").write_text("# Commands\n\nTest: `true`\n%s" % (
        "Shared: %s\n" % shared if shared else ""), encoding="utf-8")
    for n, (title, level, touches, blocked, st) in tickets.items():
        (folder / ("%02d-%s.md" % (n, title))).write_text(TICKET % {
            "n": "%02d" % n, "title": title, "status": st, "level": level,
            "touches": "Touches: %s\n" % touches if touches else "",
            "blocked": "Blocked by: %s\n" % blocked if blocked else ""}, encoding="utf-8")


CSV = {1: ("model", 2, "src/model/", "", "open"), 2: ("csv-writer", 1, "src/csv/", "", "open"),
       3: ("export-api", 3, "app/api/", "", "open"), 4: ("export-button", 3, "app/web/", "", "open"),
       5: ("docs", 1, "docs/export.md", "", "open"), 6: ("cli", 2, "src/cli/", "", "open")}


class Width(unittest.TestCase):
    def test_level_3_tickets_in_one_folder_run_one_after_the_other(self):
        items = [(n, [t], lvl, [], False) for n, (_, lvl, t, _, _) in CSV.items()]
        wide, waits = lanes.plan_width(items)
        self.assertEqual(wide, 4)  # 01, 02, 03 and 05 first: 04 waits for 03, 06 for a free lane
        self.assertIn((4, 3, "level 3 shares the folder app/"), waits)

    def test_blockers_overlaps_shared_and_no_touches_narrow_it(self):
        items = [(1, ["src/a.py"], 1, [], False), (2, ["src/a.py"], 1, [], False), (3, ["src/b.py"], 1, [1], False),
                 (4, None, 1, [], False), (5, ["docs/"], 1, [], True)]
        wide, waits = lanes.plan_width(items)
        self.assertEqual(wide, 2)  # then 02 beside 03, once 01 is done
        self.assertEqual(waits[0], (2, 1, "both touch src/a.py"))
        self.assertIn((4, 1, "it has no Touches: line"), waits)
        self.assertEqual(lanes.plan_width([(1, ["a/"], 1, [], False), (2, ["b/"], 1, [], False)], ["b/x"])[1],
                         [(2, 1, "it touches a Shared: path")])
        self.assertEqual(lanes.plan_width([(n, ["d%d/" % n], 1, [], False) for n in range(1, 8)])[0], 4)  # the cap
        self.assertEqual(lanes.plan_width([])[0], 0)


class Command(unittest.TestCase):
    def test_flow_status_width_prints_the_width_and_the_waits(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_plan(tmp, CSV)
            out, err = io.StringIO(), io.StringIO()
            self.assertEqual(status.run(["csv", "--width"], out, err, cwd=tmp), 0, err.getvalue())
            self.assertTrue(out.getvalue().startswith("up to 4 tickets can build at once\n"), out.getvalue())
            self.assertIn("  04 waits for 03: level 3 shares the folder app/\n", out.getvalue())

    def test_resolved_tickets_and_the_shared_line_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_plan(tmp, {1: ("a", 1, "src/a/", "", "resolved"), 2: ("b", 1, "src/b/", "", "open"),
                             3: ("c", 1, "lib/", "", "open")}, shared="lib/")
            out, err = io.StringIO(), io.StringIO()
            status.run(["csv", "--width"], out, err, cwd=tmp)
            self.assertEqual(out.getvalue(), "up to 1 ticket can build at once\n  03 waits for 02: it touches a Shared: path\n")


if __name__ == "__main__":
    unittest.main()
