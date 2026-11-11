import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import checks, gate, proc  # the package under test, from this checkout


def timeless(text):
    """text with every duration (`3s`, `4m12s`) as `Ns`, so a line that says how long a command took compares."""
    return re.sub(r"\b\d+m\d\ds\b|\b\d+s\b", "Ns", text)


@unittest.skipUnless(shutil.which("bash") and os.name != "nt",
                     "these commands are bash syntax; the gate runs commands through cmd.exe on Windows")
class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "plans" / "f").mkdir(parents=True)
        self.cwd = os.getcwd()
        self.flow_dir = os.environ.pop("FLOW_DIR", None)
        os.chdir(str(self.dir))

    def tearDown(self):
        os.chdir(self.cwd)
        if self.flow_dir is not None:
            os.environ["FLOW_DIR"] = self.flow_dir
        self.tmp.cleanup()

    def commands(self, text):
        (self.dir / "plans" / "f" / "commands.md").write_bytes(text)

    def run_gate(self, feature="f"):
        out, err = [], []
        code = gate.run(feature, out.append, err.append)
        return code, timeless("".join(out)), "".join(err)

    def test_all_three_pass_in_order(self):
        self.commands(b"# Commands: f\n\nLint: `echo l`\nTest: `echo t`\nBuild: `echo b`\n")
        code, out, _ = self.run_gate()
        self.assertEqual(code, 0)
        self.assertEqual(out, "gate: Build: echo b\ngate: Test: echo t\ngate: Lint: echo l\n"
                              "gate: 3 command(s) passed in Ns (Build Ns, Test Ns, Lint Ns)\n")

    def test_a_failure_stops_and_shows_the_output(self):
        self.commands(b"Build: `echo b`\nTest: `echo it broke >&2; exit 3`\nLint: `echo l`\n")
        code, out, _ = self.run_gate()
        self.assertEqual(code, 1)
        self.assertEqual(out, "gate: Build: echo b\ngate: Test: echo it broke >&2; exit 3\n"
                              "gate: Test failed after Ns. the last lines of its output:\nit broke\n")

    def test_placeholders_and_empty_values_are_skipped(self):
        self.commands(b"Build: `<command>`\nTest:\nSmoke: `<x>`\n")
        self.assertEqual(self.run_gate(), (0, "gate: no commands defined, nothing to run\n", ""))

    def test_no_commands_md_is_not_an_error(self):
        self.assertEqual(self.run_gate("nofeature"), (0, "gate: no commands.md for nofeature, nothing to run\n", ""))

    def test_no_feature_is_a_usage_error(self):
        self.assertEqual(self.run_gate(""), (2, "", "usage: python3 scripts/gate.py <feature>\n"))

    def test_flow_dir_moves_the_plans(self):
        (self.dir / "other" / "f").mkdir(parents=True)
        (self.dir / "other" / "f" / "commands.md").write_text("Test: `echo moved`\n", encoding="utf-8")
        os.environ["FLOW_DIR"] = "other"
        try:
            code, out, _ = self.run_gate()
        finally:
            del os.environ["FLOW_DIR"]
        self.assertEqual((code, out), (0, "gate: Test: echo moved\ngate: 1 command(s) passed in Ns (Test Ns)\n"))

    def test_the_value_is_the_first_matching_line_without_backticks(self):
        path = self.dir / "commands.md"
        path.write_bytes(b" Build: no\nBuild:\t \t`a`b`\r\nBuild: second\n")
        self.assertEqual(gate.command(path, "Build"), "ab")
        self.assertEqual(gate.command(path, "Test"), "")

    def test_tail_keeps_the_last_lines(self):
        self.assertEqual(gate.tail(""), "")
        self.assertEqual(gate.tail("a\nb\nc\n", 2), "b\nc\n")
        self.assertEqual(gate.tail("a\nb\nc", 2), "b\nc")
        self.assertEqual(gate.tail("a\n\n", 1), "\n")

    def test_the_failure_output_is_cut_to_40_lines(self):
        self.commands(b"Test: `seq 100; exit 1`\n")
        code, out, _ = self.run_gate()
        self.assertEqual(code, 1)
        self.assertTrue(out.endswith("failed after Ns. the last lines of its output:\n" +
                                     "".join("%d\n" % i for i in range(61, 101))))

    def test_checks_gate_runs_in_process_with_stderr_folded_in(self):
        self.commands(b"Test: `echo out; echo err >&2; exit 1`\n")
        result = checks.gate("scripts", "f")
        self.assertEqual(result.code, 1)
        self.assertFalse(result.ok)
        self.assertIn("gate: Test failed", result.out)
        self.assertIn("out\nerr\n", result.out)
        self.assertEqual(checks.gate("scripts", "").out, "usage: python3 scripts/gate.py <feature>\n")

    def git_init(self):
        subprocess.run(["git", "init", "-q", str(self.dir)], check=True)

    def test_in_a_git_worktree_the_output_goes_to_a_log_that_ignores_itself(self):
        self.git_init()
        self.commands(b"Build: `echo built`\nTest: `echo tested`\n")
        code, out, _ = self.run_gate()
        log = (self.dir / ".feature-flow" / "state" / "gate-f.log").resolve()
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("gate: output in "), out)
        self.assertEqual(Path(out.split("\n")[0][len("gate: output in "):]).resolve(), log)
        self.assertEqual(log.read_text(encoding="utf-8"),
                         "==== gate: Build: echo built\nbuilt\n==== gate: Test: echo tested\ntested\n")
        status = subprocess.run(["git", "status", "--porcelain"], cwd=str(self.dir), stdout=subprocess.PIPE,
                                universal_newlines=True, check=True).stdout
        self.assertNotIn(".feature-flow", status)

    def test_a_failure_shows_only_the_failed_commands_output_and_the_log_keeps_all(self):
        self.git_init()
        self.commands(b"Build: `echo built`\nTest: `echo it broke; exit 1`\n")
        code, out, _ = self.run_gate()
        self.assertEqual(code, 1)
        self.assertTrue(out.endswith("gate: Test failed after Ns. the last lines of its output:\nit broke\n"), out)
        log = self.dir / ".feature-flow" / "state" / "gate-f.log"
        self.assertIn("built\n", log.read_text(encoding="utf-8"))

    def test_the_next_run_starts_a_fresh_log(self):
        self.git_init()
        self.commands(b"Test: `echo first`\n")
        self.run_gate()
        self.commands(b"Test: `echo second`\n")
        self.run_gate()
        text = (self.dir / ".feature-flow" / "state" / "gate-f.log").read_text(encoding="utf-8")
        self.assertEqual(text, "==== gate: Test: echo second\nsecond\n")

    def test_timings_get_each_command_and_its_seconds(self):
        self.commands(b"Build: `echo b`\nTest: `sleep 1`\n")
        timings = []
        self.assertEqual(gate.run("f", [].append, [].append, timings=timings), 0)
        self.assertEqual([k for k, _ in timings], ["Build", "Test"])
        self.assertGreaterEqual(timings[1][1], 0.9)

    def test_a_long_command_gets_still_running_lines(self):
        self.commands(b"Test: `sleep 1.3`\n")
        live = []
        self.assertEqual(gate.run("f", [].append, [].append, progress=live.append, every=0.4), 0)
        self.assertGreaterEqual(len(live), 2, live)
        self.assertTrue(all(line.startswith("gate: Test still running, ") for line in live), live)

    def test_announce_names_each_command_as_it_starts(self):
        self.commands(b"Build: `echo b`\nTest: `echo t`\n")
        live = []
        gate.run("f", [].append, [].append, progress=live.append, announce=True)
        self.assertEqual(live, ["gate: Build: echo b\n", "gate: Test: echo t\n"])

    def test_checks_gate_logs_how_long_each_command_took(self):
        self.commands(b"Build: `echo b`\nCheck web/: `echo w`\n")
        logged = []
        result = checks.gate("scripts", "f", log=logged.append)
        self.assertTrue(result.ok)
        self.assertEqual(len(logged), 1)
        self.assertRegex(logged[0], r"^GATE-TIME Build=\d+ Check_web/=\d+$")
        self.assertEqual([k for k, _ in result.timings], ["Build", "Check web/"])

    def test_a_tick_never_stops_the_command_and_the_limit_still_does(self):
        with tempfile.TemporaryFile() as log:
            seen = []
            code, timed_out = proc.run(["bash", "-c", "sleep 0.5; exit 3"], False, log, None, tick=seen.append,
                                       every=0.1)
            self.assertEqual((code, timed_out), (3, False))
            self.assertGreaterEqual(len(seen), 2)
            code, timed_out = proc.run(["bash", "-c", "sleep 30"], False, log, 0.01, tick=seen.append, every=0.2)
            self.assertEqual((code, timed_out), (None, True))

    def test_clock_reads_like_the_ci_logs(self):
        self.assertEqual([gate.clock(s) for s in (0, 4.4, 59.6, 61, 252)], ["0s", "4s", "1m00s", "1m01s", "4m12s"])

    def test_the_shim_runs_the_gate(self):
        self.commands(b"Build: `echo b`\nTest: `echo t; exit 2`\n")
        env = dict(os.environ)
        env.pop("FLOW_DIR", None)
        shim = str(helpers.ROOT / "scripts" / "gate.py")
        expected = (
            (["f"], 1, "gate: Build: echo b\ngate: Test: echo t; exit 2\ngate: Test failed after Ns. the last lines of its output:\nt\n", ""),
            ([], 2, "", "usage: python3 scripts/gate.py <feature>\n"),
            (["nofeature"], 0, "gate: no commands.md for nofeature, nothing to run\n", ""),
        )
        for args, code, out, err in expected:
            run = subprocess.run([sys.executable, shim] + args, cwd=str(self.dir),
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                                 universal_newlines=True)
            self.assertEqual((run.returncode, timeless(run.stdout), run.stderr), (code, out, err))


if __name__ == "__main__":
    unittest.main()
