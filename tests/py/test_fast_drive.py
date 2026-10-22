"""Drive plans through the conductor in fast mode, the way the skill does.

The bar of the fast path: level 1 and 2 tickets pass their checks with no review of their own, a level 3 or
Sensitive ticket still gets its reviews, and once every ticket is resolved one REVIEW covers the whole feature.
A FAIL there becomes a new fix ticket, built and then reviewed with the feature again. `fast on` mid-run defers
the reviews from the next ticket on, `fast off` brings them back, and the lanes take part the same way.
"""

import re
import shutil
import sys
import unittest

from helpers import ROOT, Repo
from test_lanes_drive import Drive

PYTHON = '"%s"' % sys.executable
COMMANDS = ("# Commands: f\n\nSmoke: `%s -c \"pass\"`\nTest: `%s -c \"pass\"`\nSensitive: `src/auth/`\n"
            % (PYTHON, PYTHON))
CHECK = "```check\n$ %s -c \"print('fine')\"\nprints fine\n```\n\n" % PYTHON


def ticket(index, header):
    lines = ["# T%d\n" % index, "Type: task", "Status: open",
             "Blocked by: %s" % ("—" if index == 1 else "%02d" % (index - 1)), "Test first: no"] + header
    return "\n".join(lines) + "\n\nbody\n\n## Done when\n\n- x\n\n" + CHECK + "## Answer\n"


