"""Drive a seven-ticket plan through the conductor the way the skill does, and count the reviews per level.

The bar of ticket levels: level 1, 2 and 3 tickets get one REVIEW whatever their size (since 0.23.0, level 3
too, with the hostile caller probe), `Review: full` gets two (spec then quality), a Sensitive path or
`Review: full` raises a ticket to level 3, a level 1 diff over
the small limits becomes level 2, and a ticket with no Level line keeps the 0.8.0 size rule.
"""

import re
import shutil
import sys
import unittest

from helpers import ROOT, Repo

PYTHON = '"%s"' % sys.executable
COMMANDS = ("# Commands: f\n\nSmoke: `%s -c \"pass\"`\nTest: `%s -c \"pass\"`\nSensitive: `src/auth/`\n"
            % (PYTHON, PYTHON))
CHECK = "```check\n$ %s -c \"print('fine')\"\nprints fine\n```\n\n" % PYTHON

# slug, header lines, file the builder writes, lines it adds, level the log records, reviews expected
TICKETS = (
    ("01-light", ["Level: 1"], "a.txt", 3, "1", ["single"]),
    ("02-light-big", ["Level: 1"], "b.txt", 61, "2", ["single"]),
    ("03-standard-big", ["Level: 2"], "c.txt", 200, "2", ["single"]),
    ("04-boundary", ["Level: 3"], "d.txt", 3, "3", ["single"]),
    ("05-sensitive", ["Level: 2"], "src/auth/e.txt", 3, "3", ["single"]),
    ("06-full", ["Level: 1", "Review: full"], "f.txt", 3, "3", ["spec", "quality"]),
    ("07-no-level", [], "g.txt", 3, None, ["single"]),
)


def ticket(index, header):
    lines = ["# T%d\n" % index, "Type: task", "Status: open",
             "Blocked by: %s" % ("—" if index == 1 else "%02d" % (index - 1)), "Test first: no"] + header
    return "\n".join(lines) + "\n\nbody\n\n## Done when\n\n- x\n\n" + CHECK + "## Answer\n"


class LevelsDrive(unittest.TestCase):
    def test_each_level_gets_its_reviews(self):
        repo = Repo(tickets=())
        self.addCleanup(repo.close)
        env = {"FLOW_TICKETS_PER_SESSION": "99"}
        for folder in ("agents", "guides"):
            shutil.copytree(str(ROOT / folder), str(repo.path(folder)))
        repo.path("plans/f/commands.md").write_text(COMMANDS, encoding="utf-8")
        for index, (slug, header, _, _, _, _) in enumerate(TICKETS, 1):
            repo.path("plans/f/tasks/%s.md" % slug).write_text(ticket(index, header), encoding="utf-8")
        repo.commit("plan")
        rc, out = repo.flow("start", **env)
        env["FLOW_SESSION"] = out.split()[1]
        reply = repo.dir.parent / (repo.dir.name + "-reply.txt")
        self.addCleanup(reply.unlink, missing_ok=True)
        reply.write_text("fine\nREVIEW: PASS\n", encoding="utf-8")

        seen, levels = [], []
        while True:
            rc, out = repo.flow("next", **env)
            self.assertEqual(rc, 0, out)
            word = out.split()[0]
            if word == "DONE":
                break
            if word == "BUILD":
                slug, _, name, lines, _, _ = TICKETS[len(seen)]
                repo.path(name).parent.mkdir(parents=True, exist_ok=True)
                repo.path(name).write_text("x\n" * lines, encoding="utf-8")
                repo.set_status("plans/f/tasks/%s.md" % slug, "resolved")
                repo.commit("feat: %s" % slug)
                seen.append([])
                continue
            self.assertEqual(word, "REVIEW", out)
            if not seen[-1]:
                levels.append(repo.state()["level"])
            prompt = repo.flow("prompt", **env)[1]
            seen[-1].append(re.search(r"\((single|spec|quality) pass\)", prompt).group(1))
            self.assertEqual(repo.flow("verdict", str(reply), **env), (0, "OK"))

        self.assertEqual(seen, [t[5] for t in TICKETS])
        self.assertEqual(levels, [t[4] or "0" for t in TICKETS])
        log = repo.log()
        for num, (_, _, _, _, level, _) in enumerate(TICKETS, 1):
            events = re.findall(r"^[^,]*,%02d,(LEVEL-[123])$" % num, log, re.MULTILINE)
            self.assertEqual(events, ["LEVEL-%s" % level] if level else [], num)
        self.assertEqual(log.count("REVIEW-SMALL"), 1)


if __name__ == "__main__":
    unittest.main()
