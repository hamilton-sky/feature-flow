"""Drive a four-ticket plan through the conductor the way the skill does and see which gate ran.

The bar of plans/quick-gate: tickets 01 to 03 run Quick, the last ticket runs Test, and
FLOW_GATE_FULL=1 makes every ticket run Test.
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT, Repo

PYTHON = '"%s"' % sys.executable
SLUGS = ("01-a", "02-b", "03-c", "04-d")


def ticket(index):
    return ("# T%d\n\nType: task\nStatus: open\nBlocked by: %s\nTest first: no\n\nbody\n\n"
            "## Done when\n\n- x\n\n## Answer\n" % (index, "—" if index == 1 else "%02d" % (index - 1)))


class QuickGateDrive(unittest.TestCase):
    def drive(self, **env):
        """Drive to DONE; return what the Test and Quick commands logged, in order."""
        aux = tempfile.TemporaryDirectory()
        self.addCleanup(aux.cleanup)
        logger = Path(aux.name) / "logger.py"
        logfile = Path(aux.name) / "ran.log"
        reply = Path(aux.name) / "reply.txt"
        logger.write_text("import sys\nopen(sys.argv[2], 'a').write(sys.argv[1] + '\\n')\n", encoding="utf-8")
        reply.write_text("fine\nREVIEW: PASS\n", encoding="utf-8")
        repo = Repo(tickets=())
        self.addCleanup(repo.close)
        env["FLOW_TICKETS_PER_SESSION"] = "99"  # one session, so no handoff forces the full gate
        for folder in ("agents", "guides"):
            shutil.copytree(str(ROOT / folder), str(repo.path(folder)))
        repo.path("plans/f/commands.md").write_text(
            "# Commands: f\n\nSmoke: `%s -c \"pass\"`\nTest: `%s \"%s\" test \"%s\"`\nQuick: `%s \"%s\" quick \"%s\"`\n"
            % (PYTHON, PYTHON, logger, logfile, PYTHON, logger, logfile), encoding="utf-8")
        for index, slug in enumerate(SLUGS, 1):
            repo.path("plans/f/tasks/%s.md" % slug).write_text(ticket(index), encoding="utf-8")
        repo.commit("plan")
        rc, out = repo.flow("start", **env)
        self.assertEqual((rc, out.split()[0]), (0, "OK"), out)
        env["FLOW_SESSION"] = out.split()[1]

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
                continue
            self.assertEqual(word, "REVIEW", out)
            repo.flow("prompt", **env)
            self.assertEqual(repo.flow("verdict", str(reply), **env), (0, "OK"))
        self.assertEqual(built, len(SLUGS))
        return logfile.read_text(encoding="utf-8").split()

    def test_middle_tickets_run_quick_and_the_last_runs_test(self):
        self.assertEqual(self.drive(), ["quick", "quick", "quick", "test"])

    def test_gate_full_runs_test_for_every_ticket(self):
        self.assertEqual(self.drive(FLOW_GATE_FULL="1"), ["test", "test", "test", "test"])


if __name__ == "__main__":
    unittest.main()
