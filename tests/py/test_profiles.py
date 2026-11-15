"""Profiles: one word in FLOW_PROFILE or commands.md that fills several FLOW_ settings, never over one given."""

import shutil
import sys
import unittest

import helpers
from helpers import ROOT, Repo

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import profiles  # the package under test, from this checkout

PYTHON = '"%s"' % sys.executable


class PickTests(unittest.TestCase):
    def test_the_environment_wins_over_the_plan(self):
        self.assertEqual(profiles.pick({"FLOW_PROFILE": "Fast"}, "careful"), "fast")
        self.assertEqual(profiles.pick({}, "careful"), "careful")
        self.assertEqual(profiles.pick({}, ""), "")

    def test_an_unknown_name_is_refused(self):
        with self.assertRaises(profiles.UnknownProfile):
            profiles.pick({"FLOW_PROFILE": "turbo"}, "")

    def test_it_fills_only_what_is_not_set(self):
        env = {"FLOW_TICKETS_PER_SESSION": "9"}
        filled = profiles.apply(env, "careful")
        self.assertEqual(env["FLOW_TICKETS_PER_SESSION"], "9")
        self.assertEqual(env["FLOW_GATE_FULL"], "1")
        self.assertNotIn("FLOW_TICKETS_PER_SESSION", filled)
        self.assertEqual(profiles.apply({}, "normal"), [])

    def test_every_profile_sets_only_known_settings(self):
        # every setting a profile sets is in the settings table of docs/commands-and-settings.md
        doc = (ROOT / "docs" / "commands-and-settings.md").read_text(encoding="utf-8")
        for name, values in profiles.PROFILES.items():
            for key in values:
                self.assertIn("`%s`" % key, doc, "%s in %s" % (key, name))


class LivePageDocumentationTests(unittest.TestCase):
    def test_codex_workflow_and_approval_contract(self):
        doc = (ROOT / "docs" / "brainstorm.md").read_text(encoding="utf-8")
        for phrase in ("--serve", "--port 0", "--agent-label Codex", "--asks", "--answer-graph",
                       "--apply", "--picks", "412", "preview", "five seconds", "manual real-agent",
                       "approval intent", "no automatic Codex chat wakeup", "never starts a build"):
            self.assertIn(phrase, doc)
        source = (ROOT / "docs" / "source-of-truth.md").read_text(encoding="utf-8")
        self.assertIn("existing approval rules", source)
        self.assertIn("freezes the plan", source.lower())
        for name in ("skills/feature-flow/SKILL.md", "adapters/codex/feature-flow/SKILL.md"):
            skill = (ROOT / name).read_text(encoding="utf-8")
            for phrase in ("--serve", "--asks", "approval intent", "cannot run builds or commits"):
                self.assertIn(phrase, skill, name)


