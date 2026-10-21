"""Drive plans through the conductor with FLOW_LANES=2, the way the skill does: tickets whose Touches do not
overlap are built side by side in their own worktrees, merged one at a time, and the branches and lanes are
gone at the end. A merge that breaks the gate or conflicts rebuilds the ticket once; a level 3 ticket whose
base went stale is reviewed again before it merges.
"""

import re
import shutil
import subprocess
import sys
import unittest

from helpers import ROOT, Repo

PYTHON = '"%s"' % sys.executable
CHECK = "```check\n$ %s -c \"print('fine')\"\nprints fine\n```\n\n" % PYTHON


def ticket(title, blocked, header):
    lines = ["# %s\n" % title, "Type: task", "Status: open", "Blocked by: %s" % blocked, "Test first: no"] + header
    return "\n".join(lines) + "\n\nbody\n\n## Done when\n\n- x\n\n" + CHECK + "## Answer\n"


def git(cwd, *args):
    return subprocess.run(["git"] + list(args), cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True, check=True).stdout.strip()


class Drive:
    """A session: it keeps the builds and reviews it handed to subagents and finishes them in the order the
    test asks for, calling the conductor the way the skill says."""

    def __init__(self, test, repo, tickets, test_command='-c "pass"', lanes="2"):
        self.test, self.repo = test, repo
        for folder in ("agents", "guides"):
            shutil.copytree(str(ROOT / folder), str(repo.path(folder)))
        repo.path("plans/f/commands.md").write_text(
            "# Commands: f\n\nSetup: `%s -c \"pass\"`\nSmoke: `%s -c \"pass\"`\nTest: `%s %s`\n"
            % (PYTHON, PYTHON, PYTHON, test_command), encoding="utf-8")
        for slug, title, blocked, header in tickets:
            repo.path("plans/f/tasks/%s.md" % slug).write_text(ticket(title, blocked, header), encoding="utf-8")
        repo.commit("plan")
        self.env = {"FLOW_TICKETS_PER_SESSION": "99", "FLOW_LANES": lanes}
        rc, out = repo.flow("start", **self.env)
        test.assertEqual(rc, 0, out)
        self.env["FLOW_SESSION"] = out.split()[1]
        self.reply = repo.dir.parent / (repo.dir.name + "-reply.txt")
        test.addCleanup(self.reply.unlink, missing_ok=True)
        self.pending = []  # [kind, lane, ticket path, num]
        self.lines = []

    def call(self, *args):
        rc, out = self.repo.flow(*args, **self.env)
        self.lines.append(out)
        return rc, out

    def fill(self):
        """`next` without a lane until it says WAIT, DONE or STOP, keeping each BUILD and REVIEW."""
        rc, out = self.call("next")
        return self.take(rc, out)

    def take(self, rc, out):
        while True:
            self.test.assertEqual(rc, 0, out)
            word = out.split()[0]
            if word in ("BUILD", "REVIEW"):
                fields = out.split()
                self.pending.append([word, fields[4], fields[1], fields[2]])
                rc, out = self.call("next")
                continue
            return out

    def lane_dir(self, lane):
        return self.repo.path(".feature-flow/lanes/f/lane-%s" % lane)

    def find(self, word, num):
        for item in self.pending:
            if item[0] == word and item[3] == num:
                return item
        self.test.fail("no pending %s of %s in %s" % (word, num, self.pending))

    def build(self, num, files, append=None):
        """The builder of num writes files (path: text) in its lane, resolves the ticket and commits."""
        item = self.find("BUILD", num)
        self.pending.remove(item)
        where = self.lane_dir(item[1])
        for rel, text in files.items():
            (where / rel).parent.mkdir(parents=True, exist_ok=True)
            (where / rel).write_text(text, encoding="utf-8")
        if append:
            with open(str(where / "plans/f/learnings.md"), "a", encoding="utf-8") as handle:
                handle.write(append + "\n")
        path = where / item[2]
        path.write_text(re.sub(r"(?m)^Status: .*$", "Status: resolved", path.read_text(encoding="utf-8"), count=1),
                        encoding="utf-8")
        git(where, "add", "-A")
        git(where, "commit", "-qm", "feat: %s" % num)
        rc, out = self.call("next", item[1])
        return self.take(rc, out)

    def review(self, num, verdict="PASS"):
        item = self.find("REVIEW", num)
        self.pending.remove(item)
        self.reply.write_text("fine\nREVIEW: %s\n" % verdict, encoding="utf-8")
        self.test.assertEqual(self.call("verdict", str(self.reply), item[1])[0], 0)
        rc, out = self.call("next", item[1])
        return self.take(rc, out)


