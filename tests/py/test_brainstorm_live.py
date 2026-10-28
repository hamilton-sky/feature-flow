"""0.25.0: the live brainstorm page people edit together and talk to Claude through (feature_flow/brainstorm_live.py)."""

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
from feature_flow import brainstorm_live as live  # the module under test, from this checkout
from feature_flow import brainstorm_page as page

BRAINSTORM = """# Brainstorm: csv

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


def saved():
    """A state as the page saves it: Dana's version of the sketch and two asks, one answered."""
    st = live.state(BRAINSTORM, "csv")
    st["figures"]["1"]["versions"]["u_dana"] = {"graph": DANA, "pos": {}, "at": "2026-10-26T22:00:00Z", "via": ["hand", "claude"]}
    st["asks"] = [{"by": "u_dana", "at": "2026-10-26T22:01:00Z", "figure": "1", "version": "u_dana", "text": "Is a cache worth it?"},
                  {"by": "u_me", "at": "2026-10-26T22:02:00Z", "figure": None, "version": None, "text": "Old one", "answer": "Done."}]
    return st


class State(unittest.TestCase):
    def test_flowcharts_become_figures_numbered_like_the_page(self):
        st = live.state(BRAINSTORM, "csv")
        self.assertEqual(sorted(st["figures"]), ["1", "3"])  # figure 2 is a sequence diagram: mermaid draws it, nobody edits it
        self.assertEqual(st["figures"]["1"]["title"], "Sketch")
        self.assertEqual(st["figures"]["3"]["title"], "B. In the background")
        self.assertEqual(st["figures"]["3"]["original"]["nodes"][1]["colour"], "amber")
        self.assertEqual((st["round"], st["asks"]), (1, []))

    def test_a_new_round_keeps_what_people_saved(self):
        again = live.state(BRAINSTORM.replace("Tasks table", "Tasks"), "csv", saved())
        self.assertEqual(again["round"], 2)
        self.assertIn("u_dana", again["figures"]["1"]["versions"])
        self.assertEqual(again["figures"]["1"]["original"]["nodes"][2]["label"], "Tasks")
        self.assertEqual(len(again["asks"]), 2)
        self.assertEqual(live.state(BRAINSTORM, "csv", "junk")["round"], 1)

    def test_titles_count_figures_like_the_page_even_after_other_fences(self):
        text = "## Code\n\n```python\nx = 1\n```\n\n## Flow\n\n```mermaid\nflowchart LR\n  A --> B\n```\n"
        self.assertEqual(live.titles(text), {1: "Flow"})
        self.assertEqual(live.state(text, "f")["figures"]["1"]["title"], "Flow")

    def test_what_a_rewrite_would_drop_is_named(self):
        self.assertEqual(live.lost("flowchart LR\n  %% note\n  subgraph S\n  A --> B\n  end\n  style A fill:#fff\n"
                                   "  classDef big font-size:20px\n  classDef red fill:#fff\n"),
                         ["comments", "subgraph", "style", "classDef"])
        self.assertEqual(live.lost("flowchart LR\n  A --> B\n  classDef red fill:#fff\n  class A red\n"), [])

    def test_mermaid_round_trips_shapes_labels_styles_and_colours(self):
        text = live.mermaid(DANA)
        self.assertIn('Api["Export #quot;API#quot;"]', text)
        self.assertIn('N4[("Cache")]', text)
        self.assertIn("Api -.-> N4", text)
        self.assertIn('Admin -->|"clicks Export"| Api', text)
        self.assertIn("class Api red", text)
        back = page.flowchart(text)
        self.assertEqual([(n["id"], n["shape"], n.get("colour")) for n in back["nodes"]],
                         [("Admin", "stadium", None), ("Api", "rect", "red"), ("N4", "cylinder", None)])


class Session(unittest.TestCase):
    def test_open_asks_show_who_where_and_their_version(self):
        text = live.asks(saved())
        self.assertIn("ask 1 from u_dana", text)
        self.assertIn("about figure 1 (Sketch)", text)
        self.assertIn("Is a cache worth it?", text)
        self.assertIn("their version of the figure (hand, claude)", text)
        self.assertIn('N4[("Cache")]', text)
        self.assertNotIn("Old one", text)

    def test_an_answer_closes_the_ask(self):
        st = live.answer(saved(), 1, "Only for exports over 10k rows.")
        self.assertEqual(live.asks(st), "no open asks")
        with self.assertRaises(ValueError):
            live.answer(st, 3, "x")

    def test_apply_puts_a_version_into_the_brainstorm_file(self):
        text = live.apply(BRAINSTORM, saved(), "1", "u_dana")
        self.assertIn('N4[("Cache")]', text)
        self.assertNotIn("Tasks table", text)
        self.assertIn("sequenceDiagram", text)  # the other diagrams stay as they were
        self.assertEqual(live.diagrams(text)[0][2]["nodes"][1]["colour"], "red")
        with self.assertRaises(ValueError):  # the file changed since this state was built: apply would hit a diagram nobody saw
            live.apply(text, saved(), "1", "original")
        fresh = live.state(text, "csv", saved())
        self.assertIn("Export", live.apply(text, fresh, "1", "original"))
        for figure, version in (("1", "u_nobody"), ("2", "original"), ("9", "original")):
            with self.assertRaises(ValueError):
                live.apply(BRAINSTORM, saved(), figure, version)


class Command(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name).resolve()  # macOS: /var is /private/var, and git names the real path
        subprocess.run(["git", "init", "-q", str(self.dir)], check=True)
        self.cwd = os.getcwd()
        os.chdir(str(self.dir))
        self.file = self.dir / ".feature-flow" / "state" / "brainstorm-csv.md"
        self.file.parent.mkdir(parents=True)
        self.file.write_text(BRAINSTORM, encoding="utf-8")

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def run_page(self, *args):
        out, err = io.StringIO(), io.StringIO()
        return page.main(list(args), out, err, root=str(helpers.ROOT)), out.getvalue(), err.getvalue()

    def test_live_writes_the_page_and_its_state_and_keeps_saved_work(self):
        folder = self.dir / "live"
        rc, out, _ = self.run_page("csv", "--live", str(folder))
        self.assertEqual(rc, 0)
        index = (folder / "index.html").read_text(encoding="utf-8")
        self.assertTrue(index.startswith("<title>"))  # a fragment: the artifact host adds the document around it
        self.assertIn('data-live="1"', index)
        self.assertIn("artifact.publish", index)
        self.assertIn("round 1, 2 figures, 0 open asks", out)
        (folder / "state.json").write_text(json.dumps(saved()), encoding="utf-8")
        rc, out, _ = self.run_page("csv", "--live", str(folder))
        self.assertIn("round 2, 2 figures, 1 open asks", out)
        self.assertNotIn('data-live', page.render(BRAINSTORM, "csv", ":root{}", "route"))

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


if __name__ == "__main__":
    unittest.main()
