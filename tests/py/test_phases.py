"""The phases of a ticket and of the run are classes found through one registry, and a table says which phase
may follow which. Driven in process on throwaway repos: every phase the state file takes, and every phase a
hand-out sets, is one the table allows after the one before."""

import contextlib
import io
import os
import subprocess
import sys
import unittest
from unittest import mock

import helpers
from helpers import Repo

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import cli  # the package under test, from this checkout
from feature_flow.conductor import NoPhase
from feature_flow.conductor.phases import REGISTRY, TRANSITIONS
from feature_flow.conductor.phases.base import Outcome, Phase
from feature_flow.conductor.store import RunState

PYTHON = '"%s"' % sys.executable
CHECK = "```check\n$ %s -c \"print('fine')\"\nprints fine\n```\n\n" % PYTHON
WORDS = ("build", "review", "ask", "test", "final")
SLOTS = ["phase"] + ["L%d.phase" % k for k in range(1, 5)]
T1, T2 = "plans/f/tasks/01-a.md", "plans/f/tasks/02-b.md"
ACCEPT = "plans/f/acceptance/check.py"
PASSES_WHEN_BUILT = ("import sys\ntry:\n    text = open('feature.txt').read().strip()\nexcept OSError:\n"
                     "    text = ''\nsys.exit(0 if text == 'done' else 1)\n")


def ticket(title, blocked, header=()):
    lines = ["# %s\n" % title, "Type: task", "Status: open", "Blocked by: %s" % blocked, "Test first: no"]
    return "\n".join(lines + list(header)) + "\n\nbody\n\n## Done when\n\n- x\n\n" + CHECK + "## Answer\n"


def reach(start, table):
    """Every phase a walk of table reaches from start, start included."""
    seen, todo = {start}, [start]
    while todo:
        for nxt in table.get(todo.pop(), ()):
            if nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    return seen


class Registry(unittest.TestCase):
    def test_every_registry_word_has_a_class_and_a_row_in_the_table(self):
        self.assertEqual(sorted(REGISTRY), sorted(WORDS))
        for word, cls in REGISTRY.items():
            self.assertTrue(isinstance(cls, type) and issubclass(cls, Phase), word)
            self.assertEqual(cls.name, word)
            self.assertIn(word, TRANSITIONS)
            for method in ("hand_out", "judge", "prompt", "record", "scout_questions", "key"):
                self.assertTrue(callable(getattr(cls, method, None)), "%s has no %s" % (word, method))

    def test_only_the_tester_and_the_feature_review_are_run_wide(self):
        self.assertEqual(sorted(w for w, cls in REGISTRY.items() if not cls.lane_scoped), ["final", "test"])

    def test_the_table_names_only_its_own_rows(self):
        self.assertIn("", TRANSITIONS)
        for before, after in TRANSITIONS.items():
            for word in after:
                self.assertIn(word, TRANSITIONS, "%r -> %r" % (before, word))

    def test_a_walk_reaches_every_phase_from_between_tickets_and_gets_back_from_each(self):
        self.assertEqual(reach("", TRANSITIONS), set(TRANSITIONS))
        for word in TRANSITIONS:
            self.assertIn("", reach(word, TRANSITIONS), "no way back to between tickets from %r" % word)

    def test_record_raises_no_phase_by_default_and_outcome_has_line_and_passed(self):
        class Handle:
            feature = "f"

        with self.assertRaises(NoPhase):
            Phase.record(Handle(), "reply.txt")
        with self.assertRaises(NoPhase):
            REGISTRY["build"].record(Handle(), "reply.txt")
        outcome = Outcome("BUILD x", True)
        self.assertEqual((outcome.line, outcome.passed), ("BUILD x", True))


