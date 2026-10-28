"""The brainstorm's review page: feature-flow's side of it (feature_flow/brainstorm_page.py).

Forkboard (packages/forkboard/) makes the page and has its own tests; these check what feature-flow does: read the
brainstorm's conventions into a review document, pick the style, find Forkboard, and write a version back.
"""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import brainstorm_page as page  # the module under test, from this checkout
from feature_flow import studio

BRAINSTORM = """# Brainstorm: csv

Picked by: person
Style: blueprint

## Idea

Admins want a **CSV** of every task. See [the docs](https://docs.python.org/3/library/csv.html).

## Options

### A. Stream it

```mermaid
flowchart LR
  Admin([Admin]) -->|clicks Export| Api[Export endpoint]
  Api --> Db[(Tasks table)]
  Api -- streams rows --> Admin
```

- Pros: small

### B. In the background

```mermaid
sequenceDiagram
  Admin->>Api: export
```

## Chosen

B. Big exports are common.

## Open

- <script>alert(1)</script> and [bad](javascript:alert(1))
"""


SKETCH = """# Brainstorm: csv

## Sketch

```mermaid
flowchart LR
  Admin([Admin]) -->|clicks Export| Api[Export endpoint]
  Api --> Db[(Tasks table)]
```

## Options

### A. Stream it

```mermaid
sequenceDiagram
  Admin->>Api: export
```

### B. In the background

```mermaid
flowchart TD
  Api[Api] --> Queue{{Queue}}
  class Queue amber
```
"""

DANA = {"dir": "LR", "nodes": [{"id": "Admin", "label": "Admin", "shape": "stadium", "colour": ""},
                               {"id": "Api", "label": "Export \"API\"", "shape": "rect", "colour": "red"},
                               {"id": "N4", "label": "Cache", "shape": "cylinder", "colour": ""}],
        "edges": [{"from": "Admin", "to": "Api", "label": "clicks Export", "style": "arrow"},
                  {"from": "Api", "to": "N4", "label": "", "style": "dotted"}]}



fb = studio.load()


def saved():
    """A state as the page saves it: Dana's version of the sketch and two asks, one answered."""
    st = fb.live.state(page.document(SKETCH, "csv"))
    st["figures"]["1"]["versions"]["u_dana"] = {"graph": DANA, "pos": {}, "at": "2026-10-26T22:00:00Z", "via": ["hand", "claude"]}
    st["asks"] = [{"by": "u_dana", "at": "2026-10-26T22:01:00Z", "figure": "1", "version": "u_dana", "text": "Is a cache worth it?"},
                  {"by": "u_me", "at": "2026-10-26T22:02:00Z", "figure": None, "version": None, "text": "Old one", "answer": "Done."}]
    return st


class Document(unittest.TestCase):
    def test_the_brainstorm_conventions_become_a_review_document(self):
        doc = page.document(BRAINSTORM, "csv")
        self.assertEqual((doc["schema"], doc["id"], doc["kind"], doc["title"]), ("bundle/1", "csv", "Brainstorm", "Brainstorm: csv"))
        self.assertEqual(doc["meta"], {"picked by": "person", "style": "blueprint"})
        self.assertEqual([(s["title"], s["kind"]) for s in doc["sections"]],
                         [("Idea", "text"), ("Options", "text"), ("Chosen", "chosen"), ("Open", "open")])
        options = doc["sections"][1]["items"]
        self.assertEqual([(i["label"], i["chosen"]) for i in options], [("A", False), ("B", True)])
        self.assertIn("```mermaid", options[0]["markdown"])
        self.assertEqual(fb.doc.check(doc), doc)

    def test_risks_for_the_planner_is_a_callout(self):
        doc = page.document("# B\n\n## Risks for the planner\n\n- slow\n", "x")
        self.assertEqual(doc["sections"][0]["kind"], "callout")

    def test_forkboard_is_found_in_this_checkout_and_reads_this_format(self):
        self.assertIsNotNone(fb)
        self.assertEqual(fb.SCHEMA, studio.MAJOR)
        self.assertEqual(Path(fb.__file__).resolve().parent, helpers.ROOT / "packages" / "forkboard" / "forkboard")


class Apply(unittest.TestCase):
    def test_apply_puts_a_version_into_the_brainstorm_file(self):
        text, dropped = page.apply(SKETCH, fb, saved(), "1", "u_dana")
        self.assertIn('N4[("Cache")]', text)
        self.assertNotIn("Tasks table", text)
        self.assertIn("sequenceDiagram", text)  # the other diagrams stay as they were
        self.assertEqual(dropped, [])
        with self.assertRaises(ValueError):  # the file changed since this state was built: apply would hit a diagram nobody saw
            page.apply(text, fb, saved(), "1", "original")
        fresh = fb.live.state(page.document(text, "csv"), saved())
        self.assertIn("Export", page.apply(text, fb, fresh, "1", "original")[0])
        for figure, version in (("1", "u_nobody"), ("2", "original"), ("9", "original")):
            with self.assertRaises(ValueError):
                page.apply(SKETCH, fb, saved(), figure, version)

    def test_apply_names_what_the_rewrite_dropped(self):
        text = SKETCH.replace("  Api --> Db[(Tasks table)]\n", "  Api --> Db[(Tasks table)]\n  %% why\n  style Db fill:#fff\n")
        st = fb.live.state(page.document(text, "csv"))
        self.assertEqual(page.apply(text, fb, st, "1", "original")[1], ["comments", "style"])


