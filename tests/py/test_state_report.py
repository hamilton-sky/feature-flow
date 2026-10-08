"""Ticket 02 of trusted-checks: the conductor reports the state it left, hashes the owner token,
and refuses `next`, `prompt` and `verdict` unless the runner called it (FLOW_TRUSTED=1)."""

import hashlib
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import helpers
from helpers import Repo

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import state  # the package under test, from this checkout

T1 = "plans/f/tasks/01-a.md"
STATE = ".feature-flow/state/flow-f.state"
FINDINGS = ".feature-flow/state/flow-f.findings"
REPORT = re.compile(r"^flow-state ([0-9a-f]{64}|none) ([0-9a-f]{64}|none)$")
REFUSED = "STOP run the conductor through scripts/flow-trust.py"


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Base(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.addCleanup(self.repo.close)

    def run_flow(self, *args, **env):
        full = {k: v for k, v in os.environ.items() if not k.startswith("FLOW_")}
        full.update(env)
        result = subprocess.run([sys.executable, "scripts/flow.py", "f"] + list(args), cwd=str(self.repo.dir),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, env=full)
        return result.returncode, result.stdout.strip(), result.stderr

    def on_disk(self, rel):
        path = self.repo.path(rel)
        return sha(path.read_bytes()) if path.is_file() else "none"

    def reported(self, err):
        lines = err.splitlines()
        self.assertTrue(lines, "stderr is empty")
        match = REPORT.match(lines[-1])
        self.assertIsNotNone(match, "the last stderr line is not a flow-state report: %r" % err)
        return match.group(1), match.group(2)

    def assertReportsDisk(self, err):
        self.assertEqual(self.reported(err), (self.on_disk(STATE), self.on_disk(FINDINGS)))


class Report(Base):
    def test_every_call_reports_the_files_it_left(self):
        rc, out, err = self.run_flow("start", FLOW_TRUSTED="1")
        self.assertEqual(rc, 0, out)
        token = out.split()[1]
        self.assertReportsDisk(err)
        self.assertNotEqual(self.reported(err)[0], "none")

        rc, out, err = self.run_flow("next", FLOW_TRUSTED="1", FLOW_SESSION=token)
        self.assertTrue(out.startswith("BUILD %s 01 " % T1), out)
        self.assertReportsDisk(err)

        reply = self.repo.dir.parent / (self.repo.dir.name + "-reply.txt")
        self.addCleanup(lambda: reply.unlink() if reply.exists() else None)
        reply.write_text("bad\nREVIEW: FAIL\n", encoding="utf-8")
        rc, out, err = self.run_flow("verdict", str(reply), FLOW_TRUSTED="1", FLOW_SESSION=token)
        self.assertEqual(rc, 2, "no review is pending yet: NoPhase")
        self.assertReportsDisk(err)

        self.repo.resolve(T1)
        rc, out, err = self.run_flow("next", FLOW_TRUSTED="1", FLOW_SESSION=token)
        self.assertTrue(out.startswith("REVIEW %s 01 " % T1), out)
        self.assertReportsDisk(err)

        rc, out, err = self.run_flow("verdict", str(reply), FLOW_TRUSTED="1", FLOW_SESSION=token)
        self.assertEqual((rc, out), (0, "OK"))
        self.assertTrue(self.repo.path(FINDINGS).is_file())
        self.assertReportsDisk(err)
        self.assertNotEqual(self.reported(err)[1], "none")

        rc, out, err = self.run_flow("next", FLOW_TRUSTED="1", FLOW_SESSION="wrong")
        self.assertEqual(rc, 1)
        self.assertTrue(out.startswith("STOP "), out)
        self.assertReportsDisk(err)
        self.assertNotEqual(self.reported(err)[1], "none", "a STOP reports the findings file it found")

        rc, out, err = self.run_flow("next", FLOW_TRUSTED="1", FLOW_SESSION=token)
        self.assertTrue(out.startswith("BUILD %s 01 " % T1), out)
        self.assertReportsDisk(err)

        rc, out, err = self.run_flow("reset", FLOW_TRUSTED="1", FLOW_TAKEOVER="1")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.reported(err), ("none", "none"))
        self.assertReportsDisk(err)

    def test_a_usage_error_during_a_run_reports_the_files_on_disk(self):
        rc, out, err = self.run_flow("start", FLOW_TRUSTED="1")
        token = out.split()[1]
        self.repo.path(FINDINGS).write_text("old findings\n", encoding="utf-8")
        for args in (("verdict",), ("bogus",), ("reset", "01", "extra")):
            rc, out, err = self.run_flow(*args, FLOW_TRUSTED="1", FLOW_SESSION=token)
            self.assertEqual(rc, 2, args)
            self.assertNotEqual(self.reported(err), ("none", "none"), args)
            self.assertReportsDisk(err)

    def test_a_state_file_that_is_not_utf8_stops_and_still_reports_both_files(self):
        rc, out, err = self.run_flow("start", FLOW_TRUSTED="1")
        token = out.split()[1]
        self.repo.path(FINDINGS).write_text("old findings\n", encoding="utf-8")
        self.repo.path(STATE).write_bytes(b"owner=\xff\xfe\n")
        rc, out, err = self.run_flow("next", FLOW_TRUSTED="1", FLOW_SESSION=token)
        self.assertEqual(rc, 1, err)
        self.assertTrue(out.startswith("STOP ") and "damaged" in out, out)
        self.assertNotIn("Traceback", err)
        self.assertReportsDisk(err)
        self.assertNotEqual(self.reported(err)[1], "none")

    def test_no_report_without_flow_trusted(self):
        rc, out, err = self.run_flow("start")
        self.assertEqual(rc, 0, out)
        self.assertNotIn("flow-state", err)


