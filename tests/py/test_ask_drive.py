"""Drive questions through the conductor the way the skill does: a builder's `## Ask: <role>` section or a
reviewer's `REVIEW: ASK <role>` pauses the job, `next` hands out `ASK <role> ...`, the consultant's reply goes
through `verdict`, and the job goes on with the answer. Questions for the user stop the run, and so does a third
question for a consultant on one ticket.
"""

import shutil
import sys
import unittest

from helpers import ROOT, Repo

PYTHON = '"%s"' % sys.executable
CHECK = "```check\n$ %s -c \"print('fine')\"\nprints fine\n```\n\n" % PYTHON
T1 = "plans/f/tasks/01-t.md"


class AskDrive(unittest.TestCase):
    def setup(self, **env):
        repo = Repo(tickets=())
        self.addCleanup(repo.close)
        env = dict({"FLOW_TICKETS_PER_SESSION": "99", "FLOW_SCOUTS": "off"}, **env)
        for folder in ("agents", "guides"):
            shutil.copytree(str(ROOT / folder), str(repo.path(folder)))
        repo.path("plans/f/commands.md").write_text(
            "# Commands: f\n\nSmoke: `%s -c \"pass\"`\nTest: `%s -c \"pass\"`\n" % (PYTHON, PYTHON), encoding="utf-8")
        repo.path(T1).write_text("# T1\n\nType: task\nStatus: open\nBlocked by: —\nTest first: no\nLevel: 2\n\nbody\n\n"
                                 "## Done when\n\n- x\n\n" + CHECK + "## Answer\n", encoding="utf-8")
        repo.commit("plan")
        rc, out = repo.flow("start", **env)
        env["FLOW_SESSION"] = out.split()[1]
        self.reply = repo.dir.parent / (repo.dir.name + "-reply.txt")
        self.addCleanup(self.reply.unlink, missing_ok=True)
        self.repo, self.env = repo, env
        return repo, env

    def flow(self, *args):
        return self.repo.flow(*args, **self.env)

    def ask_in_ticket(self, role, question):
        with open(str(self.repo.path(T1)), "a", encoding="utf-8") as handle:
            handle.write("\n## Ask: %s\n\n%s\n" % (role, question))
        self.repo.commit("ask")

    def answer(self, text, last="ANSWER: GIVEN"):
        self.reply.write_text("## Answer\n\n%s\n\n%s\n" % (text, last), encoding="utf-8")
        return self.flow("verdict", str(self.reply))

    def test_a_builder_question_goes_to_its_consultant_and_the_answer_into_the_ticket(self):
        repo, env = self.setup(FLOW_MAX_RETRIES="1")
        self.assertTrue(self.flow("next")[1].startswith("BUILD"))
        self.ask_in_ticket("architect", "Should the cache live in store.py or a new module?")
        rc, line = self.flow("next")
        self.assertEqual(line.split()[:4], ["ASK", "architect", T1, "01"])
        prompt = self.flow("prompt")[1]
        self.assertIn("You are the architect", prompt)
        self.assertIn("Should the cache live in store.py or a new module?", prompt)
        self.assertIn("comes from the builder of ticket 01", prompt)
        self.assertEqual(self.answer("Put it in a new module, cache.py."), (0, "OK"))
        rc, line = self.flow("next")
        self.assertTrue(line.startswith("BUILD %s 01" % T1), line)  # the question was no failed attempt
        ticket = repo.path(T1).read_text(encoding="utf-8")
        self.assertIn("## Consulted (architect)", ticket)
        self.assertIn("Put it in a new module, cache.py.", ticket)
        self.assertEqual(repo.porcelain(), "")
        self.assertIn("ASK-ARCHITECT-GIVEN", repo.log())

    def test_a_question_for_the_user_stops_and_goes_on_once_answered_in_the_ticket(self):
        repo, env = self.setup()
        self.flow("next")
        self.ask_in_ticket("user", "CSV or JSON for the export?")
        rc, out = self.flow("next")
        self.assertEqual(rc, 1)
        self.assertIn("01-t asks you: CSV or JSON for the export?", out)
        self.assertEqual(self.flow("next")[0], 1)  # still waiting
        with open(str(repo.path(T1)), "a", encoding="utf-8") as handle:
            handle.write("\n## Consulted (user)\n\nCSV.\n")
        repo.commit("answer")
        rc, line = self.flow("next")
        self.assertTrue(line.startswith("BUILD"), line)

    def test_a_consultant_that_says_user_stops_with_its_options_in_the_ticket(self):
        repo, env = self.setup()
        self.flow("next")
        self.ask_in_ticket("po", "Should deleted rows be exported?")
        self.flow("next")
        self.assertEqual(self.answer("Either: skip them, or mark them.", "ANSWER: USER"), (0, "OK"))
        rc, out = self.flow("next")
        self.assertEqual(rc, 1)
        self.assertIn("The po says only you can decide. Its options: Either: skip them, or mark them.", out)
        ticket = repo.path(T1).read_text(encoding="utf-8")
        self.assertIn("## Ask: user", ticket)
        self.assertNotIn("## Consulted (po)", ticket)
        with open(str(repo.path(T1)), "a", encoding="utf-8") as handle:
            handle.write("\n## Consulted (user)\n\nMark them.\n")
        repo.commit("answer")
        self.assertTrue(self.flow("next")[1].startswith("BUILD"))

    def test_a_third_question_on_one_ticket_goes_to_the_user(self):
        repo, env = self.setup()
        self.flow("next")
        for n in (1, 2):
            self.ask_in_ticket("architect", "question %d" % n)
            self.assertEqual(self.flow("next")[1].split()[0], "ASK")
            self.answer("answer %d" % n)
            self.assertEqual(self.flow("next")[1].split()[0], "BUILD")
        self.ask_in_ticket("designer", "question 3")
        rc, out = self.flow("next")
        self.assertEqual(rc, 1)
        self.assertIn("(for the designer, but this ticket asked its consultants 2 times already) question 3", out)

    def test_a_reviewer_question_comes_back_as_a_note_in_the_next_review(self):
        repo, env = self.setup()
        self.flow("next")
        repo.resolve(T1)
        self.assertTrue(self.flow("next")[1].startswith("REVIEW"))
        self.reply.write_text("SPEC\n\n## Question\n\nIs an empty file a valid export?\n\nREVIEW: ASK po\n", encoding="utf-8")
        self.assertEqual(self.flow("verdict", str(self.reply)), (0, "OK"))
        rc, line = self.flow("next")
        self.assertEqual(line.split()[:2], ["ASK", "po"])
        prompt = self.flow("prompt")[1]
        self.assertIn("You are the product owner", prompt)
        self.assertIn("comes from the reviewer", prompt)
        self.assertIn("Is an empty file a valid export?", prompt)
        self.answer("Yes, with the header row only.")
        rc, line = self.flow("next")
        self.assertTrue(line.startswith("REVIEW"), line)
        self.assertIn("the answer: Yes, with the header row only.", self.flow("prompt")[1])

    def test_a_reviewer_question_for_the_user_stops_then_the_ticket_goes_back_to_its_builder(self):
        repo, env = self.setup()
        self.flow("next")
        repo.resolve(T1)
        self.flow("next")
        self.reply.write_text("## Question\n\nShip it behind a flag?\n\nREVIEW: ASK user\n", encoding="utf-8")
        self.flow("verdict", str(self.reply))
        rc, out = self.flow("next")
        self.assertEqual(rc, 1)
        self.assertIn("01-t asks you: Ship it behind a flag?", out)
        ticket = repo.path(T1).read_text(encoding="utf-8")
        self.assertIn("## Ask: user", ticket)
        self.assertIn("Status: open", ticket)
        with open(str(repo.path(T1)), "a", encoding="utf-8") as handle:
            handle.write("\n## Consulted (user)\n\nYes, behind a flag.\n")
        repo.commit("answer")
        rc, line = self.flow("next")
        self.assertTrue(line.startswith("BUILD"), line)

    def test_a_consultant_that_edits_a_file_stops_the_run(self):
        repo, env = self.setup()
        self.flow("next")
        self.ask_in_ticket("architect", "where?")
        self.flow("next")
        repo.path("x.txt").write_text("x\n", encoding="utf-8")
        repo.commit("sneaky")
        self.answer("here")
        rc, out = self.flow("next")
        self.assertEqual(rc, 1)
        self.assertTrue(out.startswith("STOP the architect changed tracked files, which a consultant must never do. "
                                       "a commit landed after it was handed out"), out)

    def test_the_consultant_gets_a_scout_with_its_own_lens(self):
        repo, env = self.setup()
        self.env["FLOW_SCOUTS"] = "on"
        self.flow("next")
        self.ask_in_ticket("designer", "Which empty state?")
        self.flow("next")
        rc, out = self.flow("scouts")
        self.assertEqual(rc, 0, out)
        self.assertEqual(len(out.splitlines()), 1)
        text = self.flow("scout-prompt", "1")[1]
        self.assertIn("ROLE: designer", text)
        self.assertIn("Which empty state?", text)


