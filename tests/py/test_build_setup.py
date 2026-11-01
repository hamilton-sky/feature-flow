"""The build setup a plan carries (0.33.0): extra gate commands (Typecheck:, Security:, Check <path>:), the checks'
own count of send-backs, a plan-level Floor: line with a reason, `Gate: off unsafe`, and `Lanes:` from the plan."""

import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import helpers
from helpers import ROOT, Repo

import sys
sys.path.insert(0, str(ROOT))
from feature_flow import evaluate, floorguard, gate, report  # the modules under test, from this checkout
from feature_flow.conductor.policy import limits

T1 = "plans/f/tasks/01-a.md"
FAIL_IF = "`python -c \"import os, sys; sys.exit(os.path.exists('%s'))\"`"


def add_commands(repo, *lines):
    cmd = repo.path("plans/f/commands.md")
    cmd.write_text(cmd.read_text(encoding="utf-8") + "".join(l + "\n" for l in lines), encoding="utf-8")


class Gate(unittest.TestCase):
    def run_gate(self, text, changed=None):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plans" / "f"
            plan.mkdir(parents=True)
            (plan / "commands.md").write_text(text, encoding="utf-8")
            chunks = []
            code = gate.run("f", chunks.append, chunks.append, 1, cwd=tmp, changed=changed)
            return code, "".join(chunks)

    def test_typecheck_and_security_run_after_lint(self):
        code, out = self.run_gate("Lint: `python -c pass`\nTypecheck: `python -c pass`\nSecurity: `python -c \"raise SystemExit(3)\"`\n")
        self.assertEqual(code, 1)
        self.assertIn("gate: Typecheck: python -c pass\n", out)
        self.assertIn("gate: Security failed", out)

    def test_a_path_check_runs_only_for_a_build_that_changed_its_path(self):
        text = "Check web/: `python -c \"raise SystemExit(4)\"`\nCheck <path>: `<placeholder>`\n"
        self.assertEqual(self.run_gate(text, changed=["src/a.py"]), (0, "gate: no commands defined, nothing to run\n"))
        code, out = self.run_gate(text, changed=["web/app.js"])
        self.assertEqual(code, 1)
        self.assertIn("gate: Check web/ failed", out)
        self.assertEqual(self.run_gate(text)[0], 1)  # by hand, every path check runs
        self.assertEqual(gate.path_checks("/no/such/file"), [])


class CheckRounds(unittest.TestCase):
    def test_checks_have_their_own_count(self):
        self.assertEqual(limits.cap_of("check", 1, 3), 3)
        self.assertEqual(limits.cap_of("review", 1, 3), 1)
        self.assertEqual(limits.cap_of("review", 2, 3), 3)

    def test_gate_send_backs_leave_the_review_rounds_alone(self):
        repo = Repo()
        self.addCleanup(repo.close)
        add_commands(repo, "Test: " + FAIL_IF % "FAILING")
        repo.path("FAILING").write_text("x\n", encoding="utf-8")
        repo.commit("failing test")
        repo.flow("next")
        for n in (1, 2):
            repo.resolve(T1, "feat: round %d" % n)
            self.assertTrue(repo.flow("next")[1].startswith("BUILD"))
        os.remove(str(repo.path("FAILING")))
        repo.commit("fixed")
        repo.resolve(T1, "feat: round 3")
        rc, out = repo.flow("next")
        self.assertTrue(out.startswith("REVIEW %s 01 " % T1), out)
        st = repo.state()
        self.assertEqual((st.get("check_rounds"), st.get("review_rounds"), st.get("round")), ("2", "0", "2"))


