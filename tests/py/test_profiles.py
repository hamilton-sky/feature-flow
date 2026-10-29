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
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for name, values in profiles.PROFILES.items():
            for key in values:
                self.assertIn("`%s`" % key, readme, "%s in %s" % (key, name))


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

    def test_an_unknown_profile_stops_the_run(self):
        repo, (rc, out) = self.setup("", FLOW_PROFILE="turbo")
        self.assertEqual(rc, 1)
        self.assertIn("STOP the profile must be careful, fast, normal, standard, not turbo", out)


if __name__ == "__main__":
    unittest.main()