class Consult(unittest.TestCase):
    def test_consult_prompt_hands_the_planner_question_to_its_consultant(self):
        repo = Repo(tickets=())
        self.addCleanup(repo.close)
        for folder in ("agents", "guides"):
            shutil.copytree(str(ROOT / folder), str(repo.path(folder)))
        shutil.rmtree(str(repo.path("plans/f")))
        repo.commit("no plan yet")
        question = repo.dir.parent / (repo.dir.name + "-q.md")
        self.addCleanup(question.unlink, missing_ok=True)
        question.write_text("Which storage fits a 10k row export?\n", encoding="utf-8")
        rc, out = repo.flow("consult-prompt", "architect", str(question))
        self.assertEqual(rc, 0, out)
        self.assertIn("You are the architect", out)
        self.assertIn("comes from the brainstorm before the feature `f` is planned", out)
        self.assertIn("Which storage fits a 10k row export?", out)
        brief = repo.path(".feature-flow/state/brief-f.md")
        brief.parent.mkdir(parents=True, exist_ok=True)
        brief.write_text("Feature: f\nWhat: an export\nThe bar: `true` exits 0\n", encoding="utf-8")
        rc, out = repo.flow("consult-prompt", "architect", str(question))
        self.assertEqual(rc, 0, out)
        self.assertIn("comes from the planner of the feature `f`", out)
        self.assertIn("Which storage fits a 10k row export?", out)
        self.assertEqual(repo.flow("consult-prompt", "boss", str(question)),
                         (1, "STOP consult takes architect, designer or po, not boss"))


if __name__ == "__main__":
    unittest.main()