class Command(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name).resolve()  # macOS: /var is /private/var, and git names the real path
        subprocess.run(["git", "init", "-q", str(self.dir)], check=True)
        self.cwd = os.getcwd()
        os.chdir(str(self.dir))
        self.state = self.dir / ".feature-flow" / "state" / "brainstorm-csv.md"
        self.state.parent.mkdir(parents=True)
        self.state.write_text(BRAINSTORM, encoding="utf-8")

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def run_page(self, *args):
        out, err = io.StringIO(), io.StringIO()
        return page.main(list(args), out, err), out.getvalue(), err.getvalue()

    def test_it_writes_the_page_beside_the_brainstorm_in_its_style(self):
        code, out, err = self.run_page("csv")
        self.assertEqual(code, 0, err)
        written = self.state.with_suffix(".html")
        self.assertEqual(out, "wrote %s\n" % written.as_posix())
        text = written.read_text(encoding="utf-8")
        self.assertIn("style blueprint", text)
        self.assertIn("Archivo", text)

    def test_the_flag_wins_over_the_style_line_and_the_line_over_flow_style(self):
        os.environ["FLOW_STYLE"] = "route"
        try:
            self.run_page("csv")
            self.assertIn("style blueprint", self.state.with_suffix(".html").read_text(encoding="utf-8"))
            self.state.write_text(BRAINSTORM.replace("Style: blueprint\n", ""), encoding="utf-8")
            self.run_page("csv")
            self.assertIn("style route", self.state.with_suffix(".html").read_text(encoding="utf-8"))
        finally:
            del os.environ["FLOW_STYLE"]
        self.run_page("csv", "--style", "route")
        self.assertIn("Bricolage", self.state.with_suffix(".html").read_text(encoding="utf-8"))

    def test_the_committed_brainstorm_wins_once_the_plan_exists(self):
        plan = self.dir / "plans" / "csv"
        plan.mkdir(parents=True)
        (plan / "brainstorm.md").write_text(BRAINSTORM.replace("## Idea", "## Idea\n\nThe committed one."),
                                            encoding="utf-8")
        code, out, _ = self.run_page("csv", "--fragment")
        self.assertEqual(out, "wrote %s\n" % (plan / "brainstorm.html").as_posix())
        self.assertIn("The committed one.", (plan / "brainstorm.html").read_text(encoding="utf-8"))

    def test_mistakes_say_what_to_do(self):
        self.assertEqual(self.run_page("csv", "--style", "neon")[0], 1)
        self.assertIn("no style neon: pick one of blueprint, route", self.run_page("csv", "--style", "neon")[2])
        code, _, err = self.run_page("other")
        self.assertEqual(code, 1)
        self.assertIn("no brainstorm for other", err)
        self.assertEqual(self.run_page()[0], 2)
        self.assertEqual(self.run_page("a/b")[0], 2)
        self.assertEqual(self.run_page("csv", "--bogus")[0], 2)

    def test_flow_status_and_the_cli_reach_it(self):
        env = dict(os.environ, PYTHONPATH=str(helpers.ROOT))
        for argv in ([sys.executable, str(helpers.ROOT / "scripts" / "flow-status.py"), "csv", "--brainstorm-page"],
                     [sys.executable, "-m", "feature_flow", "brainstorm-page", "csv", "--style", "route"]):
            result = subprocess.run(argv, cwd=str(self.dir), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    universal_newlines=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("brainstorm-csv.html", result.stdout)


class LiveCommand(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name).resolve()
        subprocess.run(["git", "init", "-q", str(self.dir)], check=True)
        self.cwd = os.getcwd()
        os.chdir(str(self.dir))
        self.file = self.dir / ".feature-flow" / "state" / "brainstorm-csv.md"
        self.file.parent.mkdir(parents=True)
        self.file.write_text(SKETCH, encoding="utf-8")

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def run_page(self, *args):
        out, err = io.StringIO(), io.StringIO()
        return page.main(list(args), out, err), out.getvalue(), err.getvalue()

    def test_live_writes_the_page_and_its_state_and_keeps_saved_work(self):
        folder = self.dir / "live"
        rc, out, _ = self.run_page("csv", "--live", str(folder))
        self.assertEqual(rc, 0)
        index = (folder / "index.html").read_text(encoding="utf-8")
        self.assertTrue(index.startswith("<title>"))
        self.assertIn('data-live="1"', index)
        self.assertIn("round 1, 2 figures, 0 open asks", out)
        (folder / "state.json").write_text(json.dumps(saved()), encoding="utf-8")
        rc, out, _ = self.run_page("csv", "--live", str(folder))
        self.assertIn("round 2, 2 figures, 1 open asks", out)

    def test_asks_answer_and_apply_from_the_command_line(self):
        st = self.dir / "state.json"
        st.write_text(json.dumps(saved()), encoding="utf-8")
        rc, out, _ = self.run_page("csv", "--asks", str(st))
        self.assertIn("Is a cache worth it?", out)
        self.assertEqual(self.run_page("csv", "--answer", str(st), "1", "Yes.")[0], 0)
        self.assertEqual(json.loads(st.read_text())["asks"][0]["answer"], "Yes.")
        rc, _, err = self.run_page("csv", "--answer", str(st), "one", "Yes.")
        self.assertEqual(rc, 1)
        self.assertIn("must be a number", err)
        self.assertEqual(self.run_page("csv", "--apply", str(st), "1", "u_dana")[0], 0)
        self.assertIn("Cache", self.file.read_text(encoding="utf-8"))
        rc, _, err = self.run_page("csv", "--asks", str(self.dir / "missing.json"))
        self.assertEqual(rc, 1)
        self.assertIn("no page state", err)

    def test_without_forkboard_it_says_how_to_get_it(self):
        real = studio.load
        studio.load = lambda: None
        try:
            rc, _, err = self.run_page("csv")
        finally:
            studio.load = real
        self.assertEqual(rc, 1)
        self.assertIn("forkboard is not here", err)


if __name__ == "__main__":
    unittest.main()
