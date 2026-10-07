"""Planning: plan-prompt, plan-review-prompt and plan-accept (plans/feature-planner tickets 03 and 04)."""

import os
import shutil
import subprocess
import sys
import unittest

from helpers import ROOT, Repo, ticket_text

DRAFT = ".feature-flow/state/draft/g"


class Planning(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        for folder in ("guides", "agents"):
            shutil.copytree(str(ROOT / folder), str(self.repo.path(".feature-flow/" + folder)))
        self.repo.path("brief.md").write_text("Feature: g\nWhat: a thing\nThe bar: `true` exits 0\n", encoding="utf-8")
        self.repo.commit("guides and a brief")

    def tearDown(self):
        self.repo.close()

    def flow(self, *args, **env):
        full = {k: v for k, v in os.environ.items() if not k.startswith("FLOW_")}
        full.update(env)
        result = subprocess.run([sys.executable, "scripts/flow.py", "g"] + list(args), cwd=str(self.repo.dir),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, env=full)
        return result.returncode, result.stdout.strip(), result.stderr

    def write_draft(self, tickets=(("01-a", "A", "—"), ("02-b", "B", "01"))):
        draft = self.repo.path(DRAFT)
        (draft / "tasks").mkdir(parents=True, exist_ok=True)
        for slug, title, blocked in tickets:
            (draft / "tasks" / ("%s.md" % slug)).write_text(ticket_text(title, "open", blocked), encoding="utf-8")
        for name, text in (("spec.md", "# Spec\n"), ("map.md", "# Map: g\n"), ("learnings.md", "# Learnings: g\n"),
                           ("commands.md", "# Commands: g\n\nTest: `true`\n")):
            (draft / name).write_text(text, encoding="utf-8")

    # ---- plan-prompt ---------------------------------------------------

    def test_plan_prompt_prints_the_planner_role_guide_and_brief(self):
        rc, out, _ = self.flow("plan-prompt", "brief.md")
        self.assertEqual(rc, 0, out)
        self.assertTrue(out.startswith("You are the planner."), out[:80])
        self.assertIn("# Plan a feature", out)
        self.assertIn("Feature: g\nWhat: a thing", out)
        self.assertIn("`%s/`" % DRAFT, out)
        self.assertNotIn("<draft>", out)
        self.assertTrue(out.endswith("The bar: `true` exits 0"), out[-80:])
        self.assertEqual(self.repo.path(".feature-flow/state/brief-g.md").read_text(encoding="utf-8"),
                         "Feature: g\nWhat: a thing\nThe bar: `true` exits 0\n")
        self.assertTrue(self.repo.path(DRAFT + "/tasks").is_dir())
        self.assertEqual(self.repo.porcelain(), "")

    def test_plan_prompt_stops_when_the_plan_exists(self):
        rc, out = self.repo.flow("plan-prompt", "brief.md")
        self.assertEqual((rc, out), (1, "STOP plans/f already exists. pick another name: a plan is never overwritten"))

    def test_plan_prompt_stops_on_a_missing_brief(self):
        rc, out, _ = self.flow("plan-prompt", "nope.md")
        self.assertEqual(rc, 1)
        self.assertTrue(out.startswith("STOP cannot read the brief nope.md"), out)

    def test_a_first_round_clears_the_old_draft_and_a_findings_round_keeps_it(self):
        self.write_draft()
        self.repo.path("findings.txt").write_text("1. spec.md: the bar is missing\nPLAN-REVIEW: FAIL\n", encoding="utf-8")
        rc, out, _ = self.flow("plan-prompt", "brief.md", "findings.txt")
        self.assertEqual(rc, 0, out)
        self.assertIn("## Review findings from the last round", out)
        self.assertIn("the bar is missing", out)
        self.assertTrue(self.repo.path(DRAFT + "/tasks/01-a.md").is_file())
        rc, out, _ = self.flow("plan-prompt", "brief.md")
        self.assertEqual(rc, 0, out)
        self.assertNotIn("Review findings", out)
        self.assertFalse(self.repo.path(DRAFT + "/tasks/01-a.md").exists())

    # ---- plan-review-prompt --------------------------------------------

    def test_plan_review_prompt_needs_a_brief_and_a_draft(self):
        rc, out, _ = self.flow("plan-review-prompt")
        self.assertEqual((rc, out), (1, "STOP no brief for g. run plan-prompt first"))

    def test_plan_review_prompt_prints_the_reviewer_role_and_the_brief_only(self):
        self.flow("plan-prompt", "brief.md")
        self.write_draft()
        rc, out, _ = self.flow("plan-review-prompt")
        self.assertEqual(rc, 0, out)
        self.assertTrue(out.startswith("You are the plan reviewer, not the planner."), out[:80])
        self.assertIn("# Review a draft plan", out)
        self.assertIn("Feature: g\nWhat: a thing", out)
        self.assertNotIn("You are the planner.", out)
        self.assertIn("PLAN-REVIEW: PASS", out)

    # ---- plan-accept ---------------------------------------------------

    def test_plan_accept_copies_a_checked_draft(self):
        self.flow("plan-prompt", "brief.md")
        self.write_draft()
        rc, out, _ = self.flow("plan-accept")
        self.assertEqual((rc, out), (0, "OK plans/g"))
        for name in ("spec.md", "map.md", "learnings.md", "commands.md", "tasks/01-a.md", "tasks/02-b.md"):
            self.assertTrue(self.repo.path("plans/g/" + name).is_file(), name)
        self.assertIn("plans/g/", self.repo.porcelain())
        self.assertIn("PLAN-ACCEPT", self.repo.path(".feature-flow/state/flow-g.log").read_text(encoding="utf-8"))

    def test_plan_accept_follows_flow_dir(self):
        self.flow("plan-prompt", "brief.md")
        self.write_draft()
        rc, out, _ = self.flow("plan-accept", FLOW_DIR="docs/plans")
        self.assertEqual((rc, out), (0, "OK docs/plans/g"))
        self.assertTrue(self.repo.path("docs/plans/g/tasks/01-a.md").is_file())

    def test_plan_accept_never_overwrites(self):
        self.write_draft()
        rc, out = self.repo.flow("plan-accept")
        self.assertEqual(rc, 1)
        self.assertTrue(out.startswith("STOP plans/f already exists"), out)

    def test_plan_accept_stops_without_a_draft(self):
        rc, out, _ = self.flow("plan-accept")
        self.assertEqual((rc, out), (1, "STOP no draft plan in %s/. run the planner first" % DRAFT))
        self.assertFalse(self.repo.path("plans/g").exists())

    def test_plan_accept_copies_nothing_when_the_draft_fails_the_check(self):
        self.write_draft((("01-a", "A", "02"), ("02-b", "B", "01")))
        rc, out, _ = self.flow("plan-accept")
        self.assertEqual(rc, 1)
        self.assertTrue(out.startswith("STOP the draft fails the plan check"), out)
        self.assertFalse(self.repo.path("plans/g").exists())

    def test_usage_names_the_plan_commands(self):
        rc, _, err = self.flow("plan-prompt")
        self.assertEqual(rc, 2)
        for name in ("plan-prompt", "plan-review-prompt", "plan-accept"):
            self.assertIn(name, err)
        self.assertEqual(self.flow("plan-accept", "extra")[0], 2)


if __name__ == "__main__":
    unittest.main()