class Session:
    """The conductor run in process on a throwaway repo, recording every phase the state file takes (per slot:
    the run's and each lane's) and every hand-out (the phase before it and after it)."""

    def __init__(self, test, tickets, commands, **env):
        self.test = test
        self.repo = repo = Repo(tickets=())
        test.addCleanup(repo.close)
        repo.path("plans/f/commands.md").write_text("# Commands: f\n\n" + commands, encoding="utf-8")
        for rel, text in tickets:
            repo.path(rel).write_text(text, encoding="utf-8")
        repo.commit("plan")
        self.reply = repo.dir.parent / (repo.dir.name + "-reply.txt")
        test.addCleanup(self.reply.unlink, missing_ok=True)
        self.seen = {slot: "" for slot in SLOTS}
        self.moves = []  # (slot, before, after) each time a saved phase changed
        self.handed = []  # (word, phase before, phase after) for each hand-out
        self.env = dict({"FLOW_TICKETS_PER_SESSION": "99", "FLOW_SCOUTS": "off"}, **env)
        rc, out = self.call("start")
        test.assertEqual(rc, 0, out)
        self.env["FLOW_SESSION"] = out.split()[1]

    def saved(self, real):
        def save(run):
            for slot in SLOTS:
                now = str(run.get(slot, "") or "")
                if now != self.seen[slot]:
                    self.moves.append((slot, self.seen[slot], now))
                    self.seen[slot] = now
            return real(run)
        return save

    def wrap(self, word, real):
        def hand_out(cls, ws, *args, **kw):
            before = ws.get("phase")
            line = real(ws, *args, **kw)
            self.handed.append((word, before, ws.get("phase")))
            return line
        return classmethod(hand_out)

    def call(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith("FLOW_")}
        env.update(self.env, FLOW_TRUSTED="1")
        out = io.StringIO()
        here = os.getcwd()
        os.chdir(str(self.repo.dir))
        try:
            with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(out), \
                    contextlib.redirect_stderr(io.StringIO()), contextlib.ExitStack() as stack:
                stack.enter_context(mock.patch.object(RunState, "save", self.saved(RunState.save)))
                for word, cls in REGISTRY.items():
                    stack.enter_context(mock.patch.object(cls, "hand_out", self.wrap(word, cls.hand_out)))
                rc = cli.main(["f"] + list(args), scripts=self.repo.path("scripts"))
        finally:
            os.chdir(here)
        return rc, out.getvalue().strip()

    def next(self, *lane):
        rc, out = self.call("next", *lane)
        self.test.assertEqual(rc, 0, out)
        return out

    def verdict(self, text, *lane):
        self.reply.write_text(text, encoding="utf-8")
        rc, out = self.call("verdict", str(self.reply), *lane)
        self.test.assertEqual((rc, out), (0, "OK"))

    def check(self, words):
        """Every saved phase and every hand-out followed what the table allows, and words were handed out."""
        for slot, before, after in self.moves:
            self.test.assertIn(after, TRANSITIONS.get(before, ()), "%s went %r -> %r" % (slot, before, after))
        for word, before, after in self.handed:
            self.test.assertEqual(after, word)
            self.test.assertIn(after, TRANSITIONS.get(before, ()), "the %s hand-out followed %r" % (word, before))
        self.test.assertEqual(sorted({w for w, _, _ in self.handed}), sorted(words))


