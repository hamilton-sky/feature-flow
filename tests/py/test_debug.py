import shutil
import unittest

from helpers import ROOT, Repo

T1 = "plans/f/tasks/01-a.md"
INTRO = "The debugging guide follows"


class DebugGuide(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        for folder in ("agents", "guides"):
            shutil.copytree(str(ROOT / folder), str(self.repo.path(folder)))
        cmd = self.repo.path("plans/f/commands.md")
        cmd.write_text(cmd.read_text(encoding="utf-8")
                       + "Test: `python -c \"import os, sys; sys.exit(os.path.exists('FAILING'))\"`\n", encoding="utf-8")
        self.repo.commit("prompts")

    def tearDown(self):
        self.repo.close()

    def test_debug_first_build_prompt_has_no_debugging_guide(self):
        rc, out = self.repo.flow("next")
        self.assertEqual(rc, 0)
        self.assertTrue(out.startswith("BUILD"), out)
        prompt = self.repo.flow("prompt")[1]
        self.assertNotIn(INTRO, prompt)

    def test_debug_build_prompt_after_a_failing_gate_carries_the_guide(self):
        self.repo.flow("next")
        self.repo.path("FAILING").write_text("x\n", encoding="utf-8")
        self.repo.resolve(T1)
        rc, out = self.repo.flow("next")
        self.assertEqual(rc, 0)
        self.assertTrue(out.startswith("BUILD %s 01 " % T1), out)
        prompt = self.repo.flow("prompt")[1]
        self.assertIn(INTRO, prompt)
        self.assertIn("Follow it before you change any code.", prompt)
        for word in ("reproduce", "isolate", "fix", "prove"):
            self.assertIn(word, prompt.split(INTRO, 1)[1].lower())


if __name__ == "__main__":
    unittest.main()
