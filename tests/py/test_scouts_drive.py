"""Drive the scouts the way the skill does: `scouts` lists the helpers due before a phase, `scout-prompt` gives
each one's prompt, the session saves each reply where the line says, and the phase's `prompt` carries them.

The bar: none at level 1, one before a build below level 3, two before a level 3 build and one before its spec
review, one before the feature review, two (code and web) before planning. Replies never reach another
phase's prompt, and FLOW_SCOUTS=off turns them all off.
"""

import os
import re
import shutil
import subprocess
import sys
import unittest

from helpers import ROOT, Repo
from test_lanes_drive import Drive

PYTHON = '"%s"' % sys.executable
CHECK = "```check\n$ %s -c \"print('fine')\"\nprints fine\n```\n\n" % PYTHON
SCOUT = re.compile(r"^SCOUT (\d) (flow-scout|flow-web) (.+)$")


def ticket(index, header):
    lines = ["# T%d\n" % index, "Type: task", "Status: open",
             "Blocked by: %s" % ("—" if index == 1 else "%02d" % (index - 1)), "Test first: no"] + header
    return "\n".join(lines) + "\n\nbody\n\n## Done when\n\n- x\n\n" + CHECK + "## Answer\n"


class ScoutsDrive(unittest.TestCase):
    def setup(self, headers, **env):
        repo = Repo(tickets=())
        self.addCleanup(repo.close)
        env = dict({"FLOW_TICKETS_PER_SESSION": "99"}, **env)
        for folder in ("agents", "guides"):
            shutil.copytree(str(ROOT / folder), str(repo.path(folder)))
        repo.path("plans/f/commands.md").write_text(
            "# Commands: f\n\nSmoke: `%s -c \"pass\"`\nTest: `%s -c \"pass\"`\n" % (PYTHON, PYTHON), encoding="utf-8")
        for index, header in enumerate(headers, 1):
            repo.path("plans/f/tasks/%02d-t.md" % index).write_text(ticket(index, header), encoding="utf-8")
        repo.commit("plan")
        rc, out = repo.flow("start", **env)
        self.assertEqual(rc, 0, out)
        env["FLOW_SESSION"] = out.split()[1]
        env.pop("FLOW_FAST", None)
        reply = repo.dir.parent / (repo.dir.name + "-reply.txt")
        self.addCleanup(reply.unlink, missing_ok=True)
        return repo, env, reply

    def scout(self, repo, env, *lane):
        """Run scouts and every scout-prompt, save a reply naming each, and return [(agent, prompt)]."""
        rc, out = repo.flow("scouts", *lane, **env)
        self.assertEqual(rc, 0, out)
        if out == "NONE":
            return []
        found = []
        for line in out.splitlines():
            k, agent, path = SCOUT.match(line).groups()
            rc, text = repo.flow("scout-prompt", k, *lane, **env)
            self.assertEqual(rc, 0, text)
            found.append((agent, text))
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("## Findings\n- scout %s saw helpers.py\n" % k)
        return found

    def drive(self, repo, env, reply):
        """To DONE, scouting before every phase. Returns [(word, num, pass or "", [(agent, role)], prompt)]."""
        seen = []
        while True:
            rc, out = repo.flow("next", **env)
            self.assertEqual(rc, 0, out)
            fields = out.split()
            if fields[0] == "DONE":
                return seen
            found = self.scout(repo, env)
            prompt = repo.flow("prompt", **env)[1]
            roles = [(agent, re.search(r"^ROLE: (\w+)$", text, re.MULTILINE).group(1)) for agent, text in found]
            kind = re.search(r"\((single|spec|quality|feature) pass\)", prompt)
            seen.append((fields[0], fields[2], kind.group(1) if kind else "", roles, prompt))
            if fields[0] == "BUILD":
                repo.resolve(fields[1])
            else:
                reply.write_text("fine\nREVIEW: PASS\n", encoding="utf-8")
                self.assertEqual(repo.flow("verdict", str(reply), **env), (0, "OK"))

    def test_scouts_follow_the_level_and_their_findings_reach_only_their_phase(self):
        repo, env, reply = self.setup((["Level: 1"], ["Level: 2", "Touches: work-02-t.txt"], ["Level: 3"]))
        seen = self.drive(repo, env, reply)
        self.assertEqual([(w, n, p, r) for w, n, p, r, _ in seen], [
            ("BUILD", "01", "", []),
            ("REVIEW", "01", "single", []),
            ("BUILD", "02", "", [("flow-scout", "builder")]),
            ("REVIEW", "02", "single", []),
            ("BUILD", "03", "", [("flow-scout", "builder"), ("flow-scout", "builder")]),
            ("REVIEW", "03", "single", [("flow-scout", "reviewer")]),
        ])
        for word, num, _, roles, prompt in seen:
            if roles:
                self.assertIn("## Scout findings (unverified)", prompt, (word, num))
                self.assertIn("scout %d saw helpers.py" % len(roles), prompt)
            else:
                self.assertNotIn("Scout findings", prompt, (word, num))  # never a reply saved for another phase
        self.assertEqual(len(re.findall(r",SCOUTS-\d$", repo.log(), re.MULTILINE)), 3)

    def test_the_scout_prompt_carries_the_role_lens_the_ticket_and_its_touches(self):
        repo, env, _ = self.setup((["Level: 2", "Touches: src/a.py, tests/"],))
        line = repo.flow("next", **env)[1]
        base = line.split()[3]
        found = self.scout(repo, env)
        self.assertEqual(len(found), 1)
        text = found[0][1]
        self.assertIn("You are a scout.", text)
        self.assertIn("ROLE: builder", text)
        self.assertIn("`git show %s:plans/f/tasks/01-t.md`" % base, text)
        self.assertIn("its `Touches:` line names src/a.py, tests/", text)
        self.assertNotIn("model: haiku", text)  # the role's body, not its frontmatter

    def test_scout_prompt_needs_scouts_first_and_a_real_number(self):
        repo, env, _ = self.setup((["Level: 2"],))
        repo.flow("next", **env)
        self.assertEqual(repo.flow("scout-prompt", "1", **env)[0], 2)
        self.assertEqual(repo.flow("scouts", **env)[0], 0)
        self.assertEqual(repo.flow("scout-prompt", "2", **env), (1, "STOP no scout 2: there are 1"))
        rc, out = repo.flow("scouts", FLOW_TRUSTED="0", FLOW_SESSION=env["FLOW_SESSION"])
        self.assertIn("flow-trust.py", out)

    def test_flow_scouts_off_lists_none(self):
        repo, env, reply = self.setup((["Level: 3"],))
        env["FLOW_SCOUTS"] = "off"
        seen = self.drive(repo, env, reply)
        self.assertEqual([r for _, _, _, r, _ in seen], [[], []])

    def test_the_feature_review_gets_a_reviewer_scout(self):
        repo, env, reply = self.setup((["Level: 1"], ["Level: 2"]), FLOW_FAST="1")
        seen = self.drive(repo, env, reply)
        final = [s for s in seen if s[1] == "all"]
        self.assertEqual([(w, p, r) for w, _, p, r, _ in final], [("REVIEW", "feature", [("flow-scout", "reviewer")])])
        self.assertIn("## Scout findings (unverified)", final[0][4])


