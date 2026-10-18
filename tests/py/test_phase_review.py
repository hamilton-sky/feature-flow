"""Review: gate skips the fresh reviewer when the conductor's checks prove the ticket, and a plan whose last
ticket is `Type: acceptance` gets one phase review, two or three area reviewers over the whole range, before
it. Their findings go into the acceptance ticket, whose build is the one fix pass."""

import shutil
import sys
import unittest

from helpers import ROOT, Repo

PYTHON = '"%s"' % sys.executable
CHECK = "```check\n$ %s -c \"print('fine')\"\nprints fine\n```\n\n" % PYTHON
COMMANDS = "# Commands: f\n\nSmoke: `%s -c \"pass\"`\nTest: `%s -c \"pass\"`\n" % (PYTHON, PYTHON)
T = ["plans/f/tasks/01-a.md", "plans/f/tasks/02-b.md", "plans/f/tasks/03-accept.md"]


def ticket(title, blocked, header="", check=True, kind="task"):
    return ("# %s\n\nType: %s\nStatus: open\nBlocked by: %s\nTest first: no\n%s\nbody\n\n## Done when\n\n- x\n\n%s"
            "## Answer\n" % (title, kind, blocked, header + "\n" if header else "", CHECK if check else ""))


class Base(unittest.TestCase):
    PLAN = (("01-a", ticket("A", "—", "Review: gate")),
            ("02-b", ticket("B", "01", "Review: gate", check=False)),
            ("03-accept", ticket("Acceptance", "01, 02", kind="acceptance")))

    def setUp(self):
        self.repo = Repo(tickets=())
        self.addCleanup(self.repo.close)
        for folder in ("agents", "guides"):
            shutil.copytree(str(ROOT / folder), str(self.repo.path(folder)))
        self.repo.path("plans/f/commands.md").write_text(COMMANDS, encoding="utf-8")
        for slug, text in self.PLAN:
            self.repo.path("plans/f/tasks/%s.md" % slug).write_text(text, encoding="utf-8")
        self.repo.commit("plan")
        self.plan_commit = self.repo.head()
        self.env = {"FLOW_TICKETS_PER_SESSION": "99"}
        rc, out = self.repo.flow("start", **self.env)
        self.env["FLOW_SESSION"] = out.split()[1]
        self.pass_file = self.reply("pass", "fine\nREVIEW: PASS\n")
        self.fail_file = self.reply("fail", "PHASE security\n1. major app.py save: stores the token in the draft"
                                            " - drop it class: token in drafts\nREVIEW: FAIL\n")

    def reply(self, name, text):
        path = self.repo.dir.parent / ("%s-%s.txt" % (self.repo.dir.name, name))
        path.write_text(text, encoding="utf-8")
        self.addCleanup(path.unlink, missing_ok=True)
        return str(path)

    def flow(self, *args, **env):
        return self.repo.flow(*args, **dict(self.env, **env))

    def build(self, index, lines=3, **env):
        rc, out = self.flow("next", **env)
        self.assertTrue(out.startswith("BUILD %s " % T[index]), out)
        self.repo.path("work-%d.txt" % index).write_text("x\n" * lines, encoding="utf-8")
        self.repo.set_status(T[index], "resolved")
        self.repo.commit("feat: %d" % index)

    def review_passes(self, **env):
        while True:
            rc, out = self.flow("next", **env)
            if not out.startswith("REVIEW"):
                return out
            self.flow("prompt", **env)
            self.assertEqual(self.flow("verdict", self.pass_file, **env), (0, "OK"))

    def to_phase_review(self, **env):
        self.build(0, **env)
        self.build(1, **env)
        return self.review_passes(**env)


class GateReview(Base):
    def test_a_gate_ticket_with_a_passing_check_block_skips_the_reviewer(self):
        self.build(0)
        rc, out = self.flow("next")
        self.assertTrue(out.startswith("BUILD %s " % T[1]), out)
        self.assertIn(",01,REVIEW-SKIP", self.repo.log())
        self.assertNotIn(",01,REVIEW\n", self.repo.log())

    def test_a_gate_ticket_without_a_check_block_is_reviewed(self):
        self.build(0)
        self.build(1)
        rc, out = self.flow("next")
        self.assertTrue(out.startswith("REVIEW %s " % T[1]), out)

    def test_a_big_diff_is_reviewed_whatever_the_review_line_says(self):
        self.build(0, lines=5, FLOW_REVIEW_GATE_LINES="4")
        rc, out = self.flow("next", FLOW_REVIEW_GATE_LINES="4")
        self.assertTrue(out.startswith("REVIEW %s " % T[0]), out)

    def test_a_ticket_a_reviewer_failed_is_reviewed_again_after_its_rebuild(self):
        self.build(0, lines=5, FLOW_REVIEW_GATE_LINES="4")
        self.flow("next", FLOW_REVIEW_GATE_LINES="4")
        self.assertEqual(self.flow("verdict", self.fail_file), (0, "OK"))
        rc, out = self.flow("next")
        self.assertTrue(out.startswith("BUILD %s " % T[0]), out)
        self.repo.set_status(T[0], "resolved")
        self.repo.commit("fix")  # a small fix: under the line limit now
        rc, out = self.flow("next")
        self.assertTrue(out.startswith("REVIEW %s " % T[0]), out)