class FastDrive(unittest.TestCase):
    def setup(self, plan, **env):
        """plan: (slug, header lines, file the builder writes). Returns (repo, env, reply file)."""
        repo = Repo(tickets=())
        self.addCleanup(repo.close)
        env = dict({"FLOW_TICKETS_PER_SESSION": "99"}, **env)
        for folder in ("agents", "guides"):
            shutil.copytree(str(ROOT / folder), str(repo.path(folder)))
        repo.path("plans/f/commands.md").write_text(COMMANDS, encoding="utf-8")
        for index, (slug, header, _) in enumerate(plan, 1):
            repo.path("plans/f/tasks/%s.md" % slug).write_text(ticket(index, header), encoding="utf-8")
        repo.commit("plan")
        self.files = {slug: name for slug, _, name in plan}
        rc, out = repo.flow("start", **env)
        self.assertEqual(rc, 0, out)
        env["FLOW_SESSION"] = out.split()[1]
        env.pop("FLOW_FAST", None)  # the run keeps it; later calls do not pass it
        reply = repo.dir.parent / (repo.dir.name + "-reply.txt")
        self.addCleanup(reply.unlink, missing_ok=True)
        return repo, env, reply

    def drive(self, repo, env, reply, verdicts=(), on_build=None):
        """Run to DONE. Every ticket review passes; the feature reviews take verdicts in turn (then PASS).
        Returns [(word, ticket name or 'all', pass)] in the order the conductor handed them out."""
        verdicts = list(verdicts)
        seen = []
        while True:
            rc, out = repo.flow("next", **env)
            self.assertEqual(rc, 0, out)
            fields = out.split()
            if fields[0] == "DONE":
                return seen, out
            if fields[0] == "BUILD":
                slug = re.sub(r"\.md$", "", fields[1].rsplit("/", 1)[-1])
                name = self.files.get(slug, "fix-%s.txt" % slug)
                repo.path(name).parent.mkdir(parents=True, exist_ok=True)
                repo.path(name).write_text("x\n", encoding="utf-8")
                repo.set_status(fields[1], "resolved")
                repo.commit("feat: %s" % slug)
                seen.append(("BUILD", fields[2], ""))
                if on_build:
                    on_build(fields[2])
                continue
            self.assertEqual(fields[0], "REVIEW", out)
            prompt = repo.flow("prompt", **env)[1]
            kind = re.search(r"\((single|spec|quality|feature) pass\)", prompt).group(1)
            seen.append(("REVIEW", fields[2], kind))
            verdict = verdicts.pop(0) if kind == "feature" and verdicts else "PASS"
            reply.write_text("FEATURE\n1. major x.py (ticket 01): wrong - fix it\n\nREVIEW: %s\n" % verdict
                             if verdict == "FAIL" else "fine\nREVIEW: PASS\n", encoding="utf-8")
            self.assertEqual(repo.flow("verdict", str(reply), **env), (0, "OK"))

    def test_only_level_3_and_sensitive_tickets_are_reviewed_then_the_feature_once(self):
        repo, env, reply = self.setup((
            ("01-light", ["Level: 1"], "a.txt"),
            ("02-standard", ["Level: 2"], "b.txt"),
            ("03-boundary", ["Level: 3"], "c.txt"),
            ("04-sensitive", ["Level: 2"], "src/auth/d.txt"),
            ("05-no-level", [], "e.txt"),
        ), FLOW_FAST="1")
        base = repo.head()
        seen, done = self.drive(repo, env, reply)
        reviews = [(num, kind) for word, num, kind in seen if word == "REVIEW"]
        self.assertEqual(reviews, [("03", "spec"), ("03", "quality"), ("04", "spec"), ("04", "quality"),
                                   ("all", "feature")])
        self.assertIn("DONE f is complete", done)
        log = repo.log()
        self.assertEqual(len(re.findall(r",(0[125]),REVIEW-DEFERRED$", log, re.MULTILINE)), 3)
        self.assertIn("FEATURE-PASS", log)
        self.assertEqual(repo.state().get("deferred"), "")

    def test_the_feature_review_prompt_names_the_range_and_the_deferred_tickets(self):
        repo, env, reply = self.setup((("01-a", ["Level: 1"], "a.txt"), ("02-b", ["Level: 2"], "b.txt")),
                                      FLOW_FAST="1")
        base = repo.head()
        line = None
        while line is None or not line.startswith("REVIEW"):
            rc, line = repo.flow("next", **env)
            self.assertEqual(rc, 0, line)
            if line.startswith("BUILD"):
                repo.resolve(line.split()[1])
        self.assertEqual(line, "REVIEW plans/f all %s" % base)
        prompt = repo.flow("prompt", **env)[1]
        self.assertIn("(feature pass), from commit `%s` to HEAD" % base, prompt)
        self.assertIn("without a review of their own: 01, 02.", prompt)
        self.assertIn("# Review a whole feature", prompt)
        self.assertEqual(repo.flow("prompt", "1", **env)[0], 1)  # the feature review has no lane

    def test_a_failed_feature_review_becomes_a_fix_ticket_and_the_feature_is_reviewed_again(self):
        repo, env, reply = self.setup((("01-a", ["Level: 1"], "a.txt"), ("02-b", ["Level: 2"], "b.txt")),
                                      FLOW_FAST="1")
        seen, done = self.drive(repo, env, reply, verdicts=["FAIL"])
        self.assertEqual(seen, [("BUILD", "01", ""), ("BUILD", "02", ""), ("REVIEW", "all", "feature"),
                                ("BUILD", "03", ""), ("REVIEW", "all", "feature")])
        fix = repo.path("plans/f/tasks/03-feature-review-fixes-1.md").read_text(encoding="utf-8")
        self.assertIn("Status: resolved", fix)
        self.assertIn("> 1. major x.py (ticket 01): wrong - fix it", fix)
        self.assertIn("Level: 2", fix)
        self.assertIn("FEATURE-FAIL", repo.log())
        self.assertIn("DONE", done)

    def test_a_feature_review_without_a_verdict_is_handed_out_again_then_stops(self):
        repo, env, reply = self.setup((("01-a", ["Level: 3"], "a.txt"), ("02-b", ["Level: 1"], "b.txt")),
                                      FLOW_FAST="1")
        reply.write_text("fine\nREVIEW: PASS\n", encoding="utf-8")
        line = ""
        while not line.startswith("REVIEW plans/f all"):
            rc, line = repo.flow("next", **env)
            self.assertEqual(rc, 0, line)
            if line.startswith("BUILD"):
                repo.resolve(line.split()[1])
            elif line.startswith("REVIEW plans/f/tasks/01"):  # the level 3 ticket's own reviews
                self.assertEqual(repo.flow("verdict", str(reply), **env), (0, "OK"))
        first = line
        reply.write_text("no verdict here\n", encoding="utf-8")
        self.assertEqual(repo.flow("verdict", str(reply), **env), (0, "RETRY no review verdict"))
        self.assertEqual(repo.flow("next", **env), (0, first))  # the level 3 ticket's review count is not this one's
        self.assertEqual(repo.flow("verdict", str(reply), **env), (0, "RETRY no review verdict"))
        rc, out = repo.flow("next", **env)
        self.assertEqual((rc, out), (1, "STOP no verdict from the feature review of f after 2 attempt(s)"))

    def test_the_feature_review_stops_after_its_rounds(self):
        repo, env, reply = self.setup((("01-a", ["Level: 1"], "a.txt"),), FLOW_FAST="1", FLOW_MAX_REVIEW_ROUNDS="1")
        with self.assertRaises(AssertionError) as caught:
            self.drive(repo, env, reply, verdicts=["FAIL", "FAIL"])
        self.assertIn("STOP the feature review of f still fails after 1 round(s)", str(caught.exception))

    def test_fast_on_mid_run_defers_from_the_next_ticket_and_fast_off_brings_reviews_back(self):
        repo, env, reply = self.setup((
            ("01-a", ["Level: 1"], "a.txt"),
            ("02-b", ["Level: 1"], "b.txt"),
            ("03-c", ["Level: 1"], "c.txt"),
        ))

        def switch(num):
            if num == "01":  # switched before the conductor judges 01, so 01 is the first deferred
                self.assertEqual(repo.flow("fast", "on", **env), (0, "OK fast on"))
            if num == "02":
                rc, out = repo.flow("fast", "off", **env)
                self.assertEqual(rc, 0, out)
                self.assertIn("1 ticket(s) already deferred still get the feature review", out)

        seen, _ = self.drive(repo, env, reply, on_build=switch)
        self.assertEqual([(num, kind) for word, num, kind in seen if word == "REVIEW"],
                         [("02", "single"), ("03", "single"), ("all", "feature")])
        self.assertIn("FAST-ON", repo.log())
        self.assertIn("FAST-OFF", repo.log())

    def test_fast_needs_the_session_and_on_or_off(self):
        repo, env, _ = self.setup((("01-a", ["Level: 1"], "a.txt"),))
        self.assertEqual(repo.flow("fast", "maybe", **env), (1, "STOP fast takes on or off, not maybe"))
        rc, out = repo.flow("fast", "on", FLOW_SESSION="nope")
        self.assertEqual(rc, 1)
        self.assertIn("owned by another session", out)
        rc, out = repo.flow("fast", "on", FLOW_TRUSTED="0", FLOW_SESSION=env["FLOW_SESSION"])
        self.assertIn("flow-trust.py", out)

    def test_with_the_gate_off_every_ticket_keeps_its_review(self):
        repo, env, reply = self.setup((("01-a", ["Level: 1"], "a.txt"),), FLOW_FAST="1", FLOW_GATE="off")
        env["FLOW_GATE"] = "off"
        seen, _ = self.drive(repo, env, reply)
        self.assertEqual([num for word, num, _ in seen if word == "REVIEW"], ["01"])

    def test_reset_keeps_the_deferred_tickets_for_the_feature_review(self):
        repo, env, reply = self.setup((("01-a", ["Level: 1"], "a.txt"), ("02-b", ["Level: 1"], "b.txt")),
                                      FLOW_FAST="1")
        rc, line = repo.flow("next", **env)
        repo.resolve(line.split()[1])
        rc, line = repo.flow("next", **env)  # 01 deferred, 02 handed out
        self.assertTrue(line.startswith("BUILD plans/f/tasks/02-b.md"), line)
        rc, out = repo.flow("reset", FLOW_TAKEOVER="1")
        self.assertEqual(rc, 0, out)
        self.assertIn("kept 1 ticket(s) built in fast mode for the feature review", out)
        rc, out = repo.flow("start")
        env["FLOW_SESSION"] = out.split()[1]
        seen, _ = self.drive(repo, env, reply)
        self.assertEqual([num for word, num, _ in seen if word == "REVIEW"], ["all"])
        self.assertEqual(len(re.findall(r"REVIEW-DEFERRED", repo.log())), 2)

    def test_relay_hands_off_before_the_feature_review_is_judged(self):
        repo, env, reply = self.setup((("01-a", ["Level: 1"], "a.txt"),), FLOW_FAST="1", FLOW_RELAY="1")
        env["FLOW_RELAY"] = "1"
        rc, line = repo.flow("next", **env)
        repo.resolve(line.split()[1])
        self.assertEqual(repo.flow("next", **env)[1].split()[0], "HANDOFF")  # after the build
        env["FLOW_SESSION"] = repo.flow("start", **env)[1].split()[1]
        rc, line = repo.flow("next", **env)
        self.assertTrue(line.startswith("REVIEW plans/f all"), line)
        reply.write_text("ok\nREVIEW: PASS\n", encoding="utf-8")
        self.assertEqual(repo.flow("verdict", str(reply), **env), (0, "OK"))
        self.assertEqual(repo.flow("next", **env)[1].split()[0], "HANDOFF")  # after the feature review
        env["FLOW_SESSION"] = repo.flow("start", **env)[1].split()[1]
        rc, out = repo.flow("next", **env)
        self.assertTrue(out.startswith("DONE"), out)
        self.assertRegex(repo.log(), r",all,REVIEW\n")

    def test_without_fast_nothing_changes(self):
        repo, env, reply = self.setup((("01-a", ["Level: 1"], "a.txt"), ("02-b", ["Level: 2"], "b.txt")))
        seen, _ = self.drive(repo, env, reply)
        self.assertNotIn("all", [num for _, num, _ in seen])
        self.assertNotIn("REVIEW-DEFERRED", repo.log())


