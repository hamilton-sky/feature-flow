"""The forkboard command (forkboard/cli.py)."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import helpers
from forkboard import __version__, cli, live


class Command(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.doc = self.dir / "csv.json"
        self.doc.write_text(json.dumps(helpers.fixture("sketch")), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, stdin=None):
        out, err = io.StringIO(), io.StringIO()
        old = sys.stdin
        sys.stdin = io.StringIO(stdin or "")
        try:
            return cli.main(list(args), out, err), out.getvalue(), err.getvalue()
        finally:
            sys.stdin = old

    def test_render_writes_the_page_beside_the_document_or_to_stdout(self):
        code, out, err = self.run_cli("render", str(self.doc), "--theme", "blueprint")
        self.assertEqual(code, 0, err)
        self.assertIn("style blueprint", self.doc.with_suffix(".html").read_text(encoding="utf-8"))
        code, out, _ = self.run_cli("render", "-", "--fragment", stdin=self.doc.read_text(encoding="utf-8"))
        self.assertTrue(out.startswith("<title>Brainstorm: csv</title>"))

    def test_live_writes_the_page_and_its_state_and_keeps_saved_work(self):
        folder = self.dir / "live"
        code, out, _ = self.run_cli("live", str(self.doc), str(folder))
        self.assertEqual(code, 0)
        index = (folder / "index.html").read_text(encoding="utf-8")
        self.assertTrue(index.startswith("<title>"))  # a fragment: the artifact host adds the document around it
        self.assertIn('data-live="1"', index)
        self.assertIn("artifact.publish", index)
        self.assertIn("round 1, 2 figures, 0 open asks", out)
        st = json.loads((folder / "state.json").read_text(encoding="utf-8"))
        st["asks"] = [{"by": "u_dana", "figure": "1", "text": "Why?"}]
        (folder / "state.json").write_text(json.dumps(st), encoding="utf-8")
        code, out, _ = self.run_cli("live", str(self.doc), str(folder))
        self.assertIn("round 2, 2 figures, 1 open asks", out)

    def test_asks_answer_and_version_from_the_command_line(self):
        folder = self.dir / "live"
        self.run_cli("live", str(self.doc), str(folder))
        st = live.load(folder / "state.json")
        st["asks"] = [{"by": "u_dana", "figure": "1", "text": "Is a cache worth it?"}]
        (folder / "state.json").write_text(live.dump(st), encoding="utf-8")
        self.assertIn("Is a cache worth it?", self.run_cli("asks", str(folder))[1])
        self.assertEqual(self.run_cli("answer", str(folder), "1", "Yes.")[0], 0)
        self.assertEqual(live.load(folder / "state.json")["asks"][0]["answer"], "Yes.")
        code, _, err = self.run_cli("answer", str(folder), "one", "Yes.")
        self.assertEqual(code, 1)
        self.assertIn("must be a number", err)
        code, out, _ = self.run_cli("version", str(folder), "1", "original")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("flowchart LR"))

    def test_mistakes_say_what_to_do(self):
        code, _, err = self.run_cli("render", str(self.doc), "--theme", "neon")
        self.assertEqual(code, 1)
        self.assertIn("no theme neon: pick one of blueprint, bright, paper, route, sketch, terminal", err)
        bad = self.dir / "bad.json"
        bad.write_text(json.dumps({"schema": "bundle/2"}), encoding="utf-8")
        code, _, err = self.run_cli("render", str(bad))
        self.assertEqual(code, 1)
        self.assertIn("reads bundle/1 documents, not bundle/2", err)
        code, _, err = self.run_cli("asks", str(self.dir / "missing.json"))
        self.assertEqual(code, 1)
        self.assertIn("no page state", err)
        self.assertEqual(self.run_cli()[0], 2)
        self.assertEqual(self.run_cli("render")[0], 2)
        self.assertEqual(self.run_cli("render", str(self.doc), "--bogus")[0], 2)

    def test_python_m_forkboard_runs_it(self):
        env = dict(os.environ, PYTHONPATH=str(helpers.PACKAGE))
        result = subprocess.run([sys.executable, "-m", "forkboard", "--version"], env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(result.stdout, "forkboard %s\n" % __version__, result.stderr)
        result = subprocess.run([sys.executable, "-m", "forkboard", "themes"], env=env, stdout=subprocess.PIPE,
                                universal_newlines=True)
        names = [line.split()[0] for line in result.stdout.splitlines()]
        self.assertEqual(names, ["blueprint", "bright", "paper", "route", "sketch", "terminal"])
        self.assertIn("sketch     early, fuzzy ideas", result.stdout)


if __name__ == "__main__":
    unittest.main()