class PhaseReview(Base):
    def test_the_acceptance_ticket_waits_for_the_phase_review(self):
        out = self.to_phase_review()
        self.assertEqual(out, "PHASE-REVIEW f %s %s correctness,security,performance"
                         % (self.plan_commit, self.repo.head()))
        self.assertIn("PHASE-BASE %s" % self.plan_commit, self.repo.log())

    def test_each_area_gets_its_own_prompt(self):
        self.to_phase_review()
        rc, out = self.flow("prompt")
        self.assertEqual(rc, 1)
        self.assertIn("name the phase review area", out)
        rc, out = self.flow("prompt", "security")
        self.assertEqual(rc, 0, out)
        self.assertIn("area `security`", out)
        self.assertIn('git diff "%s..%s"' % (self.plan_commit, self.repo.head()), out)
        self.assertIn("':(exclude)plans/f/tasks/'", out)
        self.assertNotIn("<area>", out)

    def test_a_failed_area_sends_its_findings_to_the_acceptance_build(self):
        self.to_phase_review()
        for area, reply in (("correctness", self.pass_file), ("security", self.fail_file),
                            ("performance", self.pass_file)):
            self.assertEqual(self.flow("verdict", reply, area), (0, "OK"))
        rc, out = self.flow("next")
        self.assertTrue(out.startswith("BUILD %s " % T[2]), out)
        text = self.repo.path(T[2]).read_text(encoding="utf-8")
        self.assertIn("## Review findings (round 1, phase review: security)", text)
        self.assertIn("class: token in drafts", text)
        self.assertEqual(self.repo.state()["round"], "1")
        self.assertEqual(self.repo.state()["must_review"], "1")
        self.assertIn("The debugging guide follows", self.flow("prompt")[1])
        self.assertIn("phase review findings for 03", self.repo.git("log", "-1", "--format=%s"))
        self.assertIn(",phase,PHASE-FAIL", self.repo.log())

    def test_a_clean_phase_review_goes_straight_on(self):
        self.to_phase_review()
        for area in ("correctness", "security", "performance"):
            self.flow("verdict", self.pass_file, area)
        rc, out = self.flow("next")
        self.assertTrue(out.startswith("BUILD %s " % T[2]), out)
        self.assertNotIn("Review findings", self.repo.path(T[2]).read_text(encoding="utf-8"))
        self.assertEqual(self.repo.state()["round"], "0")

    def test_an_area_without_a_verdict_is_asked_again_then_stops(self):
        self.to_phase_review()
        self.flow("verdict", self.pass_file, "correctness")
        self.flow("verdict", self.pass_file, "performance")
        rc, out = self.flow("next")
        self.assertEqual(out, "PHASE-REVIEW f %s %s security" % (self.plan_commit, self.repo.head()))
        rc, out = self.flow("next")
        self.assertEqual(rc, 1)
        self.assertIn("no phase review verdict from security", out)

    def test_a_phase_reviewer_that_changes_files_stops_the_run(self):
        self.to_phase_review()
        self.repo.path("plans/f/spec.md").write_text("changed\n", encoding="utf-8")
        rc, out = self.flow("next")
        self.assertEqual(rc, 1)
        self.assertIn("a phase reviewer changed tracked files", out)

    def test_off_skips_it_and_fewer_areas_can_be_named(self):
        self.assertTrue(self.to_phase_review(FLOW_PHASE_REVIEW="off").startswith("BUILD %s " % T[2]))
        rc, out = self.repo.flow("start", FLOW_PHASE_AREAS="speed")
        self.assertIn("FLOW_PHASE_AREAS must name one to three of", out)

    def test_two_areas(self):
        out = self.to_phase_review(FLOW_PHASE_AREAS="correctness,security")
        self.assertTrue(out.endswith(" correctness,security"), out)

    def test_the_prompt_can_go_to_a_file(self):
        self.to_phase_review()
        rc, out = self.flow("prompt", "--file", "performance")
        self.assertEqual(out, "PROMPT .feature-flow/state/prompt-f-performance.md")
        text = self.repo.path(".feature-flow/state/prompt-f-performance.md").read_text(encoding="utf-8")
        self.assertEqual(text.strip(), self.flow("prompt", "performance")[1])
        self.assertEqual(self.flow("prompt", "--file", "a", "b")[0], 2)


class OnDemand(Base):
    PLAN = (("01-a", ticket("A", "—", "Review: gate")),
            ("02-b", ticket("B", "01", "Review: gate")),
            ("03-accept", ticket("Acceptance", "01, 02", "Review: gate")))

    def test_a_plan_without_an_acceptance_type_has_no_automatic_phase_review(self):
        for index in range(3):
            self.build(index)
        rc, out = self.flow("next")
        self.assertTrue(out.startswith("DONE"), out)

    def test_review_phase_reopens_the_last_ticket_for_the_fix(self):
        for index in range(3):
            self.build(index)
        self.flow("next")
        rc, out = self.flow("review-phase")
        self.assertTrue(out.startswith("PHASE-REVIEW f %s " % self.plan_commit), out)
        self.assertEqual(self.flow("review-phase")[0], 1)  # one at a time
        for area, reply in (("correctness", self.fail_file), ("security", self.pass_file),
                            ("performance", self.pass_file)):
            self.flow("verdict", reply, area)
        rc, out = self.flow("next")
        self.assertTrue(out.startswith("BUILD %s " % T[2]), out)
        self.assertIn("phase review: correctness", self.repo.path(T[2]).read_text(encoding="utf-8"))

    def test_review_phase_needs_the_runner_and_no_pending_step(self):
        rc, out = self.repo.flow("review-phase", FLOW_TRUSTED="0", FLOW_SESSION=self.env["FLOW_SESSION"])
        self.assertIn("STOP run the conductor through scripts/flow-trust.py", out)
        self.flow("next")
        rc, out = self.flow("review-phase")
        self.assertEqual(rc, 1)
        self.assertIn("a build is pending", out)


if __name__ == "__main__":
    unittest.main()
