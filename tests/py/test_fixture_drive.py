"""Drive a two-ticket plan through the conductor, the same way on Linux, macOS and Windows.

The bar of plans/interactive-flow-python: `python scripts/flow.py f start`, then `next` with the
token, hands out BUILD; once the ticket is resolved and committed, `next` hands out REVIEW.
The plan's commands use the interpreter running this test, so they work wherever the suite runs.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TICKET = "plans/f/tasks/01-a.md"

TICKET_TEXT = ("# %s\n\nType: task\nStatus: %s\nBlocked by: %s\nTest first: no\n\n\nbody\n\n"
               "## Done when\n\n- x\n\n## Answer\n")

# Double quotes, which both bash -c and cmd.exe read; shlex.quote's single quotes break cmd.exe.
PYTHON = '"%s"' % sys.executable
COMMANDS = ("# Commands: f\n\n"
            "Build: `%s -c \"pass\"`\n"
            "Smoke: `%s -c \"pass\"`\n"
            "Test: `%s -c \"pass\"`\n") % ((PYTHON,) * 3)


class FixtureDrive(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        shutil.copytree(str(ROOT / "scripts"), str(self.dir / "scripts"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(str(ROOT / "feature_flow"), str(self.dir / "feature_flow"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        plan = self.dir / "plans" / "f"
        (plan / "tasks").mkdir(parents=True)
        (plan / "tasks" / "01-a.md").write_text(TICKET_TEXT % ("A", "open", "—"), encoding="utf-8")
        (plan / "tasks" / "02-b.md").write_text(TICKET_TEXT % ("B", "open", "01"), encoding="utf-8")
        (plan / "map.md").write_text("# Map: f\n\n## Decisions so far\n\n<One line per resolved ticket.>\n", encoding="utf-8")
        (plan / "learnings.md").write_text("# Learnings: f\n\n- (NN) <what you found>\n", encoding="utf-8")
        (plan / "commands.md").write_text(COMMANDS, encoding="utf-8")
        (plan / "spec.md").write_text("# Spec\n", encoding="utf-8")
        self.git("init", "-q")
        self.git("config", "user.email", "t@t")
        self.git("config", "user.name", "t")
        self.git("config", "core.autocrlf", "false")
        self.git("add", "-A")
        self.git("commit", "-qm", "init")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.run(["git"] + list(args), cwd=str(self.dir), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True, check=True).stdout.strip()

    def flow(self, *args, **env):
        full = {k: v for k, v in os.environ.items() if not k.startswith("FLOW_")}
        full["FLOW_TRUSTED"] = "1"
        full.update(env)
        result = subprocess.run([sys.executable, "scripts/flow.py", "f"] + list(args), cwd=str(self.dir),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                                env=full)
        return result.returncode, result.stdout.strip()

    def test_start_then_next_reaches_review(self):
        rc, out = self.flow("start")
        self.assertEqual(rc, 0, out)
        words = out.split()
        self.assertEqual(words[0], "OK", out)
        token = words[1]

        sha = self.git("rev-parse", "HEAD")
        rc, out = self.flow("next", FLOW_SESSION=token)
        self.assertEqual((rc, out), (0, "BUILD %s 01 %s" % (TICKET, sha)))

        path = self.dir / TICKET
        path.write_text(path.read_text(encoding="utf-8").replace("Status: open", "Status: resolved"),
                        encoding="utf-8")
        (self.dir / "work-01-a.txt").write_text("work\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-qm", "feat: 01")

        rc, out = self.flow("next", FLOW_SESSION=token)
        self.assertEqual((rc, out), (0, "REVIEW %s 01 %s" % (TICKET, sha)))
        self.assertEqual(self.git("status", "--porcelain"), "")


class PlanDrive(unittest.TestCase):
    """The bar of plans/feature-planner: a brief becomes a committed plan through the conductor, and
    the session then starts building it. The test writes the draft where the planner would."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        for folder in ("scripts", "feature_flow", "guides", "agents"):
            dest = self.dir / folder if folder in ("scripts", "feature_flow") else self.dir / ".feature-flow" / folder
            shutil.copytree(str(ROOT / folder), str(dest), ignore=shutil.ignore_patterns("__pycache__"))
        for args in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"],
                     ["config", "core.autocrlf", "false"], ["add", "-A"], ["commit", "-qm", "init"]):
            self.git(*args)

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.run(["git"] + list(args), cwd=str(self.dir), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True, check=True).stdout.strip()

    def flow(self, *args, **env):
        full = {k: v for k, v in os.environ.items() if not k.startswith("FLOW_")}
        full["FLOW_TRUSTED"] = "1"
        full.update(env)
        result = subprocess.run([sys.executable, "scripts/flow.py", "csv"] + list(args), cwd=str(self.dir),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, env=full,
                                encoding="utf-8")
        return result.returncode, result.stdout.strip()

    def test_a_brief_becomes_a_plan_that_starts(self):
        self.assertEqual(self.flow("start"), (0, "PLAN"))
        brief = self.dir / ".feature-flow" / "state" / "brief-csv.md"
        brief.write_text("Feature: csv\nWhat: export as CSV\nThe bar: `python -c pass` exits 0\n", encoding="utf-8")
        rc, out = self.flow("plan-prompt", ".feature-flow/state/brief-csv.md")
        self.assertEqual(rc, 0, out)
        self.assertTrue(out.startswith("You are the planner."))

        draft = self.dir / ".feature-flow" / "state" / "draft" / "csv"
        (draft / "tasks" / "01-a.md").write_text(TICKET_TEXT % ("A", "open", "—"), encoding="utf-8")
        (draft / "tasks" / "02-b.md").write_text(TICKET_TEXT % ("B", "open", "01"), encoding="utf-8")
        for name, text in (("spec.md", "# Spec\n"), ("map.md", "# Map: csv\n"), ("learnings.md", "# Learnings\n"),
                           ("commands.md", COMMANDS)):
            (draft / name).write_text(text, encoding="utf-8")
        rc, out = self.flow("plan-review-prompt")
        self.assertEqual(rc, 0, out)
        self.assertTrue(out.startswith("You are the plan reviewer"))
        self.assertEqual(self.git("status", "--porcelain"), "")

        self.assertEqual(self.flow("plan-accept"), (0, "OK plans/csv"))
        self.git("add", "plans/csv")
        self.git("commit", "-qm", "docs(csv): plan")
        rc, out = self.flow("start")
        self.assertEqual(rc, 0, out)
        self.assertEqual(out.split()[0], "OK", out)
        rc, out = self.flow("next", FLOW_SESSION=out.split()[1])
        self.assertTrue(out.startswith("BUILD plans/csv/tasks/01-a.md 01 "), out)


if __name__ == "__main__":
    unittest.main()