class OnlyTheConductorsFiles(unittest.TestCase):
    def test_other_files_with_the_same_suffix_do_not_change_the_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            state.SEEN.clear()
            state.save(Path(tmp) / "other.state", {"a": "1"})
            state.write_text(Path(tmp) / "other.findings", "x\n")
            state.load(Path(tmp) / "other.state")
            state.read_bytes(Path(tmp) / "other.findings")
            self.assertEqual(state.reported(), "none none")
            state.save(Path(tmp) / "flow-f.state", {"a": "1"}, kind="state")
            state.write_text(Path(tmp) / "flow-f.findings", "x\n", kind="findings")
            self.assertEqual(state.reported(), "%s %s" % (sha(b"a=1\n"), sha(b"x\n")))
            state.remove(Path(tmp) / "flow-f.findings", kind="findings")
            self.assertEqual(state.reported(), "%s none" % sha(b"a=1\n"))
            state.SEEN.clear()


class Owner(Base):
    def test_the_state_file_holds_only_the_hash_of_the_token(self):
        rc, out, err = self.run_flow("start", FLOW_TRUSTED="1")
        token = out.split()[1]
        text = self.repo.path(STATE).read_text(encoding="utf-8")
        self.assertEqual([line for line in text.splitlines() if token in line], [])
        self.assertEqual(self.repo.state()["owner"], sha(token.encode()))
        rc, out, err = self.run_flow("next", FLOW_TRUSTED="1", FLOW_SESSION=token)
        self.assertTrue(out.startswith("BUILD %s 01 " % T1), out)
        rc, out, err = self.run_flow("next", FLOW_TRUSTED="1", FLOW_SESSION=sha(token.encode()))
        self.assertEqual(rc, 1, "the stored hash is not a token")

    def test_an_old_raw_token_still_works_and_is_hashed_on_the_next_save(self):
        old = "0123456789abcdef"
        self.repo.path(".feature-flow/state").mkdir(parents=True)
        self.repo.path(STATE).write_text("owner=%s\nphase=\nsession_done=0\n" % old, encoding="utf-8")
        rc, out, err = self.run_flow("start", FLOW_TRUSTED="1")
        self.assertEqual(rc, 1)
        self.assertIn("owned by session 01234567.", out)
        self.assertNotIn(old, out, "a STOP prints only the first 8 characters of the owner")
        rc, out, err = self.run_flow("next", FLOW_TRUSTED="1", FLOW_SESSION=old)
        self.assertTrue(out.startswith("BUILD %s 01 " % T1), out)
        self.assertEqual(self.repo.state()["owner"], sha(old.encode()))
        rc, out, err = self.run_flow("next", FLOW_TRUSTED="1", FLOW_SESSION=old)
        self.assertEqual(rc, 0, out)

    def test_a_stop_for_another_session_shows_eight_characters(self):
        rc, out, err = self.run_flow("start", FLOW_TRUSTED="1")
        token = out.split()[1]
        owner = sha(token.encode())
        rc, out, err = self.run_flow("next", FLOW_TRUSTED="1", FLOW_SESSION="wrong")
        self.assertIn("owned by another session (%s)" % owner[:8], out)
        self.assertNotIn(owner[:9], out)
        rc, out, err = self.run_flow("reset")
        self.assertIn("owned by session %s." % owner[:8], out)


class Refuse(Base):
    def test_loop_commands_need_the_runner(self):
        rc, out, err = self.run_flow("start")
        self.assertEqual(rc, 0, out)
        token = out.split()[1]
        for args in (("next",), ("prompt",), ("verdict", "reply.txt")):
            rc, out, err = self.run_flow(*args, FLOW_SESSION=token)
            self.assertEqual(rc, 1, args)
            self.assertTrue(out.startswith(REFUSED), out)
            self.assertEqual(out, REFUSED + ", as the skill says")
        self.assertNotIn("phase=build", self.repo.path(STATE).read_text(encoding="utf-8"))

    def test_start_reset_and_planning_stay_allowed(self):
        self.assertEqual(self.run_flow("start")[0], 0)
        rc, out, err = self.run_flow("reset", FLOW_TAKEOVER="1")
        self.assertEqual(rc, 0, out)
        rc, out, err = self.run_flow("plan-accept")
        self.assertNotIn(REFUSED, out)


if __name__ == "__main__":
    unittest.main()
