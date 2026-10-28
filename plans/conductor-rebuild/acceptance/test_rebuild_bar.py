"""The bar (spec.md § Goal and the bar), acceptance tests A1 and A2, and the package layout spec.md § Decisions and
§ Interfaces settle: the Conductor in facade.py, the strings existing tests read, the exports kept."""

import ast
import subprocess
import sys
import unittest

from support import ROOT

PACKAGE = ROOT / "feature_flow" / "conductor"
CHECK_CODE_DOC = '"""Stop when the files the conductor runs from changed since the ticket was picked."""'


def python(code):
    return subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, universal_newlines=True)


class Bar(unittest.TestCase):
    # Bar 2 / A1: `python3 -c "import feature_flow.conductor as c; print(c.Conductor, c.Stop, c.NoPhase)"` prints the
    # three classes and exits 0; `feature_flow.conductor.errors.Stop is feature_flow.conductor.Stop`.
    def test_a1_the_package_prints_the_three_classes_and_errors_holds_the_same_ones(self):
        result = python("import feature_flow.conductor as c; print(c.Conductor, c.Stop, c.NoPhase)")
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ("Conductor", "Stop", "NoPhase"):
            self.assertRegex(result.stdout, r"<class '[\w.]*\b%s'>" % name)
        result = python("import feature_flow.conductor as c, feature_flow.conductor.errors as e\n"
                        "print(e.Stop is c.Stop, e.NoPhase is c.NoPhase)")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "True True")

    # Bar 3 / A2: `feature_flow/conductor.py` no longer exists.
    def test_bar3_conductor_py_no_longer_exists(self):
        self.assertFalse((ROOT / "feature_flow" / "conductor.py").exists(), "feature_flow/conductor.py still exists")
        self.assertTrue((PACKAGE / "__init__.py").is_file(), "no package feature_flow/conductor/")

    # Bar 4 / A2 / story "A maintainer adds a mode": the facade is under 300 lines and no package module reaches 400.
    def test_a2_ratchet_facade_under_300_lines_every_other_module_under_400(self):
        facade = PACKAGE / "facade.py"
        self.assertTrue(facade.is_file(), "no feature_flow/conductor/facade.py")
        self.assertLess(len(facade.read_text(encoding="utf-8").splitlines()), 300)
        others = [p for p in PACKAGE.rglob("*.py") if p != facade]
        self.assertTrue(others, "the package holds only the facade")
        for path in others:
            lines = len(path.read_text(encoding="utf-8").splitlines())
            self.assertLess(lines, 400, "%s has %d lines" % (path.relative_to(ROOT), lines))


class CompatibilitySeam(unittest.TestCase):
    # Decisions, Where the Conductor class lives: `facade.py` with `__init__.py` re-exporting it. Interfaces:
    # `feature_flow.conductor` exports `Conductor`, `Stop`, `NoPhase`, `followups_only`, `section_after`, `demote`,
    # `owner_hash`.
    def test_the_conductor_lives_in_facade_and_the_package_exports_the_seam(self):
        result = python("import feature_flow.conductor as c, feature_flow.conductor.facade as f\n"
                        "print(c.Conductor is f.Conductor)\n"
                        "print(all(callable(getattr(c, n)) for n in ('followups_only', 'section_after', 'demote', "
                        "'owner_hash')))")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split(), ["True", "True"])

    # Interfaces: `Conductor(feature, scripts)`; its 17 command methods with today's names and arguments.
    def test_the_facade_conductor_has_the_17_commands(self):
        names = ("start", "next", "prompt", "verdict", "reset", "fast_switch", "scouts", "scout_prompt", "budget_cmd",
                 "replan_prompt", "plan_prompt", "plan_review_prompt", "plan_accept", "plan_scouts",
                 "plan_scout_prompt", "consult_prompt", "brainstorm_prompt")
        result = python("import feature_flow.conductor.facade as f\n"
                        "print(' '.join(n for n in %r if not callable(getattr(f.Conductor, n, None))))" % (names,))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "", "commands missing on facade.Conductor")

    # Edge case: `tests/py/test_trust_drive.py` and `tests/py/test_trust_runner.py` insert `return` after
    # `check_code`'s docstring (8 spaces in) -> `check_code` stays a `Conductor` method in `facade.py`, with that
    # docstring, to the end.
    def test_check_code_stays_a_conductor_method_in_facade_with_its_docstring(self):
        facade = PACKAGE / "facade.py"
        self.assertTrue(facade.is_file(), "no feature_flow/conductor/facade.py")
        source = facade.read_text(encoding="utf-8")
        self.assertIn("\n        %s\n" % CHECK_CODE_DOC, source)
        tree = ast.parse(source)
        methods = [node for cls in tree.body if isinstance(cls, ast.ClassDef) and cls.name == "Conductor"
                   for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "check_code"]
        self.assertEqual(len(methods), 1, "check_code is not a method of Conductor in facade.py")
        self.assertEqual(ast.get_docstring(methods[0]), CHECK_CODE_DOC.strip('"'))

    # Decisions, Tests that name `conductor.py`: `return "OK %s" % token` stays in `facade.py` (`start`), and
    # `"BUILD %s %s %s%s"` lives in `facade.py` or the build phase.
    def test_the_strings_the_trust_tests_read_live_where_the_spec_says(self):
        facade = PACKAGE / "facade.py"
        self.assertTrue(facade.is_file(), "no feature_flow/conductor/facade.py")
        self.assertIn(b'return "OK %s" % token', facade.read_bytes())
        holders = [p for p in (facade, PACKAGE / "phases" / "build.py")
                   if p.is_file() and b'"BUILD %s %s %s%s"' in p.read_bytes()]
        self.assertEqual(len(holders), 1, "the BUILD line is in neither facade.py nor phases/build.py")


if __name__ == "__main__":
    unittest.main()