class PlanFloor(unittest.TestCase):
    def test_a_plan_floor_line_needs_a_reason_and_allows_only_diff_categories(self):
        self.assertEqual(floorguard.plan_allow("Floor: allow config, reason: upgrading eslint\n"),
                         ("config", "upgrading eslint", ""))
        self.assertIn("needs a reason", floorguard.plan_allow("Floor: allow config\n")[2])
        self.assertIn("not commands-edit", floorguard.plan_allow("Floor: allow commands-edit, reason: x\n")[2])
        self.assertEqual(floorguard.plan_allow("Floor: `<optional: allow ...>`\n"), ("", "", ""))

    def test_the_relax_is_logged_and_a_bad_line_stops_the_start(self):
        repo = Repo()
        self.addCleanup(repo.close)
        add_commands(repo, "Floor: allow config, reason: upgrading eslint")
        repo.commit("relax")
        rc, out = repo.flow("start")
        self.assertEqual(rc, 0, out)
        self.assertIn("FLOOR-RELAXED-CONFIG", repo.log())
        repo2 = Repo()
        self.addCleanup(repo2.close)
        add_commands(repo2, "Floor: allow config")
        repo2.commit("relax without a reason")
        rc, out = repo2.flow("start")
        self.assertEqual(rc, 1)
        self.assertIn("needs a reason", out)

    def test_the_floor_guard_reads_the_plan_line_at_base(self):
        repo = Repo()
        self.addCleanup(repo.close)
        add_commands(repo, "Floor: allow config, reason: upgrading eslint")
        repo.commit("relax")
        base = repo.head()
        repo.path("setup.cfg").write_text("[flake8]\nmax-line-length = 200\n", encoding="utf-8")
        repo.commit("config")
        out, err = io.StringIO(), io.StringIO()
        self.assertEqual(floorguard.run(["f", "01", base], out.write, err.write, cwd=str(repo.dir)), 0, out.getvalue())


class UnsafeGate(unittest.TestCase):
    def test_gate_off_needs_unsafe_and_is_logged(self):
        repo = Repo()
        self.addCleanup(repo.close)
        add_commands(repo, "Gate: off")
        repo.commit("gate off")
        rc, out = repo.flow("start")
        self.assertEqual(rc, 1)
        self.assertIn("only as `Gate: off unsafe`", out)
        cmd = repo.path("plans/f/commands.md")
        cmd.write_text(cmd.read_text(encoding="utf-8").replace("Gate: off", "Gate: off unsafe"), encoding="utf-8")
        repo.commit("gate off unsafe")
        rc, out = repo.flow("start")
        self.assertEqual(rc, 0, out)
        self.assertIn("GATE-OFF-UNSAFE", repo.log())

    def test_the_report_and_eval_say_so(self):
        rows = report.parse("2026-11-01T10:00:00Z,-,GATE-OFF-UNSAFE\n2026-11-01T10:00:00Z,-,FLOOR-RELAXED-CONFIG\n"
                            "2026-11-01T10:00:01Z,-,START\n")
        self.assertIn("gate off (unsafe), floor relaxed: config", report.render("f", rows).splitlines()[0])
        self.assertEqual(evaluate.rebuilds_by_lane([(None, "01", "LEASE-2", ""), (None, "01", "REBUILD", ""),
                                                    (None, "02", "REBUILD", "")]), {"2": 1})


class Lanes(unittest.TestCase):
    def repo(self, lanes_line, tickets=(("01-a", "A", "—"), ("02-b", "B", "—"), ("03-c", "C", "—"))):
        repo = Repo(tickets=tickets)
        self.addCleanup(repo.close)
        for n, (slug, _, _) in enumerate(tickets, 1):
            path = repo.path("plans/f/tasks/%s.md" % slug)
            text = path.read_text(encoding="utf-8")
            path.write_text(text.replace("Status: open\n", "Status: open\nTouches: src/%s/\n" % slug, 1), encoding="utf-8")
        if lanes_line:
            add_commands(repo, lanes_line)
        repo.commit("plan")
        return repo

    def started(self, repo, **env):
        rc, out = repo.flow("start", **env)
        self.assertEqual(rc, 0, out)
        return repo.state().get("lanes", "")

    def test_auto_takes_the_width_capped_by_the_profile(self):
        self.assertEqual(self.started(self.repo("Lanes: `auto`")), "3")
        self.assertEqual(self.started(self.repo("Lanes: auto"), FLOW_PROFILE="careful"), "2")
        self.assertEqual(self.started(self.repo("Lanes: auto"), FLOW_PROFILE="fast"), "")  # fast batches
        repo = self.repo("Lanes: auto")
        self.started(repo)
        self.assertIn("LANES-AUTO-3", repo.log())

    def test_flow_lanes_wins_a_number_is_kept_and_no_line_is_one(self):
        self.assertEqual(self.started(self.repo("Lanes: auto"), FLOW_LANES="2"), "2")
        self.assertEqual(self.started(self.repo("Lanes: 2")), "2")
        self.assertEqual(self.started(self.repo("")), "")
        repo = self.repo("Lanes: many")
        rc, out = repo.flow("start")
        self.assertEqual(rc, 1)
        self.assertIn("Lanes: must be auto or 1 to 4, not many", out)


if __name__ == "__main__":
    unittest.main()
