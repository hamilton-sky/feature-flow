import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

ROOT = helpers.ROOT
COPIES = (".feature-flow/feature_flow/", ".feature-flow/guides/", ".feature-flow/agents/")


def _lf(data):
    return data.replace(b"\r\n", b"\n")


def _lf_copy(dst):
    """The source tree with LF line endings, whatever the checkout did: a Windows checkout has CRLF
    files, and the installer's text transforms are only meant for the LF files of a wheel or a clone."""
    skip = shutil.ignore_patterns(".git", ".feature-flow", "plans", "tests", "__pycache__", "*.pyc", "dist", "build")
    shutil.copytree(str(ROOT), str(dst), ignore=skip)
    for path in Path(dst).rglob("*"):
        if path.is_file():
            data = path.read_bytes()
            if b"\0" not in data and b"\r\n" in data:
                path.write_bytes(_lf(data))


class OwnInstallTests(unittest.TestCase):
    def test_the_used_installed_files_match_a_fresh_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / "source", Path(tmp) / "target"
            target.mkdir()
            _lf_copy(source)
            done = subprocess.run([sys.executable, str(source / "install.py"), str(target), "--agent", "all"],
                                  capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            written = [p for top in (".claude", ".agents") for p in sorted((target / top).rglob("*")) if p.is_file()]
            self.assertTrue(written)
            for path in written:
                rel = path.relative_to(target)
                mine = ROOT / rel
                self.assertTrue(mine.is_file(), "%s is missing here: run install.py . --agent all --force" % rel.as_posix())
                self.assertEqual(_lf(mine.read_bytes()), _lf(path.read_bytes()),
                                 "%s differs from the source: run install.py . --agent all --force" % rel.as_posix())

    def test_nothing_tracked_under_feature_flow_is_a_copy_of_the_source(self):
        tracked = subprocess.run(["git", "ls-files", ".feature-flow"], cwd=str(ROOT),
                                 capture_output=True, text=True, check=True).stdout.splitlines()
        copies = [t for t in tracked if t.startswith(COPIES)]
        self.assertEqual(copies, [], "these are unused copies of the source: git rm them")


if __name__ == "__main__":
    unittest.main()
