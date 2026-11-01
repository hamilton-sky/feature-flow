"""Drive plans through the conductor with a checkpointed gate (`Gate: batch N` or `Gate: end` in commands.md).

The bar: each ticket gets only the cheap checks (Quick when there is one, the floor guard, the footprint) and no
review of its own below level 3. Every N tickets, and at the end, the full gate and each ticket's Done when checks
run at HEAD, then one review of the tickets since the last checkpoint. A red gate there reopens only the ticket
that broke it (the first at whose commit the gate fails), and a failing Done when reopens its own ticket.
"""

import re
import shutil
import sys
import unittest

from helpers import ROOT, Repo
from test_lanes_drive import Drive as LaneDrive

PYTHON = '"%s"' % sys.executable
# the Test command fails while bad.txt exists
TEST = "%s -c \"import os,sys; sys.exit(os.path.exists('bad.txt'))\"" % PYTHON


def check(exists):
    """A check block that passes only once the file exists."""
    return ("```check\n$ %s -c \"import os,sys; sys.exit(not os.path.exists('%s'))\"\n```\n\n" % (PYTHON, exists)
            if exists else "```check\n$ %s -c \"print('fine')\"\nprints fine\n```\n\n" % PYTHON)


def ticket(index, header, exists=None):
    lines = ["# T%d\n" % index, "Type: task", "Status: open",
             "Blocked by: %s" % ("—" if index == 1 else "%02d" % (index - 1)), "Test first: no"] + header
    return "\n".join(lines) + "\n\nbody\n\n## Done when\n\n- x\n\n" + check(exists) + "## Answer\n"


