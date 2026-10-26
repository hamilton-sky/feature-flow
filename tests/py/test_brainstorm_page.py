"""0.24.0: the brainstorm as a review page (feature_flow/brainstorm_page.py)."""

import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import brainstorm_page as page  # the module under test, from this checkout

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


class Parsing(unittest.TestCase):
    def test_a_flowchart_becomes_nodes_and_edges(self):
        graph = page.flowchart("flowchart LR\n  A([Admin]) -->|clicks| B[Api]\n  B --> C[(Db)]\n  B -.-> D{Ok?}\n"
                               "  D == yes ==> E((Done))\n  B -- rows --> A\n  E --- F{{Queue}}\n")
        self.assertEqual(graph["dir"], "LR")
        shapes = {n["id"]: (n["label"], n["shape"]) for n in graph["nodes"]}
        self.assertEqual(shapes, {"A": ("Admin", "stadium"), "B": ("Api", "rect"), "C": ("Db", "cylinder"),
                                  "D": ("Ok?", "diamond"), "E": ("Done", "circle"), "F": ("Queue", "hexagon")})
        edges = [(e["from"], e["to"], e["label"], e["style"]) for e in graph["edges"]]
        self.assertIn(("A", "B", "clicks", "arrow"), edges)
        self.assertIn(("B", "D", "", "dotted"), edges)
        self.assertIn(("B", "A", "rows", "arrow"), edges)
        self.assertIn(("E", "F", "", "open"), edges)

    def test_class_lines_with_a_palette_name_colour_the_boxes(self):
        graph = page.flowchart("flowchart LR\n  A --> B --> C\n  classDef amber fill:#fff\n  class A,B amber\n"
                               "  class C fancy\n  class Z teal\n")
        self.assertEqual({n["id"]: n.get("colour") for n in graph["nodes"]}, {"A": "amber", "B": "amber", "C": None})
        self.assertIn("g.node.c-amber .shape", page.PALETTE_CSS)
        self.assertEqual(sorted(json.loads(page.PALETTE_JS.split("=", 1)[1].rstrip(";"))),
                         sorted(c[0] for c in page.COLOURS))

    def test_a_chain_on_one_line_links_each_pair(self):
        graph = page.flowchart("graph TD\n  A --> B --> C\n")
        self.assertEqual(graph["dir"], "TD")
        self.assertEqual([(e["from"], e["to"]) for e in graph["edges"]], [("A", "B"), ("B", "C")])

    def test_what_it_cannot_lay_out_is_left_to_mermaid(self):
        self.assertIsNone(page.flowchart("sequenceDiagram\n  A->>B: hi\n"))
        self.assertIsNone(page.flowchart("flowchart LR\n  A --> \n"))


class Rendering(unittest.TestCase):
    def setUp(self):
        self.html = page.render(BRAINSTORM, "csv", "/* fonts: https://fonts.googleapis.com/css2?family=X */\n:root{}",
                                "blueprint")

    def test_the_sidebar_routes_to_every_section_and_option(self):
        nav = self.html[self.html.index('<nav class="route"'):self.html.index("</nav>")]
        for target in ("#idea", "#options", "#a-stream-it", "#b-in-the-background", "#chosen", "#open"):
            self.assertIn('href="%s"' % target, nav)
        self.assertIn("0 of 4 sections read", nav)
        self.assertIn('data-theme-set="dark"', nav)
        self.assertIn('id="motion"', nav)

    def test_the_chosen_option_is_marked(self):
        self.assertIn('<article class="opt chosen" id="b-in-the-background">', self.html)
        self.assertIn('<article class="opt" id="a-stream-it">', self.html)

    def test_flowcharts_become_draggable_and_others_load_mermaid(self):
        self.assertEqual(self.html.count('class="dg graph"'), 1)
        data = re.search(r'<script type="application/json" class="graph-data">(.*?)</script>', self.html).group(1)
        self.assertEqual(len(json.loads(data)["nodes"]), 3)
        self.assertIn('<pre class="mermaid">sequenceDiagram', self.html)
        self.assertIn(page.MERMAID, self.html)

    def test_each_flowchart_can_be_edited_and_undone(self):
        tools = re.search(r'<div class="tools">(.*?)</div>', self.html).group(1)
        self.assertEqual(re.findall(r'data-act="(\w+)"', tools),
                         ["add", "shapes", "colour", "rename", "connect", "delete", "undo", "redo", "reset", "copy"])
        self.assertIn('<input class="rename"', tools)
        self.assertEqual(re.findall(r'data-shape="(\w+)"', tools),
                         ["rect", "round", "stadium", "diamond", "cylinder", "hexagon", "circle"])
        for name in ("function mermaid(g)", "function change(fn)", "function restore(from, to)", "'Delete'", "key === 'z'"):
            self.assertIn(name, page.BASE_JS)

    def test_text_is_escaped_and_only_web_links_survive(self):
        self.assertNotIn("<script>alert(1)</script>", self.html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", self.html)
        self.assertNotIn('href="javascript:', self.html)
        self.assertIn('<a href="https://docs.python.org/3/library/csv.html">the docs</a>', self.html)
        self.assertIn("<b>CSV</b>", self.html)

    def test_a_label_cannot_close_the_data_script(self):
        text = BRAINSTORM.replace("Admin([Admin])", "Admin([</script><b>x])")
        out = page.render(text, "csv", ":root{}", "route")
        data = re.search(r'class="graph-data">(.*?)</script>', out).group(1)
        self.assertNotIn("<", data)
        self.assertEqual(json.loads(data)["nodes"][0]["label"], "</script><b>x")

    def test_the_style_supplies_the_fonts_and_the_page_its_own_layout(self):
        self.assertIn('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=X">', self.html)
        self.assertTrue(self.html.startswith("<!doctype html>"))
        bare = page.render(BRAINSTORM, "csv", ":root{}", "route", fragment=True)
        self.assertTrue(bare.startswith("<title>Brainstorm: csv</title>"))
        self.assertNotIn("<body>", bare)
        self.assertNotIn("<link", bare)


class Command(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
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
        return page.main(list(args), out, err, root=str(helpers.ROOT)), out.getvalue(), err.getvalue()

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


if __name__ == "__main__":
    unittest.main()
