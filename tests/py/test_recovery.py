"""0.41.0, recoverable stops: regression tests for the stops of the portable-live-page field run.

- a stale TRUST digest with unchanged files is told apart from files that really changed, and from missing or
  inconsistent evidence ("cannot determine"), and only the first has a way on (FLOW_TRUST_ACCEPT=saved-state);
- `doctor` says where the run stands and changes nothing;
- `resume` shows what it would do (--dry-run), accepts changed flow code only when told (--accept-code), keeps a live
  owner, and keeps pending work: uncommitted files, findings, the ticket's start;
- repair mode: a consult on an existing plan during a repair, warnings the plan already had (inherited) shown but not
  blocking, new ones blocking, the baseline tied to the plan's tree at the repair's start, the footprint each ticket
  gains listed;
- timing: the test-first check's time is logged, and eval reports gate runs and finding-to-fix minutes.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

import helpers
import test_proof
import test_trust_runner
from test_proof import T1

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import evaluate  # the package under test, from this checkout

STATE = test_trust_runner.STATE
LIST = ".feature-flow/state/flow-f.trust"


class Trust(test_trust_runner.Base):
    """The field run passed the TRUST digest of the call before the last one: the runner said files changed, and its
    list named none of them."""

    def prepare(self):
        shutil.copy(str(helpers.ROOT / "scripts" / "flow-status.py"), str(self.repo.path("scripts")))

    def stale(self):
        """Two calls in: (the older digest, the latest)."""
        self.begin()
        older = self.digest
        rc, lines, err = self.passed("next")  # writes the run state again: a new digest
        self.assertNotEqual(older, self.digest)
        return older, self.digest

    def test_a_stale_digest_with_unchanged_files_says_so(self):
        older, latest = self.stale()
        rc, out, err = self.trust("f", "next", FLOW_TRUST=older, FLOW_SESSION=self.token)
        self.assertEqual(rc, 1, (out, err))
        first = out.splitlines()[0]
        self.assertTrue(first.startswith("STOP the TRUST digest you passed looks like an older one"), first)
        self.assertIn("checked against the digest itself", first)
        self.assertIn("FLOW_TRUST_ACCEPT=saved-state", first)
        self.assertNotIn("flow files changed", first)

    def test_a_stale_digest_is_accepted_on_the_users_yes_and_the_call_runs(self):
        older, latest = self.stale()
        rc, out, err = self.trust("f", "prompt", FLOW_TRUST=older, FLOW_SESSION=self.token,
                                  FLOW_TRUST_ACCEPT="saved-state")
        lines = out.splitlines()
        self.assertRegex(lines[0], test_trust_runner.TRUST, (out, err))
        self.assertTrue(lines[1].startswith("TRUST-ACCEPTED saved-state:"), lines)
        self.assertTrue(lines[2:], lines)  # the conductor ran and answered
        self.assertFalse(lines[2].startswith(("STOP the TRUST", "STOP flow files")), lines)
        self.digest = test_trust_runner.TRUST.match(lines[0]).group(1)
        self.assertGoesOn()  # and its new digest is the one to pass from now on

    def test_files_that_really_changed_are_named_and_never_accepted(self):
        older, latest = self.stale()
        self.append(self.repo.path("feature_flow/conductor/facade.py"))
        for digest in (latest, older):  # the code half of both is the saved list's: the names are proven
            rc, out, err = self.trust("f", "next", FLOW_TRUST=digest, FLOW_SESSION=self.token,
                                      FLOW_TRUST_ACCEPT="saved-state")
            self.assertEqual(rc, 1, (digest, out, err))
            first = out.splitlines()[0]
            self.assertTrue(first.startswith(test_trust_runner.CHANGED), first)
            self.assertEqual(first, test_trust_runner.CHANGED + " feature_flow/conductor/facade.py")
            self.assertNotIn("TRUST-ACCEPTED", out)

    def test_a_digest_from_before_a_code_change_cannot_determine(self):
        older, latest = self.stale()
        self.append(self.repo.path("feature_flow/conductor/facade.py"))
        rc, out, err = self.trust("f", "--diagnose", FLOW_TRUST=latest)
        self.assertTrue(out.startswith("TRUST-DIAGNOSIS changed"), out)
        rc, lines, err = self.passed("prompt", FLOW_TRUST="new")  # the user accepted the change: a fresh digest
        rc, out, err = self.trust("f", "next", FLOW_TRUST=older, FLOW_SESSION=self.token)
        self.assertEqual(rc, 1, (out, err))
        self.assertIn("the evidence cannot say why", out.splitlines()[0])
        self.assertIn("from before an accepted change", out.splitlines()[0])

    def test_missing_evidence_cannot_determine_and_offers_no_way_on(self):
        older, latest = self.stale()
        self.repo.path(LIST).unlink()
        rc, out, err = self.trust("f", "next", FLOW_TRUST=older, FLOW_SESSION=self.token,
                                  FLOW_TRUST_ACCEPT="saved-state")
        self.assertEqual(rc, 1, (out, err))
        first = out.splitlines()[0]
        self.assertTrue(first.startswith("STOP the TRUST digest does not match, and the evidence cannot say why"), first)
        self.assertIn("no saved list", first)
        self.assertIn("feature-flow doctor f", first)
        self.assertNotIn("FLOW_TRUST_ACCEPT", first)

    def test_an_accepted_state_is_shown(self):
        older, latest = self.stale()
        rc, out, err = self.trust("f", "prompt", FLOW_TRUST=older, FLOW_SESSION=self.token,
                                  FLOW_TRUST_ACCEPT="saved-state")
        self.assertIn("accepted the run state phase=build num=01", out.splitlines()[1])

    def test_a_run_state_that_is_not_what_was_saved_cannot_be_accepted(self):
        older, latest = self.stale()
        self.append(self.repo.path(STATE), "phase=\n")
        rc, out, err = self.trust("f", "next", FLOW_TRUST=older, FLOW_SESSION=self.token,
                                  FLOW_TRUST_ACCEPT="saved-state")
        self.assertEqual(rc, 1, (out, err))
        self.assertIn("the run state is not what the last conductor call saved", out.splitlines()[0])

    def test_a_state_edit_after_the_latest_digest_is_named(self):
        older, latest = self.stale()
        self.append(self.repo.path(STATE), "phase=\n")
        rc, out, err = self.trust("f", "next", FLOW_TRUST=latest, FLOW_SESSION=self.token)
        self.assertEqual(out.splitlines()[0], test_trust_runner.CHANGED + " " + STATE)

    def test_a_malformed_digest_is_named(self):
        self.begin()
        rc, out, err = self.trust("f", "next", FLOW_TRUST="TRUST abc", FLOW_SESSION=self.token)
        self.assertEqual(rc, 1, (out, err))
        self.assertIn("is not a TRUST digest", out)

    def test_diagnose_runs_nothing_and_writes_nothing(self):
        older, latest = self.stale()
        before = {p: p.read_bytes() for p in self.repo.path(".feature-flow/state").iterdir() if p.is_file()}
        for digest, kind in ((older, "stale"), (latest, "ok")):
            rc, out, err = self.trust("f", "--diagnose", FLOW_TRUST=digest)
            self.assertEqual(rc, 0, (out, err))
            self.assertTrue(out.startswith("TRUST-DIAGNOSIS %s " % kind), out)
        rc, out, err = self.trust("f", "--diagnose")
        self.assertTrue(out.startswith("TRUST-DIAGNOSIS nodigest nothing changed") or
                        out.startswith("TRUST-DIAGNOSIS nodigest no digest given"), out)
        after = {p: p.read_bytes() for p in self.repo.path(".feature-flow/state").iterdir() if p.is_file()}
        self.assertEqual(before, after)

    def test_doctor_names_a_stale_digest_and_the_way_on(self):
        older, latest = self.stale()
        rc, out = doctor(self.repo, "--trust", older, scripts=True)
        self.assertEqual(rc, 0, out)
        self.assertIn("trust        stale:", out)
        self.assertIn("next         the digest from the last TRUST line", out)


def tree_bytes(folder):
    """{relative path: sha256} of every file under folder, .git included."""
    found = {}
    for path in sorted(Path(folder).rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            found[path.relative_to(folder).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def doctor(repo, *args, scripts=False):
    """`flow-status.py f --doctor` in repo (its own copy of the package); returns (exit code, stdout)."""
    folder = repo.path("scripts")
    if not (folder / "flow-status.py").is_file():
        shutil.copy(str(helpers.ROOT / "scripts" / "flow-status.py"), str(folder))
    env = {k: v for k, v in os.environ.items() if not k.startswith("FLOW_")}
    result = subprocess.run([sys.executable, "scripts/flow-status.py", "f", "--doctor"] + list(args),
                            cwd=str(repo.dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            universal_newlines=True, env=env)
    return result.returncode, result.stdout + result.stderr


class Recovery(unittest.TestCase):
    setUp = test_proof.TestFirst.setUp
    tearDown = test_proof.TestFirst.tearDown
    prepare = test_proof.TestFirst.prepare
    write = test_proof.TestFirst.write
    resolve_with = test_proof.TestFirst.resolve_with
    findings = test_proof.TestFirst.findings

    def commit_scripts(self):
        for name in ("flow-status.py", "flow-trust.py"):
            shutil.copy(str(helpers.ROOT / "scripts" / name), str(self.repo.path("scripts")))
        self.repo.path(".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        self.repo.commit("scripts")

    def sent_back(self):
        """Ticket 01 built, then sent back by the test-first check: its findings are in the ticket."""
        self.prepare()
        self.resolve_with("code.txt")
        rc, out = self.repo.flow("next")
        self.assertTrue(out.startswith("BUILD %s 01 " % T1), out)
        self.assertIn("## Review findings (round 1, test first)", self.findings())

    def test_doctor_is_read_only_and_says_where_the_run_stands(self):
        self.commit_scripts()
        self.sent_back()
        self.repo.path("loose.txt").write_text("x\n", encoding="utf-8")
        before = tree_bytes(self.repo.dir)
        rc, out = doctor(self.repo)
        self.assertEqual(rc, 0, out)
        self.assertEqual(before, tree_bytes(self.repo.dir))
        for text in ("doctor for f (read-only: nothing was changed)", "run          phase build, ticket 01",
                     "last step", "start        ticket 01 starts at", "findings     01-a has 1 findings section(s), the last round 1 (test first)",
                     "uncommitted  loose.txt", "flow code    unchanged since the ticket was picked",
                     "next         git status"):
            self.assertIn(text, out)

    def test_doctor_with_no_run_and_no_plan(self):
        self.commit_scripts()
        shutil.rmtree(str(self.repo.path("plans/f")))
        self.repo.commit("no plan")
        rc, out = doctor(self.repo)
        self.assertEqual(rc, 0, out)
        self.assertIn("plan         missing", out)
        self.assertIn("next         /feature-flow f", out)

    def test_the_dry_run_changes_nothing_and_says_what_resume_would_do(self):
        self.sent_back()
        self.failing = self.repo.head()
        before = tree_bytes(self.repo.dir)
        rc, out = self.repo.flow("resume", "--dry-run")
        self.assertEqual(rc, 0, out)
        self.assertTrue(out.startswith("PLAN "), out)
        self.assertIn("ticket 01 would carry on in its build phase from", out)
        self.assertIn("the findings, attempt notes and tickets stay as they are", out)
        self.assertIn("nothing was changed. to do it: feature-flow resume f", out)
        self.assertEqual(before, tree_bytes(self.repo.dir))

    def test_resume_keeps_the_findings_and_never_discards_uncommitted_work(self):
        self.sent_back()
        self.repo.path("half-done.txt").write_text("work in progress\n", encoding="utf-8")
        rc, out = self.repo.flow("resume")
        self.assertEqual(rc, 1, out)
        self.assertIn("resume never discards work", out)
        self.assertEqual(self.repo.path("half-done.txt").read_text(encoding="utf-8"), "work in progress\n")
        self.repo.commit("wip")
        rc, out = self.repo.flow("resume")
        self.assertEqual(rc, 0, out)
        self.assertIn("## Review findings (round 1, test first)", self.findings())
        self.assertIn("wip", out)  # its commits since the start still count for it

    def test_changed_flow_code_is_accepted_only_with_accept_code(self):
        self.prepare()
        flow = self.repo.path("feature_flow/__init__.py")
        flow.write_text(flow.read_text(encoding="utf-8") + "\n# upgraded\n", encoding="utf-8")
        self.repo.git("update-index", "--assume-unchanged", "feature_flow/__init__.py")  # an upgrade outside git
        code_sha = self.repo.state()["code_sha"]
        rc, out = self.repo.flow("resume")
        self.assertEqual(rc, 1, out)
        self.assertIn("the flow code changed since this ticket was picked: feature_flow/__init__.py", out)
        self.assertIn("feature-flow resume f --dry-run", out)
        self.assertIn("feature-flow resume f --accept-code", out)
        self.assertEqual(self.repo.state()["code_sha"], code_sha)
        rc, out = self.repo.flow("resume", "--dry-run")
        self.assertIn("would accept the flow code as it is now (changed: feature_flow/__init__.py)", out)
        self.assertEqual(self.repo.state()["code_sha"], code_sha)
        rc, out = self.repo.flow("resume", "--accept-code")
        self.assertEqual(rc, 0, out)
        self.assertIn("accepted the flow code as it is now", out)
        self.assertNotEqual(self.repo.state()["code_sha"], code_sha)

    def test_resume_keeps_a_live_owner(self):
        self.prepare()
        rc, out = self.repo.flow("start")
        token = out.split()[1]
        owner = self.repo.state()["owner"]
        rc, out = self.repo.flow("resume")  # as a stop prints it, from a terminal: no token
        self.assertEqual(rc, 0, out)
        self.assertIn("session %s still owns the feature and carries on with it" % owner[:8], out)
        self.assertEqual(self.repo.state()["owner"], owner)
        rc, out = self.repo.flow("next", FLOW_SESSION=token)
        self.assertEqual(rc, 0, out)


def ticket(title, status, touches, extra=""):
    return ("# %s\n\nType: task\nStatus: %s\nBlocked by: —\nTest first: no\nLevel: 2\nTouches: %s\n%s\nbody\n\n"
            "## Done when\n\n- x\n\n```check\n$ %s -c \"print('fine')\"\nprints fine\n```\n\n## Answer\n"
            % (title, status, touches, extra, sys.executable))


class Repair(unittest.TestCase):
    """Ticket 02 of the field run was resolved with two lint warnings; ticket 03's repair needed two files more and an
    architect's view, and the repair rules forbade editing 02."""

    def setUp(self):
        self.repo = helpers.Repo(tickets=())
        tasks = self.repo.path("plans/f/tasks")
        self.repo.path("src").mkdir()
        for name in ("a.py", "server.py", "storage.py"):
            self.repo.path("src/" + name).write_text("x = 1\n", encoding="utf-8")
        (tasks / "01-done.md").write_text(ticket("Done", "resolved", "`src/a.py`",
                                                 "See `src/gone.py` for the old one.\n"), encoding="utf-8")
        (tasks / "02-repair.md").write_text(ticket("Repair me", "open", "`src/a.py`"), encoding="utf-8")
        self.repo.path("plans/f/commands.md").write_text("# Commands: f\n\nTest: `%s -c \"pass\"`\n" % sys.executable,
                                                         encoding="utf-8")
        self.repo.commit("plan")
        for name in ("flow-status.py",):
            shutil.copy(str(helpers.ROOT / "scripts" / name), str(self.repo.path("scripts")))
        for folder in ("agents", "guides"):
            shutil.copytree(str(helpers.ROOT / folder), str(self.repo.path(folder)))
        self.repo.path(".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        self.repo.commit("layout")
        rc, out = self.repo.flow("next")
        self.assertTrue(out.startswith("BUILD plans/f/tasks/02-repair.md 02 "), out)
        rc, out = self.repo.flow("replan-prompt", "repair")
        self.assertEqual(rc, 0, out)
        self.prompt = out
        self.start = self.repo.state()["repair_sha"]

    def tearDown(self):
        self.repo.close()

    def widen(self, *paths):
        path = self.repo.path("plans/f/tasks/02-repair.md")
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("Touches: `src/a.py`", "Touches: " + ", ".join("`%s`" % p for p in ("src/a.py",) + paths)),
                        encoding="utf-8")

    def test_the_repair_prompt_names_the_baseline_and_its_check(self):
        self.assertIn("--lint --baseline %s" % self.start, self.prompt)
        self.assertIn("inherited", self.prompt)
        self.assertEqual(self.repo.state()["repair_plan"], self.repo.git("rev-parse", "%s:plans/f" % self.start))

    def test_inherited_warnings_show_but_do_not_block_and_the_footprint_is_listed(self):
        self.widen("src/server.py", "src/storage.py")
        rc, out = self.repo.flow("repair-check")
        self.assertEqual(rc, 0, out)
        lines = out.splitlines()
        self.assertEqual(lines[0], "OK repair check of f", out)
        self.assertIn("footprint: 02: + src/server.py, + src/storage.py", lines)
        self.assertIn("inherited warning: 01: names `src/gone.py`, which does not exist here (say `new` if it will "
                      "be created)", lines)
        self.assertIn("OK: the repair adds no problem (1 inherited, shown above, do not block it)", lines)
        self.repo.commit("plan(f): repair the plan")
        rc, out = self.repo.flow("next")
        self.assertTrue(out.startswith("BUILD plans/f/tasks/02-repair.md 02 "), out)
        log = self.repo.log()
        self.assertIn("REPAIR-FOOTPRINT 02: + src/server.py, + src/storage.py", log)
        self.assertIn("REPAIR-INHERITED 1", log)
        self.assertIn(",REPAIR\n", log)

    def test_a_new_warning_blocks_until_a_fix_is_committed(self):
        self.widen("src/server.py", "src/missing.py")
        rc, out = self.repo.flow("repair-check")
        self.assertTrue(out.startswith("BLOCKED repair check of f"), out)
        self.assertIn("new warning: 02: names `src/missing.py`", out)
        self.repo.commit("plan(f): repair the plan")
        rc, out = self.repo.flow("next")
        self.assertEqual(rc, 1, out)
        self.assertIn("the plan repair adds problems the plan did not have: 02: names `src/missing.py`", out)
        self.assertTrue(self.repo.state().get("repair_sha"))  # still pending: the next `next` checks again
        path = self.repo.path("plans/f/tasks/02-repair.md")
        path.write_text(path.read_text(encoding="utf-8").replace(", `src/missing.py`", ""), encoding="utf-8")
        self.repo.commit("plan(f): fix the repair")
        rc, out = self.repo.flow("next")
        self.assertTrue(out.startswith("BUILD plans/f/tasks/02-repair.md 02 "), out)

    def test_the_lint_baseline_command_matches(self):
        self.widen("src/missing.py")
        result = subprocess.run([sys.executable, "scripts/flow-status.py", "f", "--lint", "--baseline", self.start],
                                cwd=str(self.repo.dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("inherited warning: 01: names `src/gone.py`", result.stdout)
        self.assertIn("new warning: 02: names `src/missing.py`", result.stdout)
        result = subprocess.run([sys.executable, "scripts/flow-status.py", "f", "--lint", "--baseline", "nope"],
                                cwd=str(self.repo.dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("cannot read the baseline", result.stderr)

    def test_the_baseline_is_tied_to_the_recorded_plan_tree(self):
        state = self.repo.path(".feature-flow/state/flow-f.state")
        text = state.read_text(encoding="utf-8")
        tree = self.repo.state()["repair_plan"]
        state.write_text(text.replace("repair_plan=" + tree, "repair_plan=" + "0" * 40), encoding="utf-8")
        rc, out = self.repo.flow("repair-check")
        self.assertEqual(rc, 1, out)
        self.assertIn("cannot tell the repair's baseline", out)

    def test_a_resolved_ticket_changed_by_the_repair_blocks(self):
        path = self.repo.path("plans/f/tasks/01-done.md")
        path.write_text(path.read_text(encoding="utf-8").replace("See `src/gone.py` for the old one.\n", ""),
                        encoding="utf-8")
        rc, out = self.repo.flow("repair-check")
        self.assertTrue(out.startswith("BLOCKED"), out)
        self.assertIn("resolved ticket changed: plans/f/tasks/01-done.md", out)

    def test_a_blocked_repair_keeps_its_baseline_through_another_round(self):
        self.widen("src/missing.py")
        self.repo.commit("plan(f): repair the plan")
        rc, out = self.repo.flow("next")
        self.assertEqual(rc, 1, out)
        rc, out = self.repo.flow("replan-prompt", "repair")  # the planner is sent back with the new problem
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.repo.state()["repair_sha"], self.start)
        rc, out = self.repo.flow("repair-check")
        self.assertTrue(out.startswith("BLOCKED"), out)
        self.assertIn("new warning: 02: names `src/missing.py`", out)

    def test_a_third_copy_of_an_inherited_problem_is_new(self):
        from feature_flow.plan import repaircheck
        self.assertEqual(repaircheck.split(["a", "a", "b"], ["a", "b"]), (["a", "b"], ["a"]))

    def test_a_resolved_ticket_change_ends_the_report_blocked(self):
        path = self.repo.path("plans/f/tasks/01-done.md")
        path.write_text(path.read_text(encoding="utf-8").replace("# Done\n", "# Done again\n", 1), encoding="utf-8")
        rc, out = self.repo.flow("repair-check")
        self.assertTrue(out.splitlines()[-1].startswith("BLOCKED: the repair adds 1 problem(s)"), out)

    def test_a_consult_on_the_existing_plan_works_during_a_repair(self):
        question = self.repo.path(".feature-flow/state/ask-f-repair.md")
        question.write_text("architect: may the fix change both server.py and storage.py?\n", encoding="utf-8")
        rc, out = self.repo.flow("consult-prompt", "architect", str(question))
        self.assertEqual(rc, 0, out)
        self.assertIn("the planner repairing the plan of the feature `f`", out)
        self.assertIn("The plan exists and stays", out)
        self.assertNotIn("already exists", out)
        self.assertIn("CONSULT-ARCHITECT-REPAIR", self.repo.log())
        answers = self.repo.path(".feature-flow/state/ask-f-repair-answers.md")
        answers.write_text("architect: yes, both, in one ticket.\n", encoding="utf-8")
        rc, out = self.repo.flow("replan-prompt", "repair", str(answers))
        self.assertEqual(rc, 0, out)
        self.assertIn("## Consulted", out)
        self.assertIn("architect: yes, both, in one ticket.", out)
        self.assertEqual(self.repo.state()["repair_sha"], self.start)  # a second round keeps the baseline

    def test_a_consult_on_an_existing_plan_without_a_repair_says_what_to_do(self):
        self.repo.flow("resume")  # drops the repair, which committed nothing
        self.assertFalse(self.repo.state().get("repair_sha"))
        question = self.repo.path(".feature-flow/state/ask-f-repair.md")
        question.write_text("architect: anything?\n", encoding="utf-8")
        rc, out = self.repo.flow("consult-prompt", "architect", str(question))
        self.assertEqual(rc, 1, out)
        self.assertIn("a consult on an existing plan is for repairing it: run replan-prompt repair first", out)
        self.assertNotIn("pick another name", out)


class Timing(unittest.TestCase):
    def rows(self, lines):
        return evaluate.timed("\n".join(lines))

    def test_finding_to_fix_minutes(self):
        rows = self.rows([
            "2026-11-14T10:00:00Z,02,BUILD", "2026-11-14T10:05:00Z,02,REVIEW", "2026-11-14T10:10:00Z,02,VERDICT-FAIL",
            "2026-11-14T10:11:00Z,02,BUILD", "2026-11-14T10:20:00Z,02,GATE-TIME Test=300 Lint=4",
            "2026-11-14T10:24:00Z,02,REVIEW", "2026-11-14T10:30:00Z,02,VERDICT-PASS",
            "2026-11-14T10:31:00Z,03,BUILD", "2026-11-14T10:40:00Z,03,TESTFIRST-TIME 420",
            "2026-11-14T10:41:00Z,03,TESTFIRST-FAIL",
        ])
        tm = evaluate.timing(rows, {"02": {}, "03": {}})
        fix = tm["finding_to_fix"]
        self.assertEqual((fix["findings"], fix["open"]), (2, 1))
        self.assertEqual(fix["each"][0], {"ticket": "02", "check": "VERDICT-FAIL", "to_review": 14.0, "to_fix": 20.0})
        self.assertEqual(fix["median_to_fix_minutes"], 20.0)
        self.assertEqual(tm["gate_runs"]["median_seconds"], 304)
        self.assertEqual(tm["testfirst_runs"]["longest_seconds"], 420)

    def test_two_findings_fixed_by_one_pass_are_both_fixed(self):
        rows = self.rows(["2026-11-14T10:00:00Z,02,TESTFIRST-FAIL", "2026-11-14T10:02:00Z,02,GATE-FAIL",
                          "2026-11-14T10:10:00Z,02,REVIEW", "2026-11-14T10:12:00Z,02,VERDICT-PASS"])
        fix = evaluate.timing(rows, {"02": {}})["finding_to_fix"]
        self.assertEqual((fix["findings"], fix["open"]), (2, 0))

    def test_the_test_first_check_logs_its_time(self):
        case = Recovery("test_resume_keeps_a_live_owner")
        case.setUp()
        try:
            case.sent_back()
            self.assertRegex(case.repo.log(), r",01,TESTFIRST-TIME \d+\n")
        finally:
            case.tearDown()


if __name__ == "__main__":
    unittest.main()