class CheckpointDrive(unittest.TestCase):
    def setup(self, plan, gate="batch 2", quick=False, **env):
        """plan: [(slug, header lines, file a Done when check waits for or None)]."""
        repo = Repo(tickets=())
        self.addCleanup(repo.close)
        env = dict({"FLOW_TICKETS_PER_SESSION": "99", "FLOW_SCOUTS": "off"}, **env)
        for folder in ("agents", "guides"):
            shutil.copytree(str(ROOT / folder), str(repo.path(folder)))
        repo.path("plans/f/commands.md").write_text(
            "# Commands: f\n\nSmoke: `%s -c \"pass\"`\nTest: `%s`\n%s%s" % (
                PYTHON, TEST, "Quick: `%s -c \"pass\"`\n" % PYTHON if quick else "",
                "Gate: `%s`\n" % gate if gate else ""), encoding="utf-8")
        for index, (slug, header, exists) in enumerate(plan, 1):
            repo.path("plans/f/tasks/%s.md" % slug).write_text(ticket(index, header, exists), encoding="utf-8")
        repo.commit("plan")
        rc, out = repo.flow("start", **env)
        self.assertEqual(rc, 0, out)
        env["FLOW_SESSION"] = out.split()[1]
        reply = repo.dir.parent / (repo.dir.name + "-reply.txt")
        self.addCleanup(reply.unlink, missing_ok=True)
        self.repo, self.env, self.reply = repo, env, reply
        return repo

    def drive(self, build=None, verdicts=()):
        """Run to DONE. build(num, times built) may change files before the build is committed. Every review
        passes, the feature reviews take verdicts in turn. Returns [(word, num)] in order."""
        repo, env = self.repo, self.env
        verdicts = list(verdicts)
        seen, built = [], {}
        for _ in range(60):
            rc, out = repo.flow("next", **env)
            self.assertEqual(rc, 0, out)
            fields = out.split()
            if fields[0] == "DONE":
                return seen
            if fields[0] == "BUILD":
                num = fields[2]
                built[num] = built.get(num, 0) + 1
                repo.path("work-%s-%d.txt" % (num, built[num])).write_text("x\n", encoding="utf-8")
                if build:
                    build(num, built[num])
                repo.set_status(fields[1], "resolved")
                repo.commit("feat: %s" % num)
                seen.append(("BUILD", num))
                continue
            self.assertEqual(fields[0], "REVIEW", out)
            seen.append(("REVIEW", fields[2]))
            verdict = verdicts.pop(0) if fields[2] == "all" and verdicts else "PASS"
            self.reply.write_text("FEATURE\n1. major x.py (ticket 01): wrong - fix it\n\nREVIEW: FAIL\n"
                                  if verdict == "FAIL" else "fine\nREVIEW: PASS\n", encoding="utf-8")
            self.assertEqual(repo.flow("verdict", str(self.reply), **env), (0, "OK"))
        self.fail("no DONE after 60 calls: %s" % seen)

    def events(self, name):
        return re.findall(r"^[^,]*,([^,]*),%s$" % re.escape(name), self.repo.log(), re.MULTILINE)

    def test_batch_2_gates_and_reviews_every_two_tickets(self):
        self.setup([("01-a", ["Level: 2"], None), ("02-b", ["Level: 1"], None), ("03-c", ["Level: 2"], None),
                    ("04-d", [], None)])
        seen = self.drive()
        self.assertEqual(seen, [("BUILD", "01"), ("BUILD", "02"), ("REVIEW", "all"),
                                ("BUILD", "03"), ("BUILD", "04"), ("REVIEW", "all")])
        log = self.repo.log()
        self.assertIn(",GATE-BATCH-2", log)
        self.assertEqual(len(self.events("CHECKPOINT-PASS")), 2)
        self.assertEqual(len(self.events("REVIEW-DEFERRED")), 4)
        self.assertEqual(self.events("GATE-FULL"), ["all", "all"])  # no full gate after a ticket, one per checkpoint
        self.assertEqual(self.events("DONEWHEN-PASS"), ["01", "02", "03", "04"])  # each ticket's, at its checkpoint

    def test_the_checkpoint_review_is_told_it_is_a_checkpoint(self):
        self.setup([("01-a", ["Level: 2"], None), ("02-b", ["Level: 2"], None), ("03-c", ["Level: 2"], None)])
        repo, env = self.repo, self.env
        for _ in range(2):
            rc, line = repo.flow("next", **env)
            repo.resolve(line.split()[1])
        rc, line = repo.flow("next", **env)
        self.assertTrue(line.startswith("REVIEW plans/f all"), line)
        prompt = repo.flow("prompt", **env)[1]
        self.assertIn("without a review of their own: 01, 02.", prompt)
        self.assertIn("the conductor ran the full gate and each of these tickets' Done when checks at HEAD", prompt)
        self.assertIn("this is a checkpoint, not the end", prompt)

    def test_quick_runs_after_each_ticket_and_the_full_gate_at_the_checkpoint(self):
        self.setup([("01-a", ["Level: 2"], None), ("02-b", ["Level: 2"], None)], quick=True)
        self.drive()
        self.assertEqual(self.events("GATE-QUICK"), ["01", "02"])
        self.assertEqual(self.events("GATE-FULL"), ["all"])

    def test_a_red_gate_reopens_only_the_ticket_that_broke_it(self):
        self.setup([("01-a", ["Level: 2"], None), ("02-b", ["Level: 2"], None), ("03-c", ["Level: 2"], None),
                    ("04-d", ["Level: 2"], None)], gate="end")

        def build(num, times):
            if num == "02":
                path = self.repo.path("bad.txt")
                if times == 1:
                    path.write_text("broken\n", encoding="utf-8")
                else:
                    path.unlink()

        seen = self.drive(build)
        self.assertEqual(seen, [("BUILD", "01"), ("BUILD", "02"), ("BUILD", "03"), ("BUILD", "04"),
                                ("BUILD", "02"), ("REVIEW", "all")])
        self.assertEqual(self.events("CHECKPOINT-FAIL"), ["02"])
        text = self.repo.path("plans/f/tasks/02-b.md").read_text(encoding="utf-8")
        self.assertIn("## Review findings (round 1, checkpoint, gate (full))", text)
        self.assertIn("this ticket broke it", text)
        for other in ("01-a", "03-c", "04-d"):
            self.assertNotIn("checkpoint", self.repo.path("plans/f/tasks/%s.md" % other).read_text(encoding="utf-8"))
        self.assertTrue(self.repo.git("symbolic-ref", "-q", "HEAD"))  # back on the branch after the search

    def test_a_failing_done_when_reopens_its_own_ticket(self):
        self.setup([("01-a", ["Level: 2"], None), ("02-b", ["Level: 2"], "ok.txt")])

        def build(num, times):
            if num == "02" and times == 2:
                self.repo.path("ok.txt").write_text("x\n", encoding="utf-8")

        seen = self.drive(build)
        self.assertEqual(seen, [("BUILD", "01"), ("BUILD", "02"), ("BUILD", "02"), ("REVIEW", "all")])
        self.assertEqual(self.events("CHECKPOINT-FAIL"), ["02"])
        self.assertIn("checkpoint, done when", self.repo.path("plans/f/tasks/02-b.md").read_text(encoding="utf-8"))

    def test_a_failed_checkpoint_review_waits_for_its_fix_ticket(self):
        self.setup([("01-a", ["Level: 2"], None), ("02-b", ["Level: 2"], None), ("03-c", ["Level: 2"], None)])
        seen = self.drive(verdicts=["FAIL"])
        # with 3 deferred the checkpoint waits for the fix ticket (04), then reviews all four
        self.assertEqual(seen, [("BUILD", "01"), ("BUILD", "02"), ("REVIEW", "all"), ("BUILD", "03"),
                                ("BUILD", "04"), ("REVIEW", "all")])

    def test_a_level_3_ticket_keeps_its_own_review(self):
        self.setup([("01-a", ["Level: 3"], None), ("02-b", ["Level: 2"], None)], gate="end")
        seen = self.drive()
        self.assertEqual(seen, [("BUILD", "01"), ("REVIEW", "01"), ("BUILD", "02"), ("REVIEW", "all")])
        self.assertEqual(self.events("GATE-FULL"), ["01", "all"])  # with its own review, its own full gate too
        self.assertEqual(self.events("DONEWHEN-PASS"), ["01", "02"])

    def test_each_keeps_a_review_and_the_full_gate_per_ticket(self):
        self.setup([("01-a", ["Level: 2"], None), ("02-b", ["Level: 2"], None)], gate="each")
        seen = self.drive()
        self.assertEqual(seen, [("BUILD", "01"), ("REVIEW", "01"), ("BUILD", "02"), ("REVIEW", "02")])
        self.assertEqual(self.events("CHECKPOINT-PASS"), [])

    def test_the_fast_profile_gates_at_the_end_and_standard_every_3(self):
        self.setup([("01-a", ["Level: 2"], None), ("02-b", ["Level: 2"], None)], gate=None, FLOW_PROFILE="fast")
        self.assertIn(",GATE-END", self.repo.log())
        self.assertEqual(self.drive(), [("BUILD", "01"), ("BUILD", "02"), ("REVIEW", "all")])
        self.setup([("01-a", ["Level: 2"], None)], gate=None, FLOW_PROFILE="standard")
        self.assertIn(",GATE-BATCH-3", self.repo.log())

    def test_the_gate_off_keeps_every_review(self):
        self.setup([("01-a", ["Level: 2"], None)], gate="off unsafe")
        self.assertEqual(self.drive(), [("BUILD", "01"), ("REVIEW", "01")])

    def test_lanes_stop_leasing_until_the_checkpoint_has_run(self):
        repo = Repo(tickets=())
        self.addCleanup(repo.close)
        drive = LaneDrive(self, repo, (
            ("01-a", "A", "—", ["Level: 2", "Touches: a/"]),
            ("02-b", "B", "—", ["Level: 2", "Touches: b/"]),
            ("03-c", "C", "—", ["Level: 2", "Touches: c/"]),
        ), extra="Gate: `batch 2`\n")
        self.assertEqual(drive.fill(), "WAIT 1,2")
        self.assertEqual(drive.build("01", {"a/x.txt": "x\n"}), "WAIT 1,2")  # merged, deferred, 03 leased to lane 1
        self.assertEqual(drive.build("02", {"b/y.txt": "y\n"}), "WAIT 1")  # two deferred: lane 1 drains first
        item = drive.find("BUILD", "03")  # built by hand: the feature review it leads to takes no `next`
        drive.pending.remove(item)
        where = drive.lane_dir(item[1])
        (where / "c").mkdir()
        (where / "c/z.txt").write_text("z\n", encoding="utf-8")
        path = where / item[2]
        path.write_text(path.read_text(encoding="utf-8").replace("Status: open", "Status: resolved", 1), encoding="utf-8")
        repo.git("-C", str(where), "add", "-A")
        repo.git("-C", str(where), "commit", "-qm", "feat: 03")
        rc, out = drive.call("next", item[1])
        self.assertTrue(out.startswith("REVIEW plans/f all "), out)  # one review of the three, no lane
        self.assertEqual(self.events_of(repo, "CHECKPOINT-PASS"), ["all"])
        self.assertEqual(self.events_of(repo, "REVIEW-DEFERRED"), ["01", "02", "03"])
        self.assertEqual([e for e in self.events_of(repo, "MERGE-GATE-FULL-PASS")], [])  # no Quick: merges ungated
        drive.reply.write_text("fine\nREVIEW: PASS\n", encoding="utf-8")
        self.assertEqual(drive.call("verdict", str(drive.reply))[0], 0)
        rc, out = drive.call("next")
        self.assertTrue(out.startswith("DONE f is complete: 3 ticket(s)"), out)

    def events_of(self, repo, name):
        return re.findall(r"^[^,]*,([^,]*),%s$" % re.escape(name), repo.log(), re.MULTILINE)

    def test_a_bad_gate_line_stops(self):
        repo = Repo(tickets=())
        self.addCleanup(repo.close)
        repo.path("plans/f/commands.md").write_text("# Commands: f\n\nGate: `sometimes`\n", encoding="utf-8")
        repo.commit("plan")
        rc, out = repo.flow("start")
        self.assertEqual(rc, 1)
        self.assertIn("Gate: line must be each, batch N (N from 1 to 20), end, or off unsafe", out)


if __name__ == "__main__":
    unittest.main()