class LanesDrive(unittest.TestCase):
    def repo(self):
        repo = Repo(tickets=())
        self.addCleanup(repo.close)
        return repo

    def test_two_tickets_side_by_side_then_merged_and_cleaned_up(self):
        repo = self.repo()
        drive = Drive(self, repo, (
            ("01-a", "A", "—", ["Level: 2", "Touches: `a/`"]),
            ("02-b", "B", "—", ["Level: 2", "Touches: b/"]),
            ("03-c", "C", "01", ["Level: 2", "Touches: a/"]),
        ))
        self.assertEqual(drive.fill(), "WAIT 1,2")
        self.assertEqual([p[:2] for p in drive.pending], [["BUILD", "1"], ["BUILD", "2"]])
        prompt = drive.call("prompt", "1")[1]
        self.assertIn("Work in the folder `%s`" % drive.lane_dir(1).resolve(), prompt)  # macOS: /var is /private/var
        self.assertIn("ff/f/01", prompt)
        self.assertEqual(drive.build("02", {"b/y.txt": "y\n"}, append="- (02) b learned"), "WAIT 1,2")
        self.assertEqual(drive.build("01", {"a/x.txt": "x\n"}, append="- (01) a learned"), "WAIT 1,2")
        # 02 passes first; 03 waits for 01, so lane 2 has nothing to take
        self.assertEqual(drive.review("02"), "WAIT 1")
        self.assertTrue(repo.path("b/y.txt").is_file())
        out = drive.review("01")  # 01 merges (both learnings lines kept), then 03 is leased
        self.assertEqual(out, "WAIT 1")
        self.assertEqual(drive.pending[0][:2], ["BUILD", "1"])
        self.assertEqual(drive.pending[0][3], "03")
        learnings = repo.path("plans/f/learnings.md").read_text(encoding="utf-8")
        self.assertIn("- (01) a learned", learnings)
        self.assertIn("- (02) b learned", learnings)
        self.assertEqual(drive.build("03", {"a/z.txt": "z\n"}), "WAIT 1")
        out = drive.review("03")
        self.assertTrue(out.startswith("DONE f is complete: 3 ticket(s)"), out)
        self.assertEqual(repo.porcelain(), "")
        self.assertEqual(git(repo.dir, "branch", "--list", "ff/*"), "")
        self.assertFalse(repo.path(".feature-flow/lanes/f").exists())
        self.assertEqual(len(git(repo.dir, "worktree", "list").splitlines()), 1)
        for name in ("a/x.txt", "b/y.txt", "a/z.txt"):
            self.assertTrue(repo.path(name).is_file(), name)
        log = repo.log()
        for event in ("LEASE-1", "LEASE-2", "MERGED-1", "MERGED-2", "MERGE-APPENDS", "FOOTPRINT-PASS"):
            self.assertIn(event, log)

    def test_overlapping_touches_run_one_after_the_other(self):
        repo = self.repo()
        drive = Drive(self, repo, (
            ("01-a", "A", "—", ["Level: 2", "Touches: src/"]),
            ("02-b", "B", "—", ["Level: 2", "Touches: src/b.py"]),
        ))
        self.assertEqual(drive.fill(), "WAIT 1")
        self.assertEqual(len(drive.pending), 1)
        drive.build("01", {"src/a.py": "a\n"})
        out = drive.review("01")
        self.assertEqual(out, "WAIT 1")
        self.assertEqual(drive.pending[0][3], "02")

    def test_a_build_outside_touches_is_sent_back(self):
        repo = self.repo()
        drive = Drive(self, repo, (("01-a", "A", "—", ["Level: 2", "Touches: a/"]),), lanes="1")
        rc, out = drive.call("next")
        self.assertTrue(out.startswith("BUILD plans/f/tasks/01-a.md 01 "), out)
        self.assertEqual(len(out.split()), 4)  # one lane: the BUILD line keeps its old form
        repo.path("a").mkdir()
        repo.path("a/x.txt").write_text("x\n", encoding="utf-8")
        repo.path("elsewhere.txt").write_text("x\n", encoding="utf-8")
        repo.set_status("plans/f/tasks/01-a.md", "resolved")
        repo.commit("feat: a")
        rc, out = drive.call("next")
        self.assertTrue(out.startswith("BUILD plans/f/tasks/01-a.md"), out)
        text = repo.path("plans/f/tasks/01-a.md").read_text(encoding="utf-8")
        self.assertIn("## Review findings (round 1, footprint check)", text)
        self.assertIn("elsewhere.txt", text)
        self.assertIn("FOOTPRINT-FAIL", repo.log())

    def test_a_red_gate_after_the_merge_rebuilds_the_later_ticket_once(self):
        repo = self.repo()
        both = "-c \"import os,sys; sys.exit(1 if os.path.exists('a/x.txt') and os.path.exists('b/y.txt') else 0)\""
        drive = Drive(self, repo, (
            ("01-a", "A", "—", ["Level: 2", "Touches: a/"]),
            ("02-b", "B", "—", ["Level: 2", "Touches: b/"]),
        ), test_command=both)
        drive.fill()
        drive.build("01", {"a/x.txt": "x\n"})
        drive.build("02", {"b/y.txt": "y\n"})
        self.assertEqual(drive.review("01"), "WAIT 2")
        out = drive.review("02")  # each lane passed alone; together the gate fails
        self.assertEqual(out, "WAIT 2")
        self.assertEqual(drive.pending[0][:2], ["BUILD", "2"])
        self.assertIn("REBUILD", repo.log())
        lane = drive.lane_dir(2)
        text = (lane / "plans/f/tasks/02-b.md").read_text(encoding="utf-8")
        self.assertIn("## Rebuild (the gate on its merge failed)", text)
        self.assertTrue((lane / "a/x.txt").is_file())  # rebuilt on the feature head, which has 01
        self.assertFalse((lane / "b/y.txt").exists())
        drive.build("02", {"b/w.txt": "w\n"})  # the rebuild keeps clear of what broke the merge
        out = drive.review("02")
        self.assertTrue(out.startswith("DONE f is complete: 2 ticket(s)"), out)
        self.assertTrue(repo.path("b/w.txt").is_file())
        self.assertFalse(repo.path("b/y.txt").exists())

    def test_a_conflict_with_the_feature_branch_rebuilds_the_ticket(self):
        repo = self.repo()
        drive = Drive(self, repo, (("01-a", "A", "—", ["Level: 2", "Touches: a/"]),
                                   ("02-b", "B", "—", ["Level: 2", "Touches: b/"])))
        drive.fill()
        drive.build("01", {"a/x.txt": "from the lane\n"})
        repo.path("a").mkdir()
        repo.path("a/x.txt").write_text("from someone else\n", encoding="utf-8")
        repo.commit("someone else")
        drive.review("01")
        self.assertEqual(drive.find("BUILD", "01")[1], "1")
        text = (drive.lane_dir(1) / "plans/f/tasks/01-a.md").read_text(encoding="utf-8")
        self.assertIn("## Rebuild (it conflicted with the feature branch)", text)
        self.assertIn("a/x.txt", text)
        self.assertEqual(repo.path("a/x.txt").read_text(encoding="utf-8"), "from someone else\n")
        # a second collision stops: the plan's Touches are likely wrong
        drive.build("01", {"a/x.txt": "from the lane, again\n"})
        repo.path("a/x.txt").write_text("someone else, again\n", encoding="utf-8")
        repo.commit("someone else again")
        drive.find("REVIEW", "01")
        drive.reply.write_text("REVIEW: PASS\n", encoding="utf-8")
        self.assertEqual(drive.call("verdict", str(drive.reply), "1")[0], 0)
        rc, out = drive.call("next", "1")
        self.assertEqual(rc, 1, out)
        self.assertTrue(out.startswith("STOP 01-a passed its review but it conflicted with the feature branch, and it "
                                       "was rebuilt once already"), out)

    def test_a_level_3_ticket_is_reviewed_again_when_another_merged_first(self):
        repo = self.repo()
        drive = Drive(self, repo, (("01-a", "A", "—", ["Level: 3", "Touches: a/"]),
                                   ("02-b", "B", "—", ["Level: 2", "Touches: b/"])))
        drive.fill()
        drive.build("01", {"a/x.txt": "x\n"})
        drive.build("02", {"b/y.txt": "y\n"})
        self.assertEqual(drive.review("01"), "WAIT 1,2")  # spec passed, quality next
        self.assertEqual(drive.review("02"), "WAIT 1")  # 02 merges first
        out = drive.review("01")  # quality passes, but its base is stale: reviewed again on the new head
        self.assertEqual(out, "WAIT 1")
        self.assertEqual(drive.pending[0][:2], ["REVIEW", "1"])
        self.assertIn("REFRESH", repo.log())
        prompt = drive.call("prompt", "1")[1]
        self.assertIn("(quality pass)", prompt)
        self.assertIn("the feature branch moved since this level 3 ticket was built", prompt)
        self.assertIn(repo.head(), prompt)
        out = drive.review("01")
        self.assertTrue(out.startswith("DONE f is complete: 2 ticket(s)"), out)
        self.assertTrue(repo.path("a/x.txt").is_file() and repo.path("b/y.txt").is_file())

    def test_a_level_3_ticket_keeps_clear_of_the_same_top_folder(self):
        repo = self.repo()
        drive = Drive(self, repo, (("01-a", "A", "—", ["Level: 3", "Touches: src/a/"]),
                                   ("02-b", "B", "—", ["Level: 2", "Touches: src/b/"]),
                                   ("03-c", "C", "—", ["Level: 2", "Touches: docs/"])))
        self.assertEqual(drive.fill(), "WAIT 1,2")
        self.assertEqual(sorted(p[3] for p in drive.pending), ["01", "03"])

    def test_lane_commands_need_the_lane_and_reset_drops_the_lanes(self):
        repo = self.repo()
        drive = Drive(self, repo, (("01-a", "A", "—", ["Level: 2", "Touches: a/"]),
                                   ("02-b", "B", "—", ["Level: 2", "Touches: b/"])))
        drive.fill()
        rc, out = drive.call("prompt")
        self.assertEqual(rc, 1)
        self.assertIn("prompt needs the lane", out)
        rc, out = drive.call("next", "3")
        self.assertIn("no lane 3: this run has lanes 1 to 2", out)
        rc, out = repo.flow("reset", FLOW_TAKEOVER="1")
        self.assertEqual(rc, 0, out)
        self.assertIn("removed the worktrees lane-1, lane-2", out)
        self.assertIn("deleted the branches ff/f/01, ff/f/02", out)
        self.assertFalse(repo.path(".feature-flow/lanes/f").exists())
        self.assertEqual(git(repo.dir, "branch", "--list", "ff/*"), "")


if __name__ == "__main__":
    unittest.main()
