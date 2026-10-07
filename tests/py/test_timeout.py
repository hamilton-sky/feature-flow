import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import checks, gate  # the package under test, from this checkout


def alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


class TimeoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "plans" / "f").mkdir(parents=True)
        self.sleeper = self.dir / "sleeper.py"
        self.sleeper.write_text("import os, sys, time\nopen(sys.argv[2], 'w').write(str(os.getpid()))\n"
                                "time.sleep(float(sys.argv[1]))\n", encoding="utf-8")
        self.cwd = os.getcwd()
        self.saved = {k: os.environ.pop(k, None) for k in ("FLOW_DIR", "FLOW_GATE_TIMEOUT")}
        os.chdir(str(self.dir))

    def tearDown(self):
        os.chdir(self.cwd)
        os.environ.pop("FLOW_GATE_TIMEOUT", None)
        for key, value in self.saved.items():
            if value is not None:
                os.environ[key] = value
        self.tmp.cleanup()

    def sleep_command(self, seconds):
        return '"%s" sleeper.py %s pid.txt' % (sys.executable, seconds)

    def commands(self, text):
        (self.dir / "plans" / "f" / "commands.md").write_text(text, encoding="utf-8")

    def run_gate(self, **kw):
        out, err = [], []
        code = gate.run("f", out.append, err.append, **kw)
        return code, "".join(out), "".join(err)

    def test_timeout_fails_the_gate_and_leaves_no_child(self):
        self.commands("Test: `%s`\n" % self.sleep_command(60))
        start = time.time()
        code, out, _ = self.run_gate(timeout=0.02)
        self.assertLess(time.time() - start, 15)
        self.assertEqual(code, 1)
        self.assertIn("gate: Test timed out after 0.02 minutes", out)
        if sys.platform != "win32":
            pid = int((self.dir / "pid.txt").read_text())
            for _ in range(50):
                if not alive(pid):
                    break
                time.sleep(0.1)
            self.assertFalse(alive(pid), "the sleeping child is still running")

    def test_timeout_zero_means_no_limit(self):
        self.commands("Test: `%s`\n" % self.sleep_command(2))
        os.environ["FLOW_GATE_TIMEOUT"] = "0"
        code, out, _ = self.run_gate()
        self.assertEqual((code, out.endswith("gate: 1 command(s) passed\n")), (0, True), out)

    def test_timeout_that_is_not_a_number_names_the_variable(self):
        self.commands("Test: `%s`\n" % self.sleep_command(0))
        os.environ["FLOW_GATE_TIMEOUT"] = "abc"
        code, out, err = self.run_gate()
        self.assertEqual(code, 2)
        self.assertIn("FLOW_GATE_TIMEOUT", err)
        self.assertEqual(out, "")

    def test_timeout_for_the_smoke_command_kills_it(self):
        start = time.time()
        result = checks.smoke(self.sleep_command(60), 0.02)
        self.assertLess(time.time() - start, 15)
        self.assertFalse(result.ok)
        self.assertTrue(result.timed_out)


class SmokeLogTests(unittest.TestCase):
    def setUp(self):
        self.repo = helpers.Repo()

    def tearDown(self):
        self.repo.close()

    def test_a_failing_smoke_leaves_a_log_and_one_line_stop(self):
        cmd = '"%s" -c "print(\'boom\'); raise SystemExit(1)"' % sys.executable
        rc, out = self.repo.flow("next", FLOW_SMOKE=cmd)
        log = self.repo.dir / ".feature-flow" / "state" / "f.smoke.log"
        self.assertEqual(rc, 1)
        self.assertEqual(len(out.splitlines()), 1, out)
        self.assertTrue(out.startswith("STOP smoke test failed before 01-a: the base is already broken. "
                                       "fix it first. command: "), out)
        self.assertTrue(out.endswith("the last 40 lines are in %s" % log), out)
        self.assertIn("boom", log.read_text(encoding="utf-8"))

    def test_timeout_that_is_not_a_number_stops_the_conductor(self):
        rc, out = self.repo.flow("next", FLOW_GATE_TIMEOUT="abc")
        self.assertEqual(rc, 1)
        self.assertIn("FLOW_GATE_TIMEOUT", out)


if __name__ == "__main__":
    unittest.main()
