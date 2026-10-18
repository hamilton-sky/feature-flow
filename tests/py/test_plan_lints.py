"""The plan checks that keep tickets few and Done when honest: a plan of more than 8 tickets, a run of chained
tickets in one package, an escape clause, a check that expects output its command cannot print, and a ticket
that uses what another ticket creates without waiting for it."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import helpers
from helpers import Repo

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import prompts, status  # the package under test, from this checkout

CHECKED = "\n```check\n$ true\n```\n"


class Out:
    def __init__(self):
        self.text = ""

    def write(self, text):
        self.text += text


class PlanLints(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        subprocess.run(["git", "init", "-q"], check=True)
        Path("existing.py").write_text("def parse_config():\n    pass\n", encoding="utf-8")
        subprocess.run(["git", "add", "existing.py"], check=True)
        self.plan = Path("plans/f")
        (self.plan / "tasks").mkdir(parents=True)
        (self.plan / "commands.md").write_text("# Commands: f\n\nTest: `python3 -c pass`\n", encoding="utf-8")

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def ticket(self, num, blocked="—", header="", body="body", done="- x", check=CHECKED):
        text = ("# T%d\n\nType: task\nStatus: open\nBlocked by: %s\nTest first: no\n%s\n%s\n\n## Done when\n\n%s\n%s"
                "\n## Answer\n" % (num, blocked, header, body, done, check))
        (self.plan / "tasks" / ("%02d-t.md" % num)).write_text(text, encoding="utf-8")

    def run_status(self, mode="--lint"):
        out, err = Out(), Out()
        code = status.run(["f", mode], out, err)
        return code, out.text + err.text

    # ---- size ----------------------------------------------------------

    def test_more_than_eight_tickets_warns(self):
        for n in range(1, 10):
            self.ticket(n)
        code, out = self.run_status("--check")
        self.assertEqual(code, 0, out)
        self.assertIn("warning: 9 tickets to build in one plan. aim for 4 to 6", out)

    def test_eight_tickets_do_not(self):
        for n in range(1, 9):
            self.ticket(n)
        self.assertNotIn("tickets to build in one plan", self.run_status("--check")[1])

    def test_three_chained_tickets_in_one_package_warn(self):
        self.ticket(1, header="Touches: src/api/models.py, tests/test_models.py")
        self.ticket(2, "01", header="Touches: src/api/service.py")
        self.ticket(3, "02", header="Touches: `src/api/**`")
        self.ticket(4, "03", header="Touches: web/app.js")
        out = self.run_status("--check")[1]
        self.assertIn("warning: 01, 02, 03 are chained one after another and all change `src/api`", out)
        self.assertNotIn("04", out.split("chained")[0])

    def test_a_chain_across_packages_or_with_a_gap_does_not(self):
        self.ticket(1, header="Touches: src/api/models.py")
        self.ticket(2, "01", header="Touches: web/app.js")
        self.ticket(3, "02", header="Touches: src/api/service.py")
        self.ticket(5, "03", header="Touches: src/api/x.py")
        self.assertNotIn("chained", self.run_status("--check")[1])

    def test_without_touches_the_description_names_the_package_and_tests_do_not_count(self):
        for n in (1, 2, 3):
            self.ticket(n, "—" if n == 1 else "%02d" % (n - 1),
                        body="Change `lib/core/step%d.py` and `tests/test_step%d.py`." % (n, n))
        self.assertIn("are chained one after another and all change `lib/core`", self.run_status("--check")[1])

    def test_package_names(self):
        self.assertEqual([status.package(p) for p in ("src/api/**", "src/api/x.py", "feature_flow/gate.py",
                                                       "README.md", "a/b/c/d.py", "*.md")],
                         ["src/api", "src/api", "feature_flow", ".", "a/b", "."])

    # ---- Done when -----------------------------------------------------

    def test_an_escape_clause_in_done_when_warns(self):
        self.ticket(1, done="- `tool count` reports 24 converted; if the counts differ, explain why")
        self.ticket(2, done="- all tests pass where possible")
        out = self.run_status()[1]
        self.assertIn("01: Done when has an escape clause", out)
        self.assertIn("02: Done when has an escape clause (`where possible`)", out)

    def test_plain_done_when_bullets_pass(self):
        self.ticket(1, done="- `tool count` reports 24 converted and 0 left alone")
        self.assertEqual(self.run_status(), (0, "OK: 1 tickets, 1 ready now\n"))

    def test_a_quiet_command_cannot_print(self):
        self.ticket(1, check="```check\n$ grep -q needle haystack.txt\nprints needle\n```\n")
        self.ticket(2, check="```check\n$ python3 x.py > /dev/null 2>&1\nprints done\n```\n")
        self.ticket(3, check="```check\n$ grep needle haystack.txt\nprints needle\n```\n")
        out = self.run_status()[1]
        self.assertIn("01: check `$ grep -q needle haystack.txt` expects `needle`, but the command prints nothing", out)
        self.assertIn("02: check `$ python3 x.py > /dev/null 2>&1` expects `done`", out)
        self.assertNotIn("03: check", out)

    def test_a_test_runner_prints_only_its_summary(self):
        self.ticket(1, check="```check\n$ python3 -m pytest -q tests/test_save.py\nprints 714 steps saved\n```\n")
        self.ticket(2, check="```check\n$ python3 -m pytest -q tests/test_save.py\nprints 3 passed\n```\n")
        self.ticket(3, check="```check\n$ python3 -m pytest -s tests/test_save.py\nprints 714 steps saved\n```\n")
        self.ticket(4, check="```check\n$ python3 -m unittest discover -s tests\nprints OK\n```\n")
        out = self.run_status()[1]
        self.assertIn("01: check `$ python3 -m pytest -q tests/test_save.py` expects `714 steps saved`, which that "
                      "command does not print", out)
        for lab in ("02", "03", "04"):
            self.assertNotIn("%s: check" % lab, out)

    def test_an_unreadable_check_block_fails_the_lint(self):
        self.ticket(1, check="```check\nprints first\n```\n")
        code, out = self.run_status()
        self.assertEqual(code, 1)
        self.assertIn("01: check block:", out)

    # ---- what one ticket creates and another uses ------------------------

    def test_a_ticket_that_uses_a_new_file_must_wait_for_it(self):
        self.ticket(1, body="Add the new `src/steps.py` with the converter.")
        self.ticket(2, body="Call the converter in `src/steps.py` from the save path.")
        out = self.run_status()[1]
        self.assertIn("02: uses `src/steps.py`, which ticket 01 creates, but is not blocked by it", out)
        self.assertNotIn("names `src/steps.py`, which does not exist", out)
        self.ticket(2, "01", body="Call the converter in `src/steps.py` from the save path.")
        self.assertNotIn("uses `src/steps.py`", self.run_status()[1])

    def test_a_ticket_that_uses_a_new_name_must_wait_for_it(self):
        self.ticket(1, body="Add `redact_secrets()` to the draft writer.")
        self.ticket(2, body="Run every draft through `redact_secrets()` before it is stored.")
        self.ticket(3, body="Change `parse_config()` to read the new key.")
        self.ticket(4, body="Add a flag to `parse_config()`.")
        out = self.run_status()[1]
        self.assertIn("02: uses `redact_secrets()`, which ticket 01 creates, but is not blocked by it", out)
        self.assertNotIn("parse_config", out)  # it exists already: neither ticket creates it

    def test_a_path_nobody_creates_still_warns_that_it_is_missing(self):
        self.ticket(1, body="Read `src/missing.py`.")
        self.assertIn("01: names `src/missing.py`, which does not exist here", self.run_status()[1])


class ClassOfDefect(unittest.TestCase):
    def test_a_class_finding_tells_the_builder_to_fix_every_site(self):
        repo = Repo()
        self.addCleanup(repo.close)
        import shutil
        for folder in ("agents", "guides"):
            shutil.copytree(str(helpers.ROOT / folder), str(repo.path(folder)))
        repo.commit("guides")
        env = {"FLOW_SESSION": repo.flow("start")[1].split()[1]}
        repo.flow("next", **env)
        repo.resolve("plans/f/tasks/01-a.md")
        repo.flow("next", **env)
        reply = repo.dir.parent / (repo.dir.name + "-reply.txt")
        self.addCleanup(reply.unlink, missing_ok=True)
        reply.write_text("1. major ui.py: shows a raw id - show the name class: raw ids on screen\nREVIEW: FAIL\n",
                         encoding="utf-8")
        repo.flow("verdict", str(reply), **env)
        rc, out = repo.flow("next", **env)
        self.assertTrue(out.startswith("BUILD"), out)
        self.assertIn(prompts.CLASS_FIX, repo.flow("prompt", **env)[1])

    def test_an_instance_finding_does_not(self):
        text = prompts.build("build", helpers.ROOT / "scripts", "f", "plans/f/tasks/01-a.md", "01", "abc", retry=True)
        self.assertNotIn(prompts.CLASS_FIX, text)


if __name__ == "__main__":
    unittest.main()
