import os
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import checks, gate  # the package under test, from this checkout


class QuickGateModeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "plans" / "f").mkdir(parents=True)
        self.cwd = os.getcwd()
        self.flow_dir = os.environ.pop("FLOW_DIR", None)
        os.chdir(str(self.dir))
        (self.dir / "logger.py").write_text(
            "import sys\n"
            "open('log', 'a').write(sys.argv[1] + '\\n')\n"
            "if len(sys.argv) > 2:\n"
            "    sys.stderr.write('quick broke\\n')\n"
            "    sys.exit(3)\n", encoding="utf-8")

    def tearDown(self):
        os.chdir(self.cwd)
        if self.flow_dir is not None:
            os.environ["FLOW_DIR"] = self.flow_dir
        self.tmp.cleanup()

    def log_cmd(self, name, fail=False):
        # works under bash and cmd.exe: double quotes only, no shell operators
        return '"%s" logger.py %s%s' % (sys.executable, name, " fail" if fail else "")

    def commands(self, quick_line, quick_cmd=None):
        lines = ["%s: `%s`" % (n, self.log_cmd(n)) for n in ("Build", "Test", "Lint")]
        if quick_line:
            lines.append(quick_line.replace("CMD", quick_cmd or self.log_cmd("Quick")))
        (self.dir / "plans" / "f" / "commands.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def ran(self):
        path = self.dir / "log"
        return path.read_text(encoding="utf-8").split() if path.exists() else []

    def run_gate(self, quick):
        out, err = [], []
        code = gate.run("f", out.append, err.append, quick=quick)
        return code, "".join(out)

    def test_full_mode_runs_build_test_lint(self):
        self.commands("Quick: `CMD`")
        code, out = self.run_gate(False)
        self.assertEqual(code, 0)
        self.assertEqual(self.ran(), ["Build", "Test", "Lint"])
        self.assertNotIn("Quick", out)

    def test_quick_mode_runs_build_quick_lint(self):
        self.commands("Quick: `CMD`")
        code, out = self.run_gate(True)
        self.assertEqual(code, 0)
        self.assertEqual(self.ran(), ["Build", "Quick", "Lint"])
        self.assertIn("gate: Quick: %s\n" % self.log_cmd("Quick"), out)
        self.assertNotIn("gate: Test:", out)

    def test_quick_mode_without_a_quick_line_runs_test(self):
        self.commands("")
        code, _ = self.run_gate(True)
        self.assertEqual(code, 0)
        self.assertEqual(self.ran(), ["Build", "Test", "Lint"])

    def test_quick_mode_with_a_placeholder_runs_test(self):
        self.commands("Quick: `<placeholder>`")
        code, _ = self.run_gate(True)
        self.assertEqual(code, 0)
        self.assertEqual(self.ran(), ["Build", "Test", "Lint"])

    def test_quick_mode_with_an_empty_quick_runs_test(self):
        self.commands("Quick:")
        code, _ = self.run_gate(True)
        self.assertEqual(code, 0)
        self.assertEqual(self.ran(), ["Build", "Test", "Lint"])

    def test_a_failing_quick_fails_the_gate_with_its_tail(self):
        self.commands("Quick: `CMD`", self.log_cmd("Quick", fail=True))
        code, out = self.run_gate(True)
        self.assertEqual(code, 1)
        self.assertIn("gate: Quick failed. the last lines of its output:\nquick broke\n", out)
        self.assertEqual(self.ran(), ["Build", "Quick"])

    def test_checks_gate_passes_quick_on(self):
        self.commands("Quick: `CMD`")
        result = checks.gate(helpers.ROOT / "scripts", "f", quick=True)
        self.assertEqual(result.code, 0)
        self.assertEqual(self.ran(), ["Build", "Quick", "Lint"])


if __name__ == "__main__":
    unittest.main()
