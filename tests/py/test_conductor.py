import os
import unittest

from helpers import Repo

T1 = "plans/f/tasks/01-a.md"
T2 = "plans/f/tasks/02-b.md"


class BuildAndChecks(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()

    def tearDown(self):
        self.repo.close()

    def test_first_next_hands_out_the_first_ticket(self):
        sha = self.repo.head()
        rc, out = self.repo.flow("next")
        self.assertEqual((rc, out), (0, "BUILD %s 01 %s" % (T1, sha)))
        self.assertTrue(self.repo.path(".feature-flow/state/flow-f.state").is_file())
        self.assertIn(",01,BUILD", self.repo.log())
        self.assertEqual(self.repo.porcelain(), "")

    def test_resolved_ticket_goes_to_review_after_the_checks(self):
        sha = self.repo.head()
        self.repo.flow("next")
        self.repo.resolve(T1)
        rc, out = self.repo.flow("next")
        self.assertEqual((rc, out), (0, "REVIEW %s 01 %s" % (T1, sha)))
        self.assertEqual(self.repo.state()["review_sha"], self.repo.head())
        self.assertIn("GATE-PASS", self.repo.log())
        self.assertIn("GUARD-PASS", self.repo.log())

    def test_claimed_ticket_is_reset_and_built_again_then_stops(self):
        self.repo.flow("next")
        self.repo.set_status(T1, "claimed")
        rc, out = self.repo.flow("next")
        self.assertEqual(rc, 0)
        self.assertTrue(out.startswith("BUILD %s 01 " % T1))
        self.assertIn("Status: open", self.repo.path(T1).read_text(encoding="utf-8"))
        rc, out = self.repo.flow("next")
        self.assertEqual((rc, out), (1, "STOP 01-a is still unresolved after 2 attempt(s)"))

    def test_failing_gate_sends_the_ticket_back_then_stops(self):
        cmd = self.repo.path("plans/f/commands.md")
        cmd.write_text(cmd.read_text(encoding="utf-8") + "Test: `python -c \"import os, sys; sys.exit(os.path.exists('FAILING'))\"`\n", encoding="utf-8")
        self.repo.path("FAILING").write_text("x\n", encoding="utf-8")
        self.repo.commit("failing test")
        self.repo.flow("next")
        for round_no in (1, 2, 3):
            self.repo.resolve(T1, "feat: round %d" % round_no)
            rc, out = self.repo.flow("next")
            self.assertEqual(rc, 0)
            self.assertTrue(out.startswith("BUILD %s 01 " % T1), out)
            text = self.repo.path(T1).read_text(encoding="utf-8")
            self.assertIn("## Review findings (round %d, gate)" % round_no, text)
            self.assertIn("Status: open", text)
            self.assertEqual(self.repo.git("log", "-1", "--format=%s"), "chore(f): 01 review findings, round %d" % round_no)
        self.repo.resolve(T1, "feat: round 4")
        rc, out = self.repo.flow("next")
        self.assertEqual((rc, out), (1, "STOP 01-a still fails the gate after 3 round(s)"))

    def test_an_uncommitted_install_is_not_a_dirty_tree_but_other_files_are(self):
        for rel in (".claude/agents/ticket-builder.md", ".agents/skills/feature-flow/SKILL.md"):
            self.repo.path(rel).parent.mkdir(parents=True, exist_ok=True)
            self.repo.path(rel).write_text("x\n", encoding="utf-8")
        self.repo.path(".feature-flow").mkdir()
        self.repo.path(".feature-flow/installed.txt").write_text(
            ".agents/skills/feature-flow/SKILL.md\n.claude/agents/ticket-builder.md\n.feature-flow/installed.txt\n",
            encoding="utf-8")
        self.repo.path("notes.txt").write_text("mine\n", encoding="utf-8")
        rc, out = self.repo.flow("next")
        self.assertEqual((rc, out), (1, "STOP working tree is not clean, commit or stash first: notes.txt"))
        self.repo.path("notes.txt").unlink()
        rc, out = self.repo.flow("next")
        self.assertEqual((rc, out), (0, "BUILD %s 01 %s" % (T1, self.repo.head())))

    def test_untracked_python_bytecode_is_not_a_dirty_tree_but_other_files_are(self):
        self.repo.path("pkg/__pycache__").mkdir(parents=True)
        self.repo.path("pkg/__pycache__/m.cpython-312.pyc").write_bytes(b"\0")
        self.repo.path("stray.pyc").write_bytes(b"\0")
        self.repo.path("notes.txt").write_text("mine\n", encoding="utf-8")
        rc, out = self.repo.flow("next")
        self.assertEqual((rc, out), (1, "STOP working tree is not clean, commit or stash first: notes.txt"))
        self.repo.path("notes.txt").unlink()
        rc, out = self.repo.flow("next")
        self.assertEqual((rc, out), (0, "BUILD %s 01 %s" % (T1, self.repo.head())))

    def test_resolved_ticket_with_a_dirty_tree_stops(self):
        self.repo.flow("next")
        self.repo.set_status(T1, "resolved")
        self.repo.commit("feat: 01")
        self.repo.path("stray.txt").write_text("x\n", encoding="utf-8")
        rc, out = self.repo.flow("next")
        self.assertEqual((rc, out), (1, "STOP working tree is dirty after 01-a, it should have been committed"))

    def test_failing_smoke_stops_before_the_first_build(self):
        rc, out = self.repo.flow("next", FLOW_SMOKE="false")
        self.assertEqual(rc, 1)
        self.assertTrue(out.startswith("STOP smoke test failed before 01-a"), out)

    def test_usage(self):
        rc, _ = self.repo.flow("bogus")
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()


class StateOutsideGit(unittest.TestCase):
    """Ticket 14: a normal Codex session can write the worktree but not .git."""

    def setUp(self):
        self.repo = Repo()
        self.gitdir = self.repo.path(".git")

    def tearDown(self):
        os.chmod(str(self.gitdir), 0o755)
        self.repo.close()

    def flow(self, *args, **env):
        """Run the conductor with .git unwritable, as the sandbox has it. Root ignores the mode,
        so the run also checks that no flow file ever appears under .git."""
        os.chmod(str(self.gitdir), 0o555)
        try:
            return self.repo.flow(*args, **env)
        finally:
            os.chmod(str(self.gitdir), 0o755)

    def review_pass(self, token, **env):
        reply = self.repo.path(".feature-flow/state/flow-review-f.txt")
        reply.write_text("looks right\nREVIEW: PASS\n", encoding="utf-8")
        self.assertEqual(self.flow("verdict", str(reply), FLOW_SESSION=token, **env), (0, "OK"))

    def test_a_run_hands_off_and_resumes_without_writing_git(self):
        env = {"FLOW_TICKETS_PER_SESSION": "1", "FLOW_INVOKE": "$feature-flow"}
        rc, out = self.flow("start", **env)
        self.assertEqual(rc, 0, out)
        token = out.split()[1]
        self.assertEqual(self.flow("next", **env)[0], 1, "a call without the owner's token stops")
        self.assertTrue(self.flow("next", FLOW_SESSION=token, **env)[1].startswith("BUILD %s 01 " % T1))
        self.repo.resolve(T1)
        self.assertTrue(self.flow("next", FLOW_SESSION=token, **env)[1].startswith("REVIEW %s 01 " % T1))
        self.review_pass(token, **env)
        self.assertEqual(self.flow("next", FLOW_SESSION=token, **env), (0, "HANDOFF $feature-flow f"))
        rc, out = self.flow("start", **env)
        self.assertEqual(rc, 0, "the next session starts without a takeover: %s" % out)
        token = out.split()[1]
        self.assertTrue(self.flow("next", FLOW_SESSION=token, **env)[1].startswith("BUILD %s 02 " % T2))
        self.assertEqual(self.repo.porcelain(), "")
        self.assertEqual(sorted(p.name for p in self.gitdir.glob("flow-*")), [])
        self.assertEqual(self.repo.path(".feature-flow/state/.gitignore").read_text(encoding="utf-8"), "*\n")

    def test_an_unwritable_state_folder_stops_with_a_clear_reason(self):
        # a file where the folder should be: refused for root too, unlike a folder's mode
        self.repo.path(".feature-flow").write_text("not a folder\n", encoding="utf-8")
        self.repo.commit("a file named .feature-flow")
        rc, out = self.repo.flow("start")
        self.assertEqual(rc, 1)
        self.assertIn("STOP cannot write the flow state in", out)

    def test_a_run_kept_under_git_moves_over_with_its_owner(self):
        self.repo.path(".git/flow-f.state").write_text("owner=abc123\nphase=\nsession_done=0\n", encoding="utf-8")
        self.repo.path(".git/flow-f.log").write_text("10:00:00,-,START\n", encoding="utf-8")
        rc, out = self.flow("start")
        self.assertEqual(rc, 1, "the old owner still holds the feature")
        self.assertIn("owned by session abc123", out)
        self.assertTrue(self.flow("next", FLOW_SESSION="abc123")[1].startswith("BUILD %s 01 " % T1))
        self.assertIn("10:00:00,-,START", self.repo.log())
        self.assertEqual(self.repo.state()["owner"], "abc123")
