import os
import sys
import unittest

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import git  # the package under test, from this checkout


class DiffSizeTests(unittest.TestCase):
    def setUp(self):
        self.repo = helpers.Repo(local=False)
        self.cwd = os.getcwd()
        os.chdir(str(self.repo.dir))
        self.base = self.repo.head()

    def tearDown(self):
        os.chdir(self.cwd)
        self.repo.close()

    def write(self, rel, data):
        path = self.repo.path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            path.write_bytes(data)
        else:
            path.write_text(data, encoding="utf-8")

    def size(self):
        return git.diff_size(self.base, self.repo.head(), "plans/f/")

    def test_two_text_files_count_added_plus_removed_lines(self):
        self.write("a.txt", "one\ntwo\nthree\n")
        self.write("b.txt", "x\n")
        self.repo.commit("start")
        self.base = self.repo.head()
        self.write("a.txt", "one\nTWO\nthree\nfour\n")  # 1 removed, 2 added
        self.write("b.txt", "x\ny\n")  # 1 added
        self.repo.commit("work")
        self.assertEqual(self.size(), (2, 4, False))

    def test_a_change_inside_the_excluded_folder_counts_nothing(self):
        self.repo.set_status("plans/f/tasks/01-a.md", "resolved")
        self.write("plans/f/map.md", "# Map: f\n\n## Decisions so far\n\n01 — done\n")
        self.repo.commit("resolve")
        self.assertEqual(self.size(), (0, 0, False))

    def test_a_binary_file_is_flagged(self):
        self.write("image.bin", b"\x00\x01\x02\xff\x00binary\x00")
        self.write("c.txt", "c\n")
        self.repo.commit("binary")
        files, lines, binary = self.size()
        self.assertEqual((files, lines), (2, 1))
        self.assertTrue(binary)

    def test_a_rename_counts_as_a_delete_plus_an_add_even_with_diff_renames_set(self):
        self.write("old.txt", "".join("line %d\n" % i for i in range(10)))
        self.repo.commit("start")
        self.base = self.repo.head()
        self.repo.git("config", "diff.renames", "true")
        self.repo.git("mv", "old.txt", "new.txt")
        self.repo.commit("rename")
        self.assertEqual(self.size(), (2, 20, False))

    def test_a_git_error_raises_runtime_error(self):
        with self.assertRaises(RuntimeError):
            git.diff_size("no-such-revision", self.repo.head(), "plans/f/")


if __name__ == "__main__":
    unittest.main()
