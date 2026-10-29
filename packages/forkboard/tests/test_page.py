"""The review page (forkboard/page.py): a review document in, one self contained HTML file out."""

import json
import re
import unittest

import helpers
from forkboard import page

CSS = "/* fonts: https://fonts.googleapis.com/css2?family=X */\n:root{}"


class Rendering(unittest.TestCase):
    def setUp(self):
        self.doc = helpers.fixture("csv")
        self.html = page.render(self.doc, CSS, "blueprint")

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
        self.assertIn('<div class="callout good">', self.html)

    def test_flowcharts_become_draggable_and_others_load_mermaid(self):
        self.assertEqual(self.html.count('class="dg graph"'), 1)
        data = re.search(r'<script type="application/json" class="graph-data">(.*?)</script>', self.html).group(1)
        self.assertEqual(len(json.loads(data)["nodes"]), 3)
        self.assertIn('<pre class="mermaid">sequenceDiagram', self.html)
        self.assertIn(page.MERMAID, self.html)

    def test_each_flowchart_can_be_edited_and_undone(self):
        tools = re.search(r'<div class="tools">(.*?)</div>', self.html).group(1)
        self.assertEqual(re.findall(r'data-act="(\w+)"', tools),
                         ["add", "shapes", "colour", "arrange", "rename", "connect", "delete", "undo", "redo", "reset",
                          "copy"])
        self.assertEqual(re.findall(r'data-arrange="(\w+)"', tools), ["LR", "TD", "radial", "grid"])
        self.assertIn('<input class="rename"', tools)
        self.assertEqual(re.findall(r'data-shape="(\w+)"', tools),
                         ["rect", "round", "stadium", "diamond", "cylinder", "hexagon", "circle"])
        editor = page.asset("editor.js")
        for name in ("function mermaid(g)", "function change(fn, how)", "function radial(g)", "function grid(g)", "function restore(from, to)", "'Delete'", "key === 'z'"):
            self.assertIn(name, editor)
        self.assertIn(editor, self.html)

    def test_the_palette_reaches_the_css_and_the_script(self):
        self.assertIn("g.node.c-amber .shape", page.palette_css())
        self.assertEqual(sorted(json.loads(page.palette_js().split("=", 1)[1].rstrip(";"))),
                         sorted(c[0] for c in page.COLOURS))

    def test_text_is_escaped_and_only_web_links_survive(self):
        self.assertNotIn("<script>alert(1)</script>", self.html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", self.html)
        self.assertNotIn('href="javascript:', self.html)
        self.assertIn('<a href="https://docs.python.org/3/library/csv.html">the docs</a>', self.html)
        self.assertIn("<b>CSV</b>", self.html)

    def test_a_label_cannot_close_the_data_script(self):
        item = self.doc["sections"][1]["items"][0]
        item["markdown"] = item["markdown"].replace("Admin([Admin])", "Admin([</script><b>x])")
        out = page.render(self.doc, ":root{}", "route")
        data = re.search(r'class="graph-data">(.*?)</script>', out).group(1)
        self.assertNotIn("<", data)
        self.assertEqual(json.loads(data)["nodes"][0]["label"], "</script><b>x")

    def test_the_theme_supplies_the_fonts_and_the_page_its_own_layout(self):
        self.assertIn('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=X">', self.html)
        self.assertTrue(self.html.startswith("<!doctype html>"))
        bare = page.render(self.doc, ":root{}", "route", fragment=True)
        self.assertTrue(bare.startswith("<title>Brainstorm: csv</title>"))
        self.assertNotIn("<body>", bare)
        self.assertNotIn("<link", bare)
        self.assertNotIn("data-live", bare)

    def test_a_document_of_another_kind_names_itself(self):
        doc = {"schema": "bundle/1", "id": "auth", "kind": "Architecture", "sections": [{"title": "Flow", "markdown": "x"}]}
        out = page.render(doc, ":root{}", "route", fragment=True)
        self.assertTrue(out.startswith("<title>Architecture: auth</title>"))
        self.assertIn("Architecture review &middot; style route", out)
        self.assertIn('<div class="stage">Architecture</div>', out)

    def test_diagrams_are_numbered_in_the_page_order_intro_first(self):
        doc = {"schema": "bundle/1", "id": "x", "intro": "```mermaid\nflowchart LR\n  I --> J\n```",
               "sections": [{"title": "S", "markdown": "```mermaid\nflowchart LR\n  A --> B\n```"}]}
        self.assertEqual([(n, title) for n, _, title in page.diagrams(doc)], [(1, ""), (2, "S")])
        out = page.render(doc, ":root{}", "route")
        self.assertLess(out.index('id="fig-1"'), out.index('id="fig-2"'))
        self.assertLess(out.index("I --&gt; J"), out.index("A --&gt; B"))

    def test_every_theme_is_a_css_file_with_its_fonts(self):
        self.assertEqual(page.themes(), ["blueprint", "bright", "paper", "route", "sketch", "terminal"])
        for name in page.themes():
            css = page.theme_css(name)
            self.assertTrue(page.FONT_LINE.search(css), name)
            self.assertTrue(page.suits(name), name)  # what the agent picks a theme by
            self.assertIn(':root[data-theme="dark"]', css, name)  # the page's light, dark and system switch
            self.assertIn('@media (prefers-color-scheme: dark)', css, name)
        self.assertIsNone(page.theme_css("neon"))
        self.assertEqual(page.suits("neon"), "")

    def test_a_theme_can_shape_the_boxes(self):
        base = page.asset("base.css")
        for token in ("--node-radius", "--node-stroke", "--node-filter", "--node-font", "--edge-width", "--edge-filter"):
            self.assertIn("var(%s" % token, base)
        self.assertIn("url(#fb-rough)", page.theme_css("sketch"))
        self.assertIn('<filter id="fb-rough" ', self.html)  # what the sketch theme points at
        self.assertEqual(self.html.count('id="fb-rough"'), 1)


if __name__ == "__main__":
    unittest.main()