class PlanScouts(unittest.TestCase):
    def test_planning_gets_a_code_and_a_web_scout_for_this_brief_only(self):
        repo = Repo(tickets=())
        self.addCleanup(repo.close)
        for folder in ("agents", "guides"):
            shutil.copytree(str(ROOT / folder), str(repo.path(folder)))
        repo.commit("guides")
        brief = repo.dir.parent / (repo.dir.name + "-brief.md")
        self.addCleanup(brief.unlink, missing_ok=True)
        brief.write_text("What: export CSV with the csvkit library\nThe bar: `make test` passes\n", encoding="utf-8")
        def flow(*args):
            full = {k: v for k, v in os.environ.items() if not k.startswith("FLOW_")}
            done = subprocess.run([sys.executable, repo.script, "x"] + list(args), cwd=str(repo.dir), env=full,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            return done.returncode, done.stdout.strip()

        rc, out = flow("plan-scouts", str(brief))
        self.assertEqual(rc, 0, out)
        lines = [SCOUT.match(l).groups() for l in out.splitlines()]
        self.assertEqual([a for _, a, _ in lines], ["flow-scout", "flow-web"])
        rc, web = flow("plan-scout-prompt", "2")
        self.assertEqual(rc, 0, web)
        self.assertIn("ROLE: planner", web)
        self.assertIn("You are a web scout for the planner.", web)
        self.assertIn("export CSV with the csvkit library", web)
        for k, _, path in lines:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("## Findings\n- plan scout %s\n" % k)
        rc, prompt = flow("plan-prompt", str(brief))
        self.assertEqual(rc, 0, prompt)
        self.assertIn("## Scout findings (unverified)", prompt)
        self.assertIn("plan scout 2", prompt)
        brief.write_text("What: something else\nThe bar: `make test` passes\n", encoding="utf-8")
        rc, prompt = flow("plan-prompt", str(brief))
        self.assertNotIn("Scout findings", prompt)  # the replies were for the other brief
        self.assertEqual(flow("plan-scout-prompt", "1")[0], 2)  # and so were the scouts listed


class LaneScouts(unittest.TestCase):
    def test_a_lane_scout_works_in_its_lane_and_saves_to_its_own_file(self):
        repo = Repo(tickets=())
        self.addCleanup(repo.close)
        drive = Drive(self, repo, (("01-a", "A", "—", ["Level: 2", "Touches: a/"]),
                                   ("02-b", "B", "—", ["Level: 2", "Touches: b/"])))
        self.assertEqual(drive.fill(), "WAIT 1,2")
        for lane in ("1", "2"):
            rc, out = repo.flow("scouts", lane, **drive.env)
            self.assertEqual(rc, 0, out)
            k, agent, path = SCOUT.match(out).groups()
            self.assertIn("scout-f-L%s-1.txt" % lane, path)
            text = repo.flow("scout-prompt", k, lane, **drive.env)[1]
            self.assertRegex(text, r"Work in the folder `[^`]*lane-%s`" % lane)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("lane %s finding\n" % lane)
        prompt = repo.flow("prompt", "2", **drive.env)[1]
        self.assertIn("lane 2 finding", prompt)
        self.assertNotIn("lane 1 finding", prompt)


if __name__ == "__main__":
    unittest.main()
