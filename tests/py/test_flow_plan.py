"""The Plan and Build steps of the guided flow's page (feature_flow/flow_plan.py): the drafted plan, its build flow
and its width on the page, and the plan-yes card's picks written into the draft so one yes freezes them with it."""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import brainstorm_page, flow_page, flow_plan, studio  # the modules under test, from this checkout
from test_brainstorm_page import BRAINSTORM
from test_lanes_width import CSV, write_plan

fb = studio.load()


class Draft(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name).resolve()
        subprocess.run(["git", "init", "-q", str(self.dir)], check=True)
        self.cwd = os.getcwd()
        os.chdir(str(self.dir))
        state = self.dir / ".feature-flow" / "state"
        state.mkdir(parents=True)
        (state / "brainstorm-csv.md").write_text(BRAINSTORM, encoding="utf-8")
        write_plan(state / "draft-root", CSV)  # plans/csv under it: move it to where the planner drafts
        (state / "draft").mkdir()
        shutil.move(str(state / "draft-root" / "plans" / "csv"), str(state / "draft" / "csv"))
        self.draft = state / "draft" / "csv"
        cmd = self.draft / "commands.md"
        cmd.write_text(cmd.read_text(encoding="utf-8") + "Profile: `standard`\nLanes: `auto`\nTypecheck: `mypy .`\n",
                       encoding="utf-8")

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def run_page(self, *args):
        out, err = io.StringIO(), io.StringIO()
        return brainstorm_page.main(list(args), out, err), out.getvalue(), err.getvalue()

    def doc(self):
        return flow_page.document(brainstorm_page.document(BRAINSTORM, "csv"), BRAINSTORM, {}, top=self.dir, feature="csv")

    def test_a_draft_makes_plan_the_current_step(self):
        doc = self.doc()
        self.assertEqual([(s["name"], s["state"]) for s in doc["steps"]],
                         [("Style", "done"), ("Team", "done"), ("Options", "done"), ("Plan", "current"),
                          ("Build", "later")])
        self.assertEqual(doc["steps"][3]["summary"], "6 tickets, standard, lanes auto (4)")
        plan, flow = [s for s in doc["sections"] if s.get("step") == "Plan"]
        self.assertIn("Up to 4 tickets can build at once. 04 waits for 03: level 3 shares the folder app/", plan["markdown"])
        self.assertIn('T01["01 model"]', plan["markdown"])
        self.assertIn("- **Gate**: `Test`, `Typecheck`", flow["markdown"])
        self.assertEqual([c["key"] for c in flow["choices"]], ["profile", "lanes", "gate", "full_review"] +
                         ["builder-%02d" % n for n in range(1, 7)])
        self.assertEqual(fb.doc.check(doc), doc)

    def test_the_plan_yes_picks_go_into_the_draft(self):
        said = flow_plan.apply_picks(self.draft, {"profile": "careful", "lanes": "2", "full_review": ["03"]})
        self.assertEqual(said, ["Profile: careful", "Lanes: 2", "Review: full on 03"])
        commands = (self.draft / "commands.md").read_text(encoding="utf-8")
        self.assertIn("Profile: `careful`\nLanes: `2`\n", commands)
        self.assertIn("Review: full", next((self.draft / "tasks").glob("03-*.md")).read_text(encoding="utf-8"))
        flow_plan.apply_picks(self.draft, {"full_review": []})
        self.assertNotIn("Review:", next((self.draft / "tasks").glob("03-*.md")).read_text(encoding="utf-8"))
        for picks, says in (({"profile": "turbo"}, "the profile must be"), ({"lanes": "9"}, "auto or 1 to 4"),
                            ({"full_review": ["99"]}, "a list of the plan's tickets")):
            with self.assertRaises(ValueError, msg=says) as caught:
                flow_plan.apply_picks(self.draft, picks)
            self.assertIn(says, str(caught.exception))

    def test_the_gate_pick_shows_the_profile_default_and_goes_into_the_draft(self):
        flow = [s for s in self.doc()["sections"] if s.get("step") == "Plan"][1]
        gate = next(c for c in flow["choices"] if c["key"] == "gate")
        self.assertEqual(gate["value"], "batch 3")  # the standard profile's default
        self.assertEqual([o["value"] for o in gate["options"]], ["each", "batch 2", "batch 3", "batch 5", "end"])
        self.assertIn("- **When**: `Gate: batch 3`, cheap checks after each ticket", flow["markdown"])
        self.assertEqual(flow_plan.apply_picks(self.draft, {"gate": "end"}), ["Gate: end"])
        self.assertIn("Gate: `end`", (self.draft / "commands.md").read_text(encoding="utf-8"))
        # the shown default follows a new profile; an explicit pick of a profile's default is dropped
        self.assertEqual(flow_plan.apply_picks(self.draft, {"gate": "batch 3"}), ["Gate: batch 3 (the standard default)"])
        self.assertNotIn("Gate:", (self.draft / "commands.md").read_text(encoding="utf-8"))
        self.assertEqual(flow_plan.apply_picks(self.draft, {"profile": "fast", "gate": "batch 3"}),
                         ["Profile: fast", "Gate: end (the fast default)"])
        for value, says in (("batch 0", "batch N (N from 1 to 20)"), ("off unsafe", "only by asking in the chat")):
            with self.assertRaises(ValueError) as caught:
                flow_plan.apply_picks(self.draft, {"gate": value})
            self.assertIn(says, str(caught.exception))

    def test_lanes_past_the_width_are_refused(self):
        tasks = self.draft / "tasks"
        for path in tasks.glob("*.md"):
            path.write_text(path.read_text(encoding="utf-8").replace("Touches:", "Touches: shared/x.py,"), encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            flow_plan.apply_picks(self.draft, {"lanes": "3"})
        self.assertIn("only 1 ticket(s) at once", str(caught.exception))

    def test_the_page_command_writes_the_draft_then_keeps_an_accepted_plan(self):
        folder = self.dir / "live"
        self.assertEqual(self.run_page("csv", "--live", str(folder))[0], 0)
        index = (folder / "index.html").read_text(encoding="utf-8")
        self.assertIn('<section class="step current" role="tabpanel" id="step-4" aria-labelledby="tab-4" data-step="Plan">', index)
        self.assertIn('<button type="button" class="approve" data-approve="Plan" disabled>Approve Plan</button>', index)
        self.assertIn('<div class="ask-about" hidden><script type="application/json">["01 ', index)  # ask about a ticket
        st = json.loads((folder / "state.json").read_text(encoding="utf-8"))
        st["picks"] = {"type": {"by": "u", "at": "t", "value": "map"}, "lanes": {"by": "u", "at": "t", "value": "3"}}
        (folder / "state.json").write_text(json.dumps(st), encoding="utf-8")
        rc, out, err = self.run_page("csv", "--picks", str(folder))
        self.assertEqual(rc, 0, err)
        self.assertEqual(out, "wrote Lanes: 3 into the draft %s\n" % self.draft.as_posix())  # Style and Team are done: type kept
        self.assertNotIn("Type: map", (self.dir / ".feature-flow/state/brainstorm-csv.md").read_text(encoding="utf-8"))
        plan = self.dir / "plans" / "csv"
        shutil.copytree(str(self.draft), str(plan))  # plan-accept
        (plan / "brainstorm.md").write_text(BRAINSTORM, encoding="utf-8")
        rc, out, _ = self.run_page("csv", "--picks", str(folder))
        self.assertIn("kept as approved", out)
        doc = self.doc()
        self.assertEqual([s["state"] for s in doc["steps"]], ["done", "done", "done", "done", "current"])
        self.assertEqual(doc["steps"][4]["summary"], "0 of 6 tickets done")
        self.assertTrue(doc["steps"][3]["summary"].startswith("approved: 6 tickets"))
        flow = [s for s in doc["sections"] if s["title"] == "Build flow"][0]
        self.assertEqual(flow["choices"], [])  # an accepted plan only shows


class Headers(unittest.TestCase):
    def test_set_header_replaces_adds_and_removes(self):
        ticket = "# 01 a\n\nStatus: open\nLevel: 2\n\n## Done when\n"
        self.assertEqual(flow_plan.set_header(ticket, "Review", "full"), "# 01 a\n\nStatus: open\nReview: full\nLevel: 2\n\n## Done when\n")
        self.assertEqual(flow_plan.set_header(ticket, "Level", "3"), ticket.replace("Level: 2", "Level: 3"))
        self.assertEqual(flow_plan.set_header(ticket, "Level", None), ticket.replace("Level: 2\n", ""))
        self.assertEqual(flow_plan.set_header("# C\n\nTest: `x`\n", "Lanes", "`auto`"), "# C\n\nTest: `x`\nLanes: `auto`\n")


if __name__ == "__main__":
    unittest.main()
