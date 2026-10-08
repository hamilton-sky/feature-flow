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


if __name__ == "__main__":
    unittest.main()
