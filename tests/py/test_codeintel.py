"""codeintel, when installed and ready, reaches the scout's and the reviewer's prompts, and eval counts its use."""

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import codeintel, evaluate, prompts, scouts, state  # the package under test, from this checkout

DOCTOR = {"engines": {"graph": {"status": "ok"}, "semantic": {"status": "ok"}, "lsp": {"status": "warn"}}}
FAKE = """import json, sys
from pathlib import Path
with open(%r, "a") as calls:
    calls.write(" ".join(sys.argv[1:]) + "\\n")
sys.stdout.write(Path(%r).read_text())
"""


class FakeCodeintel(unittest.TestCase):
    """A `codeintel` on PATH whose doctor prints self.answer and counts its calls."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name).resolve()
        self.repo, bin_dir = root / "repo", root / "bin"
        self.repo.mkdir()
        bin_dir.mkdir()
        self.calls, self.answer = root / "calls.txt", root / "doctor.json"
        self.answer.write_text(json.dumps(DOCTOR), encoding="utf-8")
        script = bin_dir / "fake.py"
        script.write_text(FAKE % (str(self.calls), str(self.answer)), encoding="utf-8")
        if sys.platform == "win32":
            (bin_dir / "codeintel.cmd").write_text('@"%s" "%s" %%*\r\n' % (sys.executable, script), encoding="utf-8")
        else:
            exe = bin_dir / "codeintel"
            exe.write_text('#!/bin/sh\nexec "%s" "%s" "$@"\n' % (sys.executable, script), encoding="utf-8")
            exe.chmod(0o755)
        self.env = {"PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", ""), "FLOW_CODEINTEL": "auto"}
        saved = {k: os.environ.get(k) for k in self.env}
        os.environ.update(self.env)
        self.addCleanup(self.restore, saved)

    @staticmethod
    def restore(saved):
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def doctor_runs(self):
        return len(self.calls.read_text(encoding="utf-8").splitlines()) if self.calls.exists() else 0


class ReadyTests(FakeCodeintel):
    def test_the_engines_the_doctor_calls_ok(self):
        self.assertEqual(codeintel.ready(self.repo), ["graph", "semantic"])
        self.assertIn("doctor --json", self.calls.read_text(encoding="utf-8"))

    def test_the_answer_is_kept_for_an_hour(self):
        codeintel.ready(self.repo)
        codeintel.ready(self.repo)
        self.assertEqual(self.doctor_runs(), 1)
        cache = self.repo / state.STATE_DIR / codeintel.CACHE
        saved = json.loads(cache.read_text(encoding="utf-8"))
        saved["checked"] -= codeintel.FRESH + 1
        cache.write_text(json.dumps(saved), encoding="utf-8")
        codeintel.ready(self.repo)
        self.assertEqual(self.doctor_runs(), 2)

    def test_off_missing_or_broken_is_no_engine(self):
        os.environ["FLOW_CODEINTEL"] = "off"
        self.assertEqual(codeintel.ready(self.repo), [])
        self.assertEqual(self.doctor_runs(), 0)
        os.environ["FLOW_CODEINTEL"] = "auto"
        self.answer.write_text("not json", encoding="utf-8")
        self.assertEqual(codeintel.ready(self.repo), [])
        os.environ["PATH"] = str(self.repo)
        self.assertEqual(codeintel.ready(self.repo), [])

    def test_nothing_ready_is_no_section(self):
        self.answer.write_text(json.dumps({"engines": {"graph": {"status": "fail"}}}), encoding="utf-8")
        self.assertEqual(codeintel.note("scout", self.repo), "")


class PromptTests(FakeCodeintel):
    def test_the_reviewer_is_told_to_ask_what_the_change_left_behind(self):
        text = codeintel.note("reviewer", self.repo, "abc123")
        self.assertIn("codeintel query --op changed --target abc123", text)
        self.assertIn("codeintel: <op> <target>: helped | no answer | wrong", text)
        self.assertIn("`search` (semantic engine)", text)

    def test_the_scout_gets_the_section_and_the_web_scout_does_not(self):
        os.chdir(str(self.repo))
        self.addCleanup(os.chdir, str(helpers.ROOT))
        self.assertIn("## codeintel", scouts.prompt("role", "builder", "q", codeintel=True))
        self.assertIn("--op callers", scouts.prompt("role", "builder", "q", codeintel=True))
        self.assertNotIn("codeintel", scouts.prompt("role", "planner", "q"))

    def test_reviews_get_the_section_and_builds_do_not(self):
        os.chdir(str(self.repo))
        self.addCleanup(os.chdir, str(helpers.ROOT))
        scripts = helpers.ROOT / "scripts"
        review = prompts.build("review", scripts, "f", "plans/f/tasks/01-a.md", "01", "abc123")
        self.assertIn("--op changed --target abc123", review)
        self.assertTrue(review.rstrip().endswith("wrong: <what it got wrong>"))
        self.assertIn("--op changed --target b4se", prompts.feature_review(scripts, "f", "plans/f", "b4se", ["01"]))
        self.assertNotIn("codeintel", prompts.build("build", scripts, "f", "plans/f/tasks/01-a.md", "01", "abc123"))


def said(text, mid="m"):
    return {"message": {"id": mid, "content": [{"type": "text", "text": text}]}}


def asked(command, tid, name="Bash"):
    return {"message": {"id": tid, "content": [{"type": "tool_use", "id": tid, "name": name, "input": command}]}}


class UseTests(unittest.TestCase):
    def test_it_counts_queries_and_what_the_agents_said(self):
        found = codeintel.use([
            asked({"command": "codeintel query --op callers --target save"}, "t1"),
            asked({"command": "codeintel query --op callers --target save"}, "t1"),  # the same call logged twice
            asked({"command": "cd x && codeintel query --target 'auth' --op search"}, "t2"),
            asked({"op": "impact", "target": "load"}, "t3", name="mcp__codeintel__code_query"),
            asked({"command": "grep -rn codeintel ."}, "t4"),
            said("## Unsure\n- none\ncodeintel: callers save: helped\n- codeintel: search `auth`: wrong: named a test "
                 "helper\ncodeintel: <op> <target>: helped | no answer | wrong: <what it got wrong>\nREVIEW: PASS"),
            said("codeintel: callers save: helped"),  # the session quoting the scout's line
            said("codeintel: impact load: no answer"),
        ])
        self.assertEqual(found["queries"], {"callers": 1, "search": 1, "impact": 1})
        self.assertEqual(found["said"], {"helped": 1, "wrong": 1, "no answer": 1})
        self.assertEqual(found["wrong"], [{"op": "search", "target": "auth", "why": "named a test helper"}])

    def test_no_use_is_none(self):
        self.assertIsNone(codeintel.use([said("nothing here"), {"message": "x"}, "junk"]))


class EvalTests(unittest.TestCase):
    def setUp(self):
        self.repo = helpers.Repo(local=False)
        self.cwd = os.getcwd()
        os.chdir(str(self.repo.dir))
        self.addCleanup(self.repo.close)
        self.addCleanup(os.chdir, self.cwd)
        self.home = tempfile.TemporaryDirectory()
        self.addCleanup(self.home.cleanup)
        folder = state.state_dir(self.repo.dir)
        (folder / "flow-f.log").write_text("2026-10-23T10:00:00Z,-,START\n2026-10-23T10:00:10Z,01,BUILD\n"
                                           "2026-10-23T10:09:00Z,01,VERDICT-PASS\n", encoding="utf-8")
        project = Path(self.home.name) / "projects" / "-tmp-x"
        project.mkdir(parents=True)
        cwd = str(self.repo.dir.resolve())
        lines = [dict(asked({"command": "codeintel query --op changed --target abc"}, "t1"),
                      cwd=cwd, timestamp="2026-10-23T10:01:00Z"),
                 dict(said("codeintel: changed abc: wrong: missed a caller in cli.py"),
                      cwd=cwd, timestamp="2026-10-23T10:02:00Z")]
        (project / "s.jsonl").write_text("\n".join(json.dumps(l) for l in lines) + "\n", encoding="utf-8")

    def run_eval(self):
        out, err = io.StringIO(), io.StringIO()
        code = evaluate.main(["f", "--claude-home", self.home.name], out, err)
        self.assertEqual(code, 0, err.getvalue())
        return out.getvalue()

    def test_the_record_the_summary_and_the_form_carry_codeintel(self):
        out = self.run_eval()
        plan = self.repo.dir / "plans" / "f"
        record = json.loads((plan / "eval.json").read_text(encoding="utf-8"))
        self.assertEqual(record["codeintel"]["queries"], {"changed": 1})
        self.assertEqual(record["codeintel"]["wrong"][0]["why"], "missed a caller in cli.py")
        self.assertIn("codeintel: 1 query (changed x1); the agents said wrong x1", out)
        form = plan / "eval-verdict.md"
        text = form.read_text(encoding="utf-8")
        self.assertIn("codeintel: (helped | no difference | misled", text)
        form.write_text(text.replace("codeintel: (helped", "codeintel: misled\nx: (helped"), encoding="utf-8")
        self.assertIn("codeintel misled", self.run_eval())
        record = json.loads((plan / "eval.json").read_text(encoding="utf-8"))
        self.assertEqual(record["verdict"]["codeintel"], "misled")

    def test_a_run_without_codeintel_asks_nothing_about_it(self):
        (Path(self.home.name) / "projects" / "-tmp-x" / "s.jsonl").write_text("", encoding="utf-8")
        out = self.run_eval()
        self.assertNotIn("codeintel", out)
        self.assertNotIn("codeintel", (self.repo.dir / "plans" / "f" / "eval-verdict.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
