"""feature-flow config: the mode and every setting a run will use, its value and where it came from. Read-only."""

import io
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import command  # the package under test, from this checkout
from feature_flow.commands import config


def run(argv, environ):
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.dict(os.environ, environ, clear=True):
        code = config.main(argv, out, err)
    return code, out.getvalue(), err.getvalue()


def row(text, name):
    """The value and source of one setting's row."""
    for line in text.splitlines():
        if line.startswith(name + "  "):
            return " ".join(line[len(name):].split())
    raise AssertionError("no row %r in\n%s" % (name, text))


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="flow-config-test-"))
        self.addCleanup(shutil.rmtree, str(self.dir), True)

    def plan(self, feature, commands):
        (self.dir / feature).mkdir()
        (self.dir / feature / "commands.md").write_text(commands, encoding="utf-8")
        return {"FLOW_DIR": str(self.dir)}

    def test_a_new_plan_gets_feature_from_the_template(self):
        code, out, _ = run([], {})
        self.assertEqual(code, 0)
        self.assertIn("A new plan (from the commands.md template)", out)
        self.assertRegex(out, r"Mode: feature +commands.md \(Mode: feature\)")
        self.assertEqual(row(out, "reviews per ticket"), "two side by side mode feature")
        self.assertEqual(row(out, "full gate and review"), "every 3 tickets mode feature")
        self.assertIn("Plan lines: none", out)
        self.assertNotIn("Ignored:", out)

    def test_a_plan_with_mode_small_and_its_own_lines(self):
        env = self.plan("tiny", "Mode: `small`\nBuild: `make`\nTest: `make test`\nLanes: `2`\nCheck web/: `npm t`\n")
        code, out, _ = run(["tiny"], env)
        self.assertEqual(code, 0, out)
        self.assertIn("Feature: tiny", out)
        self.assertRegex(out, r"Mode: small +commands.md \(Mode: small\)")
        self.assertEqual(row(out, "reviews per ticket"), "one review of the whole feature at the end mode small")
        self.assertEqual(row(out, "scouts"), "off mode small")
        self.assertEqual(row(out, "lanes"), "2 commands.md (Lanes: 2)")
        self.assertIn("Plan lines: Build, Test, Check web/", out)

    def test_a_plan_from_before_modes(self):
        env = self.plan("old", "Build: `make`\n")
        _, out, _ = run(["old"], env)
        self.assertIn("Mode: none", out)
        self.assertIn("predates modes", out)
        self.assertEqual(row(out, "reviews per ticket"), "one built-in")

    def test_retired_settings_are_listed_as_ignored_and_do_not_change_a_value(self):
        env = self.plan("p", "Mode: `careful`\n")
        env.update({"FLOW_REVIEWERS": "1", "FLOW_GATE": "off", "FLOW_TICKETS_PER_SESSION": "5"})
        _, out, _ = run(["p", "--all"], env)
        self.assertEqual(row(out, "reviews per ticket"), "two side by side mode careful")
        self.assertEqual(row(out, "full gate and review"), "each ticket mode careful")
        self.assertEqual(row(out, "tickets per session"), "5 FLOW_TICKETS_PER_SESSION=5 (env)")
        self.assertEqual(row(out, "full gate after every ticket"), "on mode careful")
        self.assertIn("Ignored: FLOW_REVIEWERS=1, FLOW_GATE=off", out)

    def test_flow_mode_and_the_old_flow_profile(self):
        env = self.plan("p", "Mode: `careful`\n")
        _, out, _ = run(["p"], dict(env, FLOW_MODE="small"))
        self.assertRegex(out, r"Mode: small +FLOW_MODE=small \(env\)")
        _, out, _ = run(["p"], dict(env, FLOW_PROFILE="fast"))
        self.assertIn("Note: FLOW_PROFILE is now FLOW_MODE", out)

    def test_mistakes(self):
        code, _, err = run(["missing"], {"FLOW_DIR": str(self.dir)})
        self.assertEqual(code, 1)
        self.assertIn("no plan", err)
        self.assertEqual(run(["a/b"], {})[0], 2)
        self.assertEqual(run(["a", "b"], {})[0], 2)
        env = self.plan("bad", "Mode: `turbo`\n")
        code, _, err = run(["bad"], env)
        self.assertEqual(code, 1)
        self.assertIn("the mode must be fix, small, feature, careful, explore, not turbo", err)

    def test_reads_nothing_into_the_real_environment(self):
        env = self.plan("p", "Mode: `careful`\n")
        with mock.patch.dict(os.environ, env, clear=True):
            config.main(["p"], io.StringIO(), io.StringIO())
            self.assertNotIn("FLOW_REVIEWERS", os.environ)

    def test_the_command_is_listed(self):
        self.assertIn("config", command.COMMANDS)
        self.assertIn("feature-flow config [<feature>] [--all]", command.USAGE)


if __name__ == "__main__":
    unittest.main()
