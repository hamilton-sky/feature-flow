"""Drive a five-ticket plan through the conductor the way the skill does, and count the reviews.

The bar of plans/small-tickets: a small ticket with a passing check block gets one REVIEW, and
Review: full, no check block, Type: convert, an over-limit diff and FLOW_SMALL_LINES=0 each get two.
"""

import re
import shutil
import sys
import unittest

from helpers import ROOT, Repo

PYTHON = '"%s"' % sys.executable
COMMANDS = ("# Commands: f\n\nSmoke: `%s -c \"pass\"`\nTest: `%s -c \"pass\"`\n") % (PYTHON, PYTHON)
CHECK = "```check\n$ %s -c \"print('fine')\"\nprints fine\n```\n\n" % PYTHON

# slug, header line, check block, lines the builder adds, reviews expected normally
TICKETS = (
    ("01-small", "", True, 3, 1),
    ("02-full", "Review: full", True, 3, 2),
    ("03-nocheck", "", False, 3, 2),
    ("04-convert", "", True, 3, 2),
    ("05-big", "", True, 61, 2),
)


def ticket(slug, header, check, index):
    kind = "convert" if slug.endswith("convert") else "task"
    lines = ["# T%d\n" % index, "Type: %s" % kind, "Status: open",
             "Blocked by: %s" % ("—" if index == 1 else "%02d" % (index - 1)), "Test first: no"]
    if header:
        lines.append(header)
    body = "\n".join(lines) + "\n\nbody\n\n## Done when\n\n- x\n\n"
    return body + (CHECK if check else "") + "## Answer\n"


class SmallDrive(unittest.TestCase):
    def drive(self, **env):
        repo = Repo(tickets=())
        env["FLOW_TICKETS_PER_SESSION"] = "99"  # one session drives all five tickets
        self.addCleanup(repo.close)
        for folder in ("agents", "guides"):
            shutil.copytree(str(ROOT / folder), str(repo.path(folder)))
        repo.path("plans/f/commands.md").write_text(COMMANDS, encoding="utf-8")
        for index, (slug, header, check, _, _) in enumerate(TICKETS, 1):
            repo.path("plans/f/tasks/%s.md" % slug).write_text(ticket(slug, header, check, index), encoding="utf-8")
        repo.commit("plan")
        rc, out = repo.flow("start", **env)
        self.assertEqual((rc, out.split()[0]), (0, "OK"), out)
        env["FLOW_SESSION"] = out.split()[1]
        reply = repo.dir.parent / (repo.dir.name + "-reply.txt")
        self.addCleanup(reply.unlink, missing_ok=True)
        reply.write_text("fine\nREVIEW: PASS\n", encoding="utf-8")

        seen = []
        while True:
            rc, out = repo.flow("next", **env)
            self.assertEqual(rc, 0, out)
            word = out.split()[0]
            if word == "DONE":
                return repo, seen
            if word == "BUILD":
                index = len(seen) + 1
                slug, _, _, lines, _ = TICKETS[index - 1]
                rel = "plans/f/tasks/%s.md" % slug
                repo.path("work-%s.txt" % slug).write_text("x\n" * lines, encoding="utf-8")
                repo.set_status(rel, "resolved")
                repo.commit("feat: %s" % slug)
                seen.append([])
                continue
            self.assertEqual(word, "REVIEW", out)
            prompt = repo.flow("prompt", **env)[1]
            seen[-1].append(re.search(r"\((single|spec|quality) pass\)", prompt).group(0)[1:-1])
            self.assertEqual(repo.flow("verdict", str(reply), **env), (0, "OK"))

    def test_each_kind_of_ticket_gets_its_reviews(self):
        repo, seen = self.drive()
        self.assertEqual(len(seen), len(TICKETS))
        self.assertEqual([len(one) for one in seen], [t[4] for t in TICKETS])
        self.assertEqual(seen[0], ["single pass"])
        for one in seen[1:]:
            self.assertEqual(one, ["spec pass", "quality pass"])
        self.assertEqual(repo.log().count("REVIEW-SMALL"), 1)

    def test_small_lines_zero_gives_two_reviews_for_every_ticket(self):
        repo, seen = self.drive(FLOW_SMALL_LINES="0")
        self.assertEqual(len(seen), len(TICKETS))
        for one in seen:
            self.assertEqual(one, ["spec pass", "quality pass"])
        self.assertNotIn("REVIEW-SMALL", repo.log())


if __name__ == "__main__":
    unittest.main()