class FeatureDrive(Drive):
    """The lanes drive, but a REVIEW with no lane word (the feature review) ends a fill, as WAIT does."""

    def take(self, rc, out):
        if out.startswith("REVIEW ") and len(out.split()) == 4:
            self.test.assertEqual(rc, 0, out)
            return out
        return Drive.take(self, rc, out)


class FastLanes(unittest.TestCase):
    def test_lanes_merge_deferred_tickets_and_the_feature_review_runs_without_a_lane(self):
        repo = Repo(tickets=())
        self.addCleanup(repo.close)
        base = repo.head()
        drive = FeatureDrive.__new__(FeatureDrive)  # Drive starts the run itself; start it with FLOW_FAST=1 instead
        drive.test, drive.repo, drive.pending, drive.lines = self, repo, [], []
        for folder in ("agents", "guides"):
            shutil.copytree(str(ROOT / folder), str(repo.path(folder)))
        repo.path("plans/f/commands.md").write_text(
            "# Commands: f\n\nSetup: `%s -c \"pass\"`\nSmoke: `%s -c \"pass\"`\nTest: `%s -c \"pass\"`\n"
            % (PYTHON, PYTHON, PYTHON), encoding="utf-8")
        for slug, touches in (("01-a", "a/"), ("02-b", "b/")):
            repo.path("plans/f/tasks/%s.md" % slug).write_text(
                ticket(1, ["Level: 2", "Touches: %s" % touches]), encoding="utf-8")
        repo.commit("plan")
        plan_head = repo.head()
        drive.env = {"FLOW_TICKETS_PER_SESSION": "99", "FLOW_LANES": "2", "FLOW_FAST": "1"}
        rc, out = repo.flow("start", **drive.env)
        self.assertEqual(rc, 0, out)
        drive.env["FLOW_SESSION"] = out.split()[1]
        drive.reply = repo.dir.parent / (repo.dir.name + "-reply.txt")
        self.addCleanup(drive.reply.unlink, missing_ok=True)

        self.assertEqual(drive.fill(), "WAIT 1,2")
        self.assertEqual(drive.build("01", {"a/x.txt": "a\n"}), "WAIT 2")
        last = drive.build("02", {"b/y.txt": "b\n"})
        self.assertEqual(last, "REVIEW plans/f all %s" % plan_head)
        self.assertNotIn("REVIEW", " ".join(l for l in drive.lines if l != last))
        self.assertEqual(repo.flow("next", "1", **drive.env)[0], 1)  # no lane for the feature review
        drive.reply.write_text("ok\nREVIEW: PASS\n", encoding="utf-8")
        self.assertEqual(repo.flow("verdict", str(drive.reply), **drive.env), (0, "OK"))
        rc, out = repo.flow("next", **drive.env)
        self.assertEqual(rc, 0, out)
        self.assertTrue(out.startswith("DONE f is complete: 2 ticket(s)"), out)
        self.assertTrue(repo.path("a/x.txt").is_file() and repo.path("b/y.txt").is_file())
        self.assertNotEqual(base, plan_head)


if __name__ == "__main__":
    unittest.main()
