import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import checks, gate  # the package under test, from this checkout


@unittest.skipUnless(shutil.which("bash"), "the gate runs commands through bash")
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
        return code, b"".join(out).decode(), b"".join(err).decode()

    def test_all_three_pass_in_order(self):
        self.commands(b"# Commands: f\n\nLint: `echo l`\nTest: `echo t`\nBuild: `echo b`\n")
        code, out, _ = self.run_gate()
        self.assertEqual(code, 0)
        self.assertEqual(out, "gate: Build: echo b\ngate: Test: echo t\ngate: Lint: echo l\n"
                              "gate: 3 command(s) passed\n")

    def test_a_failure_stops_and_shows_the_output(self):
        self.commands(b"Build: `echo b`\nTest: `echo it broke >&2; exit 3`\nLint: `echo l`\n")
        code, out, _ = self.run_gate()
        self.assertEqual(code, 1)
        self.assertEqual(out, "gate: Build: echo b\ngate: Test: echo it broke >&2; exit 3\n"
                              "gate: Test failed. the last lines of its output:\nit broke\n")

    def test_placeholders_and_empty_values_are_skipped(self):
        self.commands(b"Build: `<command>`\nTest:\nSmoke: `<x>`\n")
        self.assertEqual(self.run_gate(), (0, "gate: no commands defined, nothing to run\n", ""))

    def test_no_commands_md_is_not_an_error(self):
        self.assertEqual(self.run_gate("nofeature"), (0, "gate: no commands.md for nofeature, nothing to run\n", ""))

    def test_no_feature_is_a_usage_error(self):
        self.assertEqual(self.run_gate(""), (2, "", "usage: python3 scripts/gate.py <feature>\n"))

    def test_flow_dir_moves_the_plans(self):
        (self.dir / "other" / "f").mkdir(parents=True)
        (self.dir / "other" / "f" / "commands.md").write_text("Test: `echo moved`\n")
        os.environ["FLOW_DIR"] = "other"
        try:
            code, out, _ = self.run_gate()
        finally:
            del os.environ["FLOW_DIR"]
        self.assertEqual((code, out), (0, "gate: Test: echo moved\ngate: 1 command(s) passed\n"))

    def test_the_value_is_read_like_awk(self):
        path = self.dir / "commands.md"
        path.write_bytes(b" Build: no\nBuild:\t \t`a`b`\r\nBuild: second\n")
        self.assertEqual(gate.command(path, "Build"), b"ab\r")
        self.assertEqual(gate.command(path, "Test"), b"")

    def test_tail_keeps_the_last_lines_like_tail(self):
        self.assertEqual(gate.tail(b""), b"")
        self.assertEqual(gate.tail(b"a\nb\nc\n", 2), b"b\nc\n")
        self.assertEqual(gate.tail(b"a\nb\nc", 2), b"b\nc")
        self.assertEqual(gate.tail(b"a\n\n", 1), b"\n")

    def test_the_failure_output_is_cut_to_40_lines(self):
        self.commands(b"Test: `seq 100; exit 1`\n")
        code, out, _ = self.run_gate()
        self.assertEqual(code, 1)
        self.assertTrue(out.endswith("failed. the last lines of its output:\n" +
                                     "".join("%d\n" % i for i in range(61, 101))))

    def test_checks_gate_runs_in_process_with_stderr_folded_in(self):
        self.commands(b"Test: `echo out; echo err >&2; exit 1`\n")
        result = checks.gate("scripts", "f")
        self.assertEqual(result.code, 1)
        self.assertFalse(result.ok)
        self.assertIn("gate: Test failed", result.out)
        self.assertIn("out\nerr\n", result.out)
        self.assertEqual(checks.gate("scripts", "").out, "usage: python3 scripts/gate.py <feature>\n")

    def test_the_shim_runs_the_gate(self):
        self.commands(b"Build: `echo b`\nTest: `echo t; exit 2`\n")
        env = dict(os.environ)
        env.pop("FLOW_DIR", None)
        shim = str(helpers.ROOT / "scripts" / "gate.py")
        expected = (
            (["f"], 1, "gate: Build: echo b\ngate: Test: echo t; exit 2\ngate: Test failed. the last lines of its output:\nt\n", ""),
            ([], 2, "", "usage: python3 scripts/gate.py <feature>\n"),
            (["nofeature"], 0, "gate: no commands.md for nofeature, nothing to run\n", ""),
        )
        for args, code, out, err in expected:
            run = subprocess.run([sys.executable, shim] + args, cwd=str(self.dir),
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                                 universal_newlines=True)
            self.assertEqual((run.returncode, run.stdout, run.stderr), (code, out, err))


if __name__ == "__main__":
    unittest.main()
