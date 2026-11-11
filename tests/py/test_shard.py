"""tests/shard.py: the shards cover every test file once, and `all` runs them side by side, apart."""

import importlib.util
import subprocess
import sys
import unittest
from unittest import mock
from pathlib import Path

import helpers


def load():
    spec = importlib.util.spec_from_file_location("flow_shard", str(helpers.ROOT / "tests" / "shard.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Shards(unittest.TestCase):
    def setUp(self):
        self.shard = load()

    def test_every_test_file_is_in_exactly_one_shard(self):
        files = sorted(p.stem for p in (helpers.ROOT / "tests" / "py").glob("test_*.py"))
        for n in (1, 4):
            dealt = [name for part in self.shard.shards(n) for name in part]
            self.assertEqual(sorted(dealt), files)

    def run_all(self, script, n=3):
        said = []

        def command(k, total, verbose):
            return [sys.executable, "-c", script, str(k)]
        code = self.shard.every(n, False, say=said.append, command=command)
        return code, "\n".join(said)

    def test_all_passes_when_every_shard_passes(self):
        code, said = self.run_all("import sys; print('shard', sys.argv[1])")
        self.assertEqual(code, 0, said)
        self.assertIn("shards: all 3 passed in ", said)
        for k in (1, 2, 3):
            self.assertIn("shard %d of 3 passed in " % k, said)

    def test_one_failed_shard_fails_all_and_shows_its_output(self):
        code, said = self.run_all("import sys; print('out of', sys.argv[1]); sys.exit(sys.argv[1] == '2')")
        self.assertEqual(code, 1)
        self.assertIn("shard 2 of 3 FAILED in ", said)
        self.assertIn("out of 2", said)
        self.assertNotIn("out of 1", said)
        self.assertIn("shards: 1 of 3 failed (2) in ", said)

    def test_each_shard_has_its_own_temp_folder(self):
        script = ("import os, sys, tempfile; d = tempfile.gettempdir();"
                  "sys.exit(not (os.path.isdir(d) and os.environ['TMP'] == os.environ['TEMP'] == d))")
        said, seen = [], []
        real = subprocess.Popen

        def watch(args, **kw):
            seen.append(kw["env"]["TMPDIR"])
            return real(args, **kw)
        with mock.patch.object(self.shard.subprocess, "Popen", watch):
            code = self.shard.every(3, False, say=said.append, command=lambda k, n, v: [sys.executable, "-c", script])
        self.assertEqual(code, 0, said)
        self.assertEqual(len(set(seen)), 3, seen)
        self.assertFalse(any(Path(d).exists() for d in seen), "the temp folders are left behind")

    def test_bad_arguments_are_a_usage_error(self):
        for args in (["all", "0"], ["all", "x"], ["all", "2", "3"], ["5", "4"], []):
            self.assertEqual(self.shard.main(args), 2, args)


if __name__ == "__main__":
    unittest.main()
