"""The same three-ticket plan driven to DONE in every combination of the options that change a run.

Where the conductor lives (the repo's own install, or `install --user` in the home), the review
(a small ticket's single pass, or `Review: full`), and the gate (a Quick line, or Test only). Each
combination must finish and show the reviews and gate commands that combination promises.
`install --private` is not a column: it only adds a line to .git/info/exclude and runs the same files.
"""

import itertools
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import helpers
from helpers import ROOT, Repo

sys.path.insert(0, str(ROOT))
from feature_flow import install  # the package under test, from this checkout

PYTHON = '"%s"' % sys.executable
SLUGS = ("01-a", "02-b", "03-c")
KEYS = ("HOME", "CLAUDE_HOME", "AGENTS_HOME", "FEATURE_FLOW_HOME")
CHECK = "```check\n$ %s -c \"print('fine')\"\nprints fine\n```\n\n" % PYTHON


def ticket(index, review):
    header = "Review: full\n" if review == "full" else ""
    return ("# T%d\n\nType: task\nStatus: open\nBlocked by: %s\nTest first: no\n%s\nbody\n\n"
            "## Done when\n\n- x\n\n%s## Answer\n" % (index, "—" if index == 1 else "%02d" % (index - 1), header, CHECK))


class ModeMatrix(unittest.TestCase):
    def drive(self, where, review, gate):
        """Drive to DONE; return (reviews per ticket, the Test/Quick commands that ran, the log)."""
        aux = tempfile.TemporaryDirectory()
        self.addCleanup(aux.cleanup)
        saved = dict((k, os.environ.get(k)) for k in KEYS)
        home = Path(aux.name) / "home"
        if where == "home":
            for key, rel in (("HOME", ""), ("CLAUDE_HOME", ".claude"), ("AGENTS_HOME", ".agents"),
                             ("FEATURE_FLOW_HOME", ".feature-flow")):
                os.environ[key] = str(home / rel) if rel else str(home)
            self.assertEqual(install.run(["--user"], ROOT, lambda t: None, lambda t: None), 0)
        self.addCleanup(self.restore, saved)
        logger = Path(aux.name) / "logger.py"
        logfile = Path(aux.name) / "ran.log"
        reply = Path(aux.name) / "reply.txt"
        logger.write_text("import sys\nopen(sys.argv[2], 'a').write(sys.argv[1] + '\\n')\n", encoding="utf-8")
        reply.write_text("fine\nREVIEW: PASS\n", encoding="utf-8")

        repo = Repo(tickets=(), local=(where == "repo"))
        self.addCleanup(repo.close)
        if where == "home":
            repo.script = str(home / ".feature-flow" / "scripts" / "flow.py")
        for folder in ("agents", "guides"):
            shutil.copytree(str(ROOT / folder), str(repo.path(folder)))
        quick = "Quick: `%s \"%s\" quick \"%s\"`\n" % (PYTHON, logger, logfile) if gate == "quick" else ""
        repo.path("plans/f/commands.md").write_text(
            "# Commands: f\n\nSmoke: `%s -c \"pass\"`\nTest: `%s \"%s\" test \"%s\"`\n%s"
            % (PYTHON, PYTHON, logger, logfile, quick), encoding="utf-8")
        for index, slug in enumerate(SLUGS, 1):
            repo.path("plans/f/tasks/%s.md" % slug).write_text(ticket(index, review), encoding="utf-8")
        repo.commit("plan")

        env = {"FLOW_TICKETS_PER_SESSION": "99"}
        rc, out = repo.flow("start", **env)
        self.assertEqual((rc, out.split()[0]), (0, "OK"), out)
        env["FLOW_SESSION"] = out.split()[1]
        reviews = []
        built = 0
        while True:
            rc, out = repo.flow("next", **env)
            self.assertEqual(rc, 0, out)
            word = out.split()[0]
            if word == "DONE":
                break
            if word == "BUILD":
                repo.path("work-%d.txt" % built).write_text("x\n", encoding="utf-8")
                repo.set_status("plans/f/tasks/%s.md" % SLUGS[built], "resolved")
                repo.commit("feat: %s" % SLUGS[built])
                built += 1
                reviews.append(0)
                continue
            self.assertEqual(word, "REVIEW", out)
            repo.flow("prompt", **env)
            self.assertEqual(repo.flow("verdict", str(reply), **env), (0, "OK"))
            reviews[-1] += 1
        self.assertEqual(built, len(SLUGS))
        return reviews, logfile.read_text(encoding="utf-8").split(), repo.log()

    @staticmethod
    def restore(saved):
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_every_combination_finishes_with_the_promised_reviews_and_gates(self):
        for where, review, gate in itertools.product(("repo", "home"), ("auto", "full"), ("quick", "test")):
            with self.subTest(where=where, review=review, gate=gate):
                reviews, ran, log = self.drive(where, review, gate)
                self.assertEqual(reviews, [1, 1, 1] if review == "auto" else [2, 2, 2])
                self.assertEqual(ran, ["quick", "quick", "test"] if gate == "quick" else ["test"] * 3)
                self.assertEqual(log.count("REVIEW-SMALL"), 3 if review == "auto" else 0)
                self.assertIn("DONE", log)


if __name__ == "__main__":
    unittest.main()