class ModeTests(unittest.TestCase):
    def test_each_mode_stands_on_the_profile_it_replaces(self):
        # the modes change names, not behaviour: each one fills exactly what its old profile filled
        self.assertEqual(profiles.MODES, {"fix": "normal", "small": "fast", "feature": "standard",
                                          "careful": "careful", "explore": "standard"})
        for old, mode in (("fast", "small"), ("standard", "feature"), ("careful", "careful")):
            self.assertEqual(profiles.resolve({}, "", old), (mode, old))
            self.assertEqual(profiles.resolve({}, mode), (mode, old))
        self.assertEqual(profiles.resolve({}, "", "normal"), ("", "normal"))
        self.assertEqual(profiles.resolve({}, "", ""), ("", ""))

    def test_the_order_env_mode_then_env_profile_then_mode_line_then_profile_line(self):
        self.assertEqual(profiles.resolve({"FLOW_MODE": "small", "FLOW_PROFILE": "careful"}, "careful", "standard"),
                         ("small", "fast"))
        self.assertEqual(profiles.resolve({"FLOW_PROFILE": "careful"}, "small", "standard"), ("careful", "careful"))
        self.assertEqual(profiles.resolve({}, "`Small`", "careful"), ("small", "fast"))

    def test_an_unknown_mode_names_the_five(self):
        with self.assertRaises(profiles.UnknownProfile) as caught:
            profiles.resolve({"FLOW_MODE": "turbo"})
        self.assertEqual(str(caught.exception), "the mode must be fix, small, feature, careful, explore, not turbo")

    def test_retired_settings_set_by_hand_are_taken_out_and_named(self):
        env = {"FLOW_REVIEWERS": "1", "FLOW_ROUND_REVIEW": "on", "FLOW_GATE": "off", "FLOW_PROFILE": "fast",
               "FLOW_LANES": "2"}
        ignored = profiles.strip_retired(env)
        self.assertEqual(ignored, ["FLOW_REVIEWERS=1", "FLOW_ROUND_REVIEW=on", "FLOW_GATE=off"])
        self.assertEqual(env, {"FLOW_PROFILE": "fast", "FLOW_LANES": "2"})
        lines = profiles.warnings(env, ignored)
        self.assertEqual(len(lines), 4, lines)
        self.assertTrue(lines[0].startswith("feature-flow: FLOW_REVIEWERS=1 is ignored since 0.44.0; the mode sets it"))
        self.assertIn("`Gate: off unsafe`", lines[2])
        self.assertIn("FLOW_PROFILE is now FLOW_MODE", lines[3])
        self.assertEqual(profiles.warnings({"FLOW_MODE": "small"}, []), [])

    def test_flow_internal_keeps_the_retired_settings(self):
        env = {"FLOW_INTERNAL": "1", "FLOW_REVIEWERS": "1", "FLOW_GATE": "off"}
        self.assertEqual(profiles.strip_retired(env), [])
        self.assertEqual(env["FLOW_REVIEWERS"], "1")
        self.assertEqual(env["FLOW_GATE"], "off")

    def test_env_profile_reads_flow_mode_too(self):
        self.assertEqual(profiles.env_profile({"FLOW_MODE": "careful"}), "careful")
        self.assertEqual(profiles.env_profile({"FLOW_PROFILE": "careful"}), "careful")
        self.assertEqual(profiles.env_profile({"FLOW_MODE": "turbo"}), "")


class ProfileDriveTests(unittest.TestCase):
    def setup(self, profile_line="", **env):
        repo = Repo(tickets=(("01-a", "A", "—"),))
        self.addCleanup(repo.close)
        for folder in ("agents", "guides"):
            shutil.copytree(str(ROOT / folder), str(repo.path(folder)))
        repo.path("plans/f/commands.md").write_text(
            "# Commands: f\n\nSmoke: `%s -c \"pass\"`\nTest: `%s -c \"pass\"`\n%s" % (PYTHON, PYTHON, profile_line),
            encoding="utf-8")
        repo.commit("plan")
        return repo, repo.flow("start", **env)

    def test_the_plans_profile_is_logged_and_turns_fast_on(self):
        repo, (rc, out) = self.setup("Profile: `fast`\n")
        self.assertEqual(rc, 0, out)
        self.assertIn("PROFILE-FAST", repo.log())
        self.assertEqual(repo.state().get("fast"), "1")

    def test_a_setting_given_wins_over_the_profile(self):
        repo, (rc, out) = self.setup("Profile: fast\n", FLOW_FAST="0")
        self.assertEqual(rc, 0, out)
        self.assertNotEqual(repo.state().get("fast"), "1")

    def test_the_plans_mode_is_logged_and_sets_its_profile(self):
        repo, (rc, out) = self.setup("Mode: `small`\n")
        self.assertEqual(rc, 0, out)
        self.assertIn("MODE-SMALL", repo.log())
        self.assertIn("PROFILE-FAST", repo.log())
        self.assertEqual(repo.state().get("fast"), "1")

    def test_flow_mode_wins_over_the_plans_mode(self):
        repo, (rc, out) = self.setup("Mode: `small`\n", FLOW_MODE="careful")
        self.assertEqual(rc, 0, out)
        self.assertIn("MODE-CAREFUL", repo.log())
        self.assertNotEqual(repo.state().get("fast"), "1")

    def test_an_unknown_profile_stops_the_run(self):
        repo, (rc, out) = self.setup("", FLOW_PROFILE="turbo")
        self.assertEqual(rc, 1)
        self.assertIn("STOP the mode must be fix, small, feature, careful, explore, not turbo", out)


if __name__ == "__main__":
    unittest.main()