class Walks(unittest.TestCase):
    def test_a_serial_run_with_questions_and_a_send_back(self):
        s = Session(self, [(T1, ticket("A", "—", ["Level: 2"])), (T2, ticket("B", "01", ["Level: 2"]))],
                    "Smoke: `%s -c \"pass\"`\nTest: `%s -c \"pass\"`\n" % (PYTHON, PYTHON))
        repo = s.repo
        self.assertTrue(s.next().startswith("BUILD %s 01 " % T1))
        with open(str(repo.path(T1)), "a", encoding="utf-8") as handle:
            handle.write("\n## Ask: architect\n\nWhere does it go?\n")
        repo.commit("ask")
        self.assertTrue(s.next().startswith("ASK architect %s 01 " % T1))
        s.verdict("## Answer\n\nIn a new module.\n\nANSWER: GIVEN\n")
        self.assertTrue(s.next().startswith("BUILD %s 01 " % T1))
        repo.resolve(T1)
        self.assertTrue(s.next().startswith("REVIEW %s 01 " % T1))
        s.verdict("- [major] it is wrong\n\nREVIEW: FAIL\n")
        self.assertTrue(s.next().startswith("BUILD %s 01 " % T1))
        repo.path("work-01-a.txt").write_text("fixed\n", encoding="utf-8")
        repo.resolve(T1)
        self.assertTrue(s.next().startswith("REVIEW %s 01 " % T1))
        s.verdict("fine\n\nREVIEW: PASS\n")
        self.assertTrue(s.next().startswith("REVIEW %s 01 " % T1))  # the quality pass
        s.verdict("## Question\n\nCSV or JSON?\n\nREVIEW: ASK po\n")
        self.assertTrue(s.next().startswith("ASK po %s 01 " % T1))
        s.verdict("## Answer\n\nCSV.\n\nANSWER: GIVEN\n")
        self.assertTrue(s.next().startswith("REVIEW %s 01 " % T1))
        s.verdict("fine\n\nREVIEW: PASS\n")
        self.assertTrue(s.next().startswith("BUILD %s 02 " % T2))
        repo.resolve(T2)
        self.assertTrue(s.next().startswith("REVIEW %s 02 " % T2))
        s.verdict("fine\n\nREVIEW: PASS\n")
        self.assertTrue(s.next().startswith("REVIEW %s 02 " % T2))
        s.verdict("fine\n\nREVIEW: PASS\n")
        self.assertTrue(s.next().startswith("DONE f is complete"))
        s.check(["build", "review", "ask"])

    def test_a_fast_run_with_a_tester_and_the_feature_review(self):
        s = Session(self, [(T1, ticket("A", "—", ["Level: 2"]))],
                    "Smoke: `%s -c \"pass\"`\nTest: `%s -c \"pass\"`\nAcceptance: `%s %s`\n"
                    % (PYTHON, PYTHON, PYTHON, ACCEPT), FLOW_FAST="1")
        repo = s.repo
        self.assertTrue(s.next().startswith("TEST plans/f "))
        repo.path(ACCEPT).parent.mkdir(parents=True)
        repo.path(ACCEPT).write_text(PASSES_WHEN_BUILT, encoding="utf-8")
        repo.commit("test(f): acceptance tests")
        self.assertTrue(s.next().startswith("BUILD %s 01 " % T1))
        repo.path("feature.txt").write_text("done\n", encoding="utf-8")
        repo.resolve(T1)
        self.assertTrue(s.next().startswith("REVIEW plans/f all "))
        s.verdict("fine\n\nREVIEW: PASS\n")
        self.assertTrue(s.next().startswith("DONE f is complete"))
        s.check(["test", "build", "final"])

    def test_a_lane_ticket_waits_for_its_merge(self):
        s = Session(self, [(T1, ticket("A", "—", ["Level: 2", "Touches: a/"]))],
                    "Smoke: `%s -c \"pass\"`\nTest: `%s -c \"pass\"`\n" % (PYTHON, PYTHON), FLOW_LANES="2")
        self.assertTrue(s.next().startswith("BUILD %s 01 " % T1))
        lane = s.repo.path(".feature-flow/lanes/f/lane-1")
        (lane / "a").mkdir()
        (lane / "a" / "x.txt").write_text("x\n", encoding="utf-8")
        text = (lane / T1).read_text(encoding="utf-8").replace("Status: open", "Status: resolved")
        (lane / T1).write_text(text, encoding="utf-8")
        for args in (("add", "-A"), ("commit", "-qm", "feat: work")):
            subprocess.run(["git"] + list(args), cwd=str(lane), check=True, stdout=subprocess.PIPE)
        self.assertTrue(s.next("1").startswith("REVIEW %s 01 " % T1))
        s.verdict("fine\n\nREVIEW: PASS\n", "1")
        self.assertTrue(s.next("1").startswith("REVIEW %s 01 " % T1))
        s.verdict("fine\n\nREVIEW: PASS\n", "1")
        self.assertTrue(s.next("1").startswith("DONE f is complete"))
        self.assertIn(("L1.phase", "review", "merge"), s.moves)
        self.assertIn(("L1.phase", "merge", ""), s.moves)
        s.check(["build", "review"])


if __name__ == "__main__":
    unittest.main()
