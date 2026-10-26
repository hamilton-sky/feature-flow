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
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, env=full,
                                encoding="utf-8")
        return result.returncode, result.stdout.strip(), result.stderr

    def write_draft(self, tickets=(("01-a", "A", "—"), ("02-b", "B", "01"))):
        draft = self.repo.path(DRAFT)
        (draft / "tasks").mkdir(parents=True, exist_ok=True)
        for slug, title, blocked in tickets:
            (draft / "tasks" / ("%s.md" % slug)).write_text(ticket_text(title, "open", blocked).replace("Test first: no\n", "Test first: no\nCheck: none a fixture\n"),
                encoding="utf-8")
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

    # ---- the brainstorm ------------------------------------------------

    def brainstorm(self, line="Brainstorm: .feature-flow/state/brainstorm-g.md\n"):
        self.repo.path("brief.md").write_text("Feature: g\nWhat: a thing\nThe bar: `true` exits 0\n" + line,
                                              encoding="utf-8")
        notes = self.repo.path(".feature-flow/state/brainstorm-g.md")
        notes.parent.mkdir(parents=True, exist_ok=True)
        notes.write_text("# Brainstorm: g\n\nPicked by: person\n\n## Chosen\n\nA\n", encoding="utf-8")
        return notes

    def test_a_brief_that_names_its_brainstorm_carries_it_into_the_draft_and_the_plan(self):
        self.brainstorm()
        rc, out, _ = self.flow("plan-prompt", "brief.md")
        self.assertEqual(rc, 0, out)
        self.assertIn("## The brainstorm", out)
        self.assertIn("`%s/brainstorm.md`. Read it first" % DRAFT, out)
        self.assertIn("## Chosen\n\nA", self.repo.path(DRAFT + "/brainstorm.md").read_text(encoding="utf-8"))
        self.write_draft()
        rc, out, _ = self.flow("plan-review-prompt")
        self.assertEqual(rc, 0, out)
        self.assertIn("Check 11 applies.", out)
        self.assertEqual(self.flow("plan-accept")[:2], (0, "OK plans/g"))
        self.assertTrue(self.repo.path("plans/g/brainstorm.md").is_file())

    def test_a_findings_round_puts_the_brainstorm_back_as_the_user_picked_it(self):
        self.brainstorm()
        self.flow("plan-prompt", "brief.md")
        self.repo.path(DRAFT + "/brainstorm.md").write_text("changed by the planner\n", encoding="utf-8")
        self.repo.path("findings.txt").write_text("1. spec.md: no diagram\nPLAN-REVIEW: FAIL\n", encoding="utf-8")
        rc, out, _ = self.flow("plan-prompt", "brief.md", "findings.txt")
        self.assertEqual(rc, 0, out)
        self.assertIn("Picked by: person", self.repo.path(DRAFT + "/brainstorm.md").read_text(encoding="utf-8"))

    def test_a_brief_without_a_brainstorm_line_ignores_an_old_brainstorm(self):
        self.brainstorm(line="Brainstorm: <.feature-flow/state/brainstorm-<feature>.md, only when Step 0 ran>\n")
        rc, out, _ = self.flow("plan-prompt", "brief.md")
        self.assertEqual(rc, 0, out)
        self.assertNotIn("## The brainstorm", out)
        self.assertFalse(self.repo.path(DRAFT + "/brainstorm.md").exists())

    def test_a_brainstorm_line_must_name_this_features_file_and_it_must_exist(self):
        self.brainstorm(line="Brainstorm: notes.md\n")
        rc, out, _ = self.flow("plan-prompt", "brief.md")
        self.assertEqual((rc, out), (1, "STOP the brief's Brainstorm: line must name "
                                        ".feature-flow/state/brainstorm-g.md, not notes.md"))
        self.brainstorm().unlink()
        rc, out, _ = self.flow("plan-prompt", "brief.md")
        self.assertEqual(rc, 1)
        self.assertTrue(out.startswith("STOP the brief names the brainstorm .feature-flow/state/brainstorm-g.md, "
                                       "which does not exist"), out)

    def ask(self, text="How does the code export rows today?\n"):
        self.repo.path("q.md").write_text(text, encoding="utf-8")
        return "q.md"

    def test_brainstorm_prompt_gives_each_helper_its_role_and_the_brainstorm(self):
        q = self.ask()
        for helper, start, end in (("scout", "You are a scout.", "change nothing."),
                                   ("architect", "You are the architect", "`ANSWER: GIVEN` or `ANSWER: USER`."),
                                   ("skeptic", "You are the skeptic", "`SKEPTIC: DONE`.")):
            rc, out, _ = self.flow("brainstorm-prompt", helper, q)
            self.assertEqual(rc, 0, out)
            self.assertIn(start, out)
            self.assertIn("brainstorming how to build the feature `g`, before it is planned", out)
            self.assertIn("How does the code export rows today?", out)
            self.assertTrue(out.endswith(end), out[-80:])
        self.assertIn("ROLE: planner", self.flow("brainstorm-prompt", "web", q)[1])
        log = self.repo.path(".feature-flow/state/flow-g.log").read_text(encoding="utf-8")
        for event in ("BRAINSTORM-SCOUT", "BRAINSTORM-ARCHITECT", "BRAINSTORM-SKEPTIC", "BRAINSTORM-WEB"):
            self.assertIn(event, log)
        self.assertEqual(self.repo.porcelain(), "?? q.md")

    def test_the_script_counts_the_helpers_and_refuses_past_the_limit(self):
        q = self.ask()
        for _ in range(2):
            self.assertEqual(self.flow("brainstorm-prompt", "scout", q)[0], 0)
        rc, out, _ = self.flow("brainstorm-prompt", "scout", q)
        self.assertEqual(rc, 1)
        self.assertTrue(out.startswith("STOP the brainstorm of g has used its 2 scout helper(s) (normal;"), out)
        self.assertEqual(self.flow("brainstorm-prompt", "scout", q, FLOW_PROFILE="careful")[0], 0)  # careful allows 3
        self.assertEqual(self.flow("brainstorm-prompt", "skeptic", q)[0], 0)
        self.assertEqual(self.flow("brainstorm-prompt", "skeptic", q)[0], 1)
        for helper in ("architect", "po"):
            self.assertEqual(self.flow("brainstorm-prompt", helper, q)[0], 0)
        self.assertEqual(self.flow("brainstorm-prompt", "designer", q)[0], 1)  # the consultants share 2
        self.repo.path(".feature-flow/state/brainstorm-g.helpers").unlink()
        self.assertEqual(self.flow("brainstorm-prompt", "designer", q)[0], 0)

    def test_without_scouts_the_brainstorm_gets_no_scout_or_web_helper(self):
        q = self.ask()
        for helper in ("scout", "web"):
            rc, out, _ = self.flow("brainstorm-prompt", helper, q, FLOW_SCOUTS="off")
            self.assertEqual(rc, 1, out)
            self.assertIn("FLOW_SCOUTS=off allows no scouts", out)
        self.assertEqual(self.flow("brainstorm-prompt", "skeptic", q, FLOW_SCOUTS="off")[0], 0)

    def test_brainstorm_prompt_refuses_an_unknown_helper_an_empty_question_and_an_existing_plan(self):
        self.assertEqual(self.flow("brainstorm-prompt", "boss", self.ask())[:2],
                         (1, "STOP brainstorm-prompt takes scout, web, architect, designer, po, skeptic, not boss"))
        self.assertEqual(self.flow("brainstorm-prompt", "scout", self.ask(""))[:2], (1, "STOP the question q.md is empty"))
        rc, out = self.repo.flow("brainstorm-prompt", "scout", "q.md")
        self.assertEqual((rc, out), (1, "STOP plans/f already exists. pick another name: a plan is never overwritten"))

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

    def test_a_feature_name_with_a_path_is_refused_and_deletes_nothing(self):
        victim = self.repo.path("victim")
        victim.mkdir()
        (victim / "keep.txt").write_text("keep\n", encoding="utf-8")
        for name in ("../../../victim", "..", "a/b", "a\\b", "C:foo", "C:"):
            full = {k: v for k, v in os.environ.items() if not k.startswith("FLOW_")}
            result = subprocess.run([sys.executable, "scripts/flow.py", name, "plan-prompt", "brief.md"],
                                    cwd=str(self.repo.dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    universal_newlines=True, env=full, encoding="utf-8")
            self.assertEqual(result.returncode, 2, name)
            self.assertIn("plain folder name", result.stderr)
        self.assertTrue((victim / "keep.txt").is_file())

    def test_usage_names_the_plan_commands(self):
        rc, _, err = self.flow("plan-prompt")
        self.assertEqual(rc, 2)
        for name in ("plan-prompt", "plan-review-prompt", "plan-accept"):
            self.assertIn(name, err)
        self.assertEqual(self.flow("plan-accept", "extra")[0], 2)


if __name__ == "__main__":
    unittest.main()
