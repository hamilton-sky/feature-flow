import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

ROOT = helpers.ROOT
COPIES = (".feature-flow/feature_flow/", ".feature-flow/guides/", ".feature-flow/agents/")


class OwnInstallTests(unittest.TestCase):
    def test_the_used_installed_files_match_a_fresh_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            done = subprocess.run([sys.executable, str(ROOT / "install.py"), tmp, "--agent", "all"],
                                  capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            written = [p for top in (".claude", ".agents") for p in sorted((Path(tmp) / top).rglob("*")) if p.is_file()]
            self.assertTrue(written)
            for path in written:
                rel = path.relative_to(tmp)
                mine = ROOT / rel
                self.assertTrue(mine.is_file(), "%s is missing here: run install.py . --agent all --force" % rel.as_posix())
                self.assertEqual(mine.read_bytes(), path.read_bytes(),
                                 "%s differs from the source: run install.py . --agent all --force" % rel.as_posix())

    def test_nothing_tracked_under_feature_flow_is_a_copy_of_the_source(self):
        tracked = subprocess.run(["git", "ls-files", ".feature-flow"], cwd=str(ROOT),
                                 capture_output=True, text=True, check=True).stdout.splitlines()
        copies = [t for t in tracked if t.startswith(COPIES)]
        self.assertEqual(copies, [], "these are unused copies of the source: git rm them")


if __name__ == "__main__":
    unittest.main()
