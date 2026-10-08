import unittest

import helpers

SKILLS = ("skills/feature-flow/SKILL.md", "adapters/codex/feature-flow/SKILL.md")


class SkillTextTests(unittest.TestCase):
    def test_both_skills_name_the_home_conductor_and_the_repo_one(self):
        for rel in SKILLS:
            text = (helpers.ROOT / rel).read_text(encoding="utf-8")
            self.assertIn(".feature-flow/scripts/flow.py", text, rel)
            self.assertIn("FEATURE_FLOW_HOME", text, rel)
            self.assertIn("unrelated `scripts/flow.py`", text, rel)
            self.assertIn("scripts/flow.py", text, rel)

    def test_the_codex_role_check_honors_the_home_override(self):
        text = (helpers.ROOT / "adapters/codex/feature-flow/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("${FEATURE_FLOW_HOME:-$HOME/.feature-flow}/agents/", text)
        self.assertNotIn("check that `.agents/flow-roles/feature-planner.md`", text)  # the planner roles may be in the home too


if __name__ == "__main__":
    unittest.main()
