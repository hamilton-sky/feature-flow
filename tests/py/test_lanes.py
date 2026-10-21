"""The pieces of parallel lanes on their own: the Touches line, when two footprints may run side by side,
one lane's view of the run state, the append-only merge, and flow-status --ready and --check."""

import os
import subprocess
import sys
import unittest

from helpers import ROOT, Repo

sys.path.insert(0, str(ROOT))
from feature_flow import lanes, status  # the package under test, from this checkout


class Touches(unittest.TestCase):
    def test_the_header_line_is_split_on_commas_and_spaces(self):
        text = "# T\n\nStatus: open\nTouches: `src/api/`, tests/test_api.py  ./docs/*.md\n\n## Touches: later/\n"
        self.assertEqual(lanes.touches(text), ["src/api/", "tests/test_api.py", "docs/*.md"])

    def test_no_line_is_none_and_a_line_below_a_heading_does_not_count(self):
        self.assertIsNone(lanes.touches("# T\n\nStatus: open\n\n## Notes\n\nTouches: a/\n"))
        self.assertEqual(lanes.touches("# T\nTouches: —\n"), [])


class SideBySide(unittest.TestCase):
    def test_overlap_is_judged_on_the_part_before_a_wildcard(self):
        self.assertTrue(lanes.overlap("src/", "src/a.py"))
        self.assertTrue(lanes.overlap("src/*.py", "src/a/b.py"))
        self.assertTrue(lanes.overlap("*.md", "src/a.py"))  # could be anywhere
        self.assertFalse(lanes.overlap("src/a.py", "src/b.py"))
        self.assertFalse(lanes.overlap("src/a/", "src/b/"))
        self.assertFalse(lanes.overlap("a/", "ab/"))

    def test_the_rules(self):
        shared = ["CHANGELOG.md"]
        self.assertTrue(lanes.side_by_side((None, 2), [], shared))  # nothing running: anything goes
        self.assertTrue(lanes.side_by_side((["a/"], 2), [(["b/"], 2)], shared))
        self.assertFalse(lanes.side_by_side((None, 2), [(["b/"], 2)], shared))  # no Touches: alone
        self.assertFalse(lanes.side_by_side((["a/"], 2), [(None, 2)], shared))
        self.assertFalse(lanes.side_by_side((["a/"], 2), [(["a/x.py"], 2)], shared))
        self.assertFalse(lanes.side_by_side((["a/", "CHANGELOG.md"], 2), [(["b/"], 2)], shared))
        self.assertFalse(lanes.side_by_side((["a/"], 2), [(["b/", "CHANGELOG.md"], 2)], shared))
        # level 3 keeps clear of the other's top-level folders too
        self.assertTrue(lanes.side_by_side((["src/a/"], 2), [(["src/b/"], 2)], shared))
        self.assertFalse(lanes.side_by_side((["src/a/"], 3), [(["src/b/"], 2)], shared))
        self.assertFalse(lanes.side_by_side((["src/a/"], 2), [(["src/b/"], 3)], shared))
        self.assertTrue(lanes.side_by_side((["src/a/"], 3), [(["docs/"], 2)], shared))
        self.assertFalse(lanes.side_by_side((["src/a/"], 3), [(["*.md"], 2)], shared))


class Scoped(unittest.TestCase):
    def test_lane_keys_are_prefixed_and_run_keys_are_shared(self):
        root = {"owner": "o", "L1.phase": "build", "L2.phase": "review"}
        one = lanes.Scoped(root, 1)
        self.assertEqual(one.get("phase"), "build")
        self.assertEqual(one["owner"], "o")
        one["round"] = 2
        one["done"] = 5
        one.update({"base": "abc"})
        one.setdefault("runs", 0)
        self.assertEqual(root["L1.round"], 2)
        self.assertEqual(root["done"], 5)
        self.assertEqual(root["L1.base"], "abc")
        self.assertIn("runs", root)
        self.assertNotIn("phase", root)
        one.clear()
        self.assertEqual(root, {"owner": "o", "L2.phase": "review", "done": 5, "runs": 0})


