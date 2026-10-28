"""The conductor is the package feature_flow/conductor/: packaged, parseable on Python 3.9, and importable
by the names its callers use."""

import ast
import re
import sys
import unittest

from helpers import ROOT

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PACKAGE = ROOT / "feature_flow" / "conductor"
NAMES = ("Conductor", "Stop", "NoPhase", "followups_only", "section_after", "demote", "owner_hash")
PLANNER = ("plan_prompt", "plan_review_prompt", "plan_accept", "plan_scouts", "plan_scout_prompt",
           "consult_prompt", "brainstorm_prompt")


def listed_packages():
    """The names in pyproject.toml's `packages = [...]` (tomllib is Python 3.11+, the floor is 3.9)."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    block = re.search(r"(?ms)^packages = \[(.*?)\]", text)
    return set(re.findall(r'"([^"]+)"', block.group(1))) if block else set()


class ConductorPackage(unittest.TestCase):
    def test_the_old_module_is_gone(self):
        self.assertFalse((ROOT / "feature_flow" / "conductor.py").exists())
        self.assertTrue((PACKAGE / "__init__.py").is_file())

    def test_every_package_folder_is_listed_in_pyproject(self):
        folders = sorted(p.parent for p in PACKAGE.rglob("__init__.py") if "__pycache__" not in p.parts)
        self.assertTrue(folders, "no package under %s" % PACKAGE)
        names = {".".join(f.relative_to(ROOT).parts) for f in folders}
        for name in ("feature_flow.conductor", "feature_flow.conductor.policy", "feature_flow.conductor.phases",
                     "feature_flow.conductor.schedulers"):
            self.assertIn(name, names)
        missing = names - listed_packages()
        self.assertEqual(missing, set(), "pyproject.toml does not list %s" % sorted(missing))

    def test_every_module_parses_as_python_3_9(self):
        files = sorted(p for p in PACKAGE.rglob("*.py") if "__pycache__" not in p.parts)
        self.assertTrue(files)
        for path in files:
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                ast.parse(path.read_text(encoding="utf-8"), str(path), feature_version=(3, 9))

    def test_the_names_callers_use_import_from_the_package(self):
        import feature_flow.conductor as conductor
        import feature_flow.conductor.errors as errors

        for name in NAMES:
            self.assertTrue(hasattr(conductor, name), name)
        self.assertIs(errors.Stop, conductor.Stop)
        self.assertIs(errors.NoPhase, conductor.NoPhase)

    def test_the_planner_has_the_seven_commands(self):
        from feature_flow.conductor import facade, planning

        for name in PLANNER:
            self.assertTrue(callable(getattr(planning.Planner, name, None)), name)
            self.assertTrue(callable(getattr(facade.Conductor, name, None)), name)


if __name__ == "__main__":
    unittest.main()
