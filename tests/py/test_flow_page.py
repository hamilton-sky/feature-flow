"""The guided flow's one page (feature_flow/flow_page.py): the brainstorm page as steps, Setup with the type, the
scout levels and the helpers as choices, and the page's picks written back into the brainstorm's header lines."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import brainstorm_page, flow_page, studio  # the modules under test, from this checkout
from test_brainstorm_page import BRAINSTORM, SKETCH

fb = studio.load()
ENV = {}  # no FLOW_ settings: the normal profile


def page_doc(text):
    return flow_page.document(brainstorm_page.document(text, "csv"), text, ENV)


class Steps(unittest.TestCase):
    def test_a_picked_brainstorm_has_setup_and_options_done(self):
        doc = page_doc(BRAINSTORM)
        self.assertEqual([(s["name"], s["state"]) for s in doc["steps"]],
                         [("Setup", "done"), ("Options", "done"), ("Plan", "later"), ("Build", "later")])
        self.assertEqual(doc["steps"][0]["summary"], "type standard, scouts code=normal web=normal, helpers architect skeptic")
        self.assertEqual(doc["steps"][1]["summary"], "picked B")
        self.assertEqual([(s["title"], s["step"]) for s in doc["sections"]],
                         [("Setup", "Setup"), ("Idea", "Setup"), ("Options", "Options"), ("Chosen", "Options"),
                          ("Open", "Options")])
        self.assertEqual(fb.doc.check(doc), doc)

    def test_before_the_options_setup_is_the_current_step(self):
        doc = page_doc("# Brainstorm: csv\n\nType: learn\n\n## Idea\n\nExport rows.\n")
        self.assertEqual([s["state"] for s in doc["steps"]], ["current", "later", "later", "later"])
        doc = page_doc(SKETCH)
        self.assertEqual([s["state"] for s in doc["steps"]][:2], ["done", "current"])
        self.assertEqual(doc["steps"][1]["summary"], "2 options")

    def test_explore_ends_at_its_verdict(self):
        doc = page_doc("# B\n\nType: explore\n\n## Options\n\n### A. One\n\nx\n\n## Verdict\n\nNo-go.\n")
        self.assertEqual([s["name"] for s in doc["steps"]], ["Setup", "Options"])


class Choices(unittest.TestCase):
    def choices(self, text, env=ENV):
        doc = flow_page.document(brainstorm_page.document(text, "csv"), text, env)
        return {c["key"]: c for c in doc["sections"][0]["choices"]}

    def test_the_choices_show_the_header_and_the_limits(self):
        c = self.choices("# B\n\nType: quick\nScouts: web=off\nHelpers: architect\n\n## Idea\n\nx\n")
        self.assertEqual((c["type"]["value"], c["code"]["value"], c["web"]["value"]), ("quick", "light", "off"))
        self.assertEqual((c["consult"]["value"], c["consult"]["max"]), (["architect"], 1))
        self.assertEqual((c["skeptic"]["max"], c["lens"]["max"]), (0, 0))
        self.assertEqual(c["lens"]["note"], "Your profile and type allow none.")
        careful = self.choices("# B\n\n## Idea\n\nx\n", {"FLOW_PROFILE": "careful"})
        self.assertEqual((careful["consult"]["max"], careful["lens"]["max"]), (3, 3))
        self.assertEqual(careful["consult"]["value"], ["architect"])  # the standard type's helpers
        self.assertEqual(careful["skeptic"]["value"], ["skeptic"])


class Picks(unittest.TestCase):
    def test_picks_become_the_header_lines(self):
        text = "# Brainstorm: csv\n\nPicked by: person\nStyle: route\n\n## Idea\n\nType: in the body stays\n"
        out, lines = flow_page.apply_picks(text, {"type": "learn", "web": "light", "lens": ["ux", "security"]}, ENV)
        self.assertEqual(lines, {"Type": "learn", "Scouts": "code=light web=light", "Helpers": "po skeptic lens=ux,security"})
        self.assertEqual(out, "# Brainstorm: csv\n\nPicked by: person\nStyle: route\nType: learn\nScouts: code=light web=light\n"
                              "Helpers: po skeptic lens=ux,security\n\n## Idea\n\nType: in the body stays\n")
        again, _ = flow_page.apply_picks(out, {"consult": ["architect", "designer"]}, ENV)
        self.assertIn("Type: learn\nScouts: code=light web=light\nHelpers: architect designer skeptic lens=ux,security\n", again)
        self.assertEqual(again.count("Type:"), 2)  # the header's, and the one in the body

    def test_a_bad_pick_or_one_past_the_limits_is_refused(self):
        for picks, says in (({"type": "fast"}, "Type: must be"), ({"code": "huge"}, "code= must be"),
                            ({"lens": ["pretty"]}, "must be a list of"), ({"consult": "architect"}, "must be a list of"),
                            ({"wizard": 1}, "no line for"),
                            ({"consult": ["architect", "designer", "po"]}, "picked 3 consult helper(s), and normal")):
            with self.assertRaises(ValueError, msg=says) as caught:
                flow_page.apply_picks(BRAINSTORM, picks, ENV)
            self.assertIn(says, str(caught.exception))

    def test_a_header_with_only_a_title_gets_the_lines_under_it(self):
        out, _ = flow_page.apply_picks("# B\n\n## Idea\n\nx\n", {"type": "map"}, ENV)
        self.assertTrue(out.startswith("# B\n\nType: map\nHelpers: architect skeptic\n\n## Idea"), out)


class Command(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name).resolve()
        subprocess.run(["git", "init", "-q", str(self.dir)], check=True)
        self.cwd = os.getcwd()
        os.chdir(str(self.dir))
        self.file = self.dir / ".feature-flow" / "state" / "brainstorm-csv.md"
        self.file.parent.mkdir(parents=True)
        self.file.write_text(SKETCH, encoding="utf-8")

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def run_page(self, *args):
        out, err = io.StringIO(), io.StringIO()
        return brainstorm_page.main(list(args), out, err), out.getvalue(), err.getvalue()

    def test_the_live_page_has_steps_and_its_picks_write_the_header(self):
        folder = self.dir / "live"
        self.assertEqual(self.run_page("csv", "--live", str(folder))[0], 0)
        index = (folder / "index.html").read_text(encoding="utf-8")
        self.assertIn('<div class="step done" data-step="Setup">', index)
        self.assertIn('data-key="lens" data-kind="some" data-max="2"', index)
        rc, out, _ = self.run_page("csv", "--picks", str(folder))
        self.assertEqual((rc, out), (0, "no picks on the page: %s is as it was\n" % self.file.as_posix()))
        st = json.loads((folder / "state.json").read_text(encoding="utf-8"))
        st["picks"] = {"type": {"by": "u_me", "at": "t", "value": "map"}}
        (folder / "state.json").write_text(json.dumps(st), encoding="utf-8")
        rc, out, err = self.run_page("csv", "--picks", str(folder))
        self.assertEqual(rc, 0, err)
        self.assertIn("Type: map, Helpers: architect skeptic", out)
        self.assertTrue(self.file.read_text(encoding="utf-8").startswith("# Brainstorm: csv\n\nType: map\n"))
        st["picks"] = {"consult": {"by": "u_me", "at": "t", "value": ["architect", "designer", "po"]}}
        (folder / "state.json").write_text(json.dumps(st), encoding="utf-8")
        before = self.file.read_text(encoding="utf-8")
        rc, _, err = self.run_page("csv", "--picks", str(folder))
        self.assertEqual(rc, 1)
        self.assertIn("picked 3 consult helper(s)", err)
        self.assertEqual(self.file.read_text(encoding="utf-8"), before)

    def test_a_bad_header_says_what_to_fix_and_page_is_the_same_command(self):
        self.file.write_text("# B\n\nHelpers: wizard\n\n## Idea\n\nx\n", encoding="utf-8")
        rc, _, err = self.run_page("csv")
        self.assertEqual(rc, 1)
        self.assertIn("Helpers: takes", err)
        self.file.write_text(SKETCH, encoding="utf-8")
        done = subprocess.run([sys.executable, str(helpers.ROOT / "scripts" / "flow-status.py"), "csv", "--page"],
                              cwd=str(self.dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("brainstorm-csv.html", done.stdout)


if __name__ == "__main__":
    unittest.main()