class AppendOnlyMerge(unittest.TestCase):
    def setUp(self):
        self.repo = Repo(tickets=())
        self.addCleanup(self.repo.close)

    def branch(self, name, path, text):
        self.repo.git("checkout", "-q", "-b", name, self.base)
        with open(str(self.repo.path(path)), "a", encoding="utf-8") as handle:
            handle.write(text)
        self.repo.commit(name)

    def merge(self, path_a, text_a, path_b, text_b):
        self.base = self.repo.git("rev-parse", "--abbrev-ref", "HEAD")
        self.branch("one", path_a, text_a)
        self.repo.git("checkout", "-q", self.base)
        self.branch("two", path_b, text_b)
        subprocess.run(["git", "merge", "-q", "--no-edit", "one"], cwd=str(self.repo.dir),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return lanes.resolve_appends(self.repo.dir, "plans/f")

    def test_two_appends_keep_both(self):
        left = self.merge("plans/f/learnings.md", "- (01) one\n", "plans/f/learnings.md", "- (02) two\n")
        self.assertEqual(left, [])
        text = self.repo.path("plans/f/learnings.md").read_text(encoding="utf-8")
        self.assertTrue(text.endswith("- (02) two\n- (01) one\n"), text)
        self.assertNotIn("<<<<<<<", text)

    def test_an_edit_that_is_not_an_append_is_left(self):
        path = self.repo.path("plans/f/map.md")
        path.write_text("changed\n", encoding="utf-8")
        self.repo.commit("rewrite on the base")
        self.base = self.repo.git("rev-parse", "--abbrev-ref", "HEAD")
        self.repo.git("checkout", "-q", "-b", "one")
        path.write_text("rewritten\n", encoding="utf-8")
        self.repo.commit("one")
        self.repo.git("checkout", "-q", self.base)
        self.repo.git("checkout", "-q", "-b", "two")
        path.write_text("changed\nappended\n", encoding="utf-8")
        self.repo.commit("two")
        subprocess.run(["git", "merge", "-q", "--no-edit", "one"], cwd=str(self.repo.dir),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(lanes.resolve_appends(self.repo.dir, "plans/f"), ["plans/f/map.md"])

    def test_a_conflict_outside_the_plan_files_is_left(self):
        self.repo.path("code.txt").write_text("base\n", encoding="utf-8")
        self.repo.commit("code")
        self.assertEqual(self.merge("code.txt", "one\n", "code.txt", "two\n"), ["code.txt"])


class StatusReady(unittest.TestCase):
    def run_status(self, repo, mode):
        lines = []

        class Out:
            def write(self, text):
                lines.append(text)
        cwd = os.getcwd()
        os.chdir(str(repo.dir))
        try:
            code = status.run(["f", mode], Out(), Out())
        finally:
            os.chdir(cwd)
        return code, "".join(lines)

    def test_ready_lists_every_ready_ticket(self):
        repo = Repo(tickets=(("01-a", "A", "—"), ("02-b", "B", "—"), ("03-c", "C", "01")))
        self.addCleanup(repo.close)
        self.assertEqual(self.run_status(repo, "--ready"),
                         (0, "plans/f/tasks/01-a.md\nplans/f/tasks/02-b.md\n"))
        self.assertEqual(self.run_status(repo, "--next"), (0, "plans/f/tasks/01-a.md\n"))
        for slug in ("01-a", "02-b", "03-c"):
            repo.set_status("plans/f/tasks/%s.md" % slug, "resolved")
        self.assertEqual(self.run_status(repo, "--ready")[0], 10)

    def test_check_refuses_an_empty_touches_line(self):
        repo = Repo(tickets=(("01-a", "A", "—"),))
        self.addCleanup(repo.close)
        path = repo.path("plans/f/tasks/01-a.md")
        path.write_text(path.read_text(encoding="utf-8").replace("Test first: no\n", "Test first: no\nTouches: \n"),
                        encoding="utf-8")
        code, out = self.run_status(repo, "--check")
        self.assertNotEqual(code, 0)
        self.assertIn("Touches must name at least one path", out)


if __name__ == "__main__":
    unittest.main()
