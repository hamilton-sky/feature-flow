"""The diagram model: mermaid flowcharts in and out (forkboard/graph.py)."""

import unittest

import helpers  # noqa: F401  (puts this checkout's forkboard first)
from forkboard import graph

DANA = {"dir": "LR", "nodes": [{"id": "Admin", "label": "Admin", "shape": "stadium", "colour": ""},
                               {"id": "Api", "label": "Export \"API\"", "shape": "rect", "colour": "red"},
                               {"id": "N4", "label": "Cache", "shape": "cylinder", "colour": ""}],
        "edges": [{"from": "Admin", "to": "Api", "label": "clicks Export", "style": "arrow"},
                  {"from": "Api", "to": "N4", "label": "", "style": "dotted"}]}


class Parsing(unittest.TestCase):
    def test_a_flowchart_becomes_nodes_and_edges(self):
        g = graph.flowchart("flowchart LR\n  A([Admin]) -->|clicks| B[Api]\n  B --> C[(Db)]\n  B -.-> D{Ok?}\n"
                            "  D == yes ==> E((Done))\n  B -- rows --> A\n  E --- F{{Queue}}\n")
        self.assertEqual(g["dir"], "LR")
        shapes = {n["id"]: (n["label"], n["shape"]) for n in g["nodes"]}
        self.assertEqual(shapes, {"A": ("Admin", "stadium"), "B": ("Api", "rect"), "C": ("Db", "cylinder"),
                                  "D": ("Ok?", "diamond"), "E": ("Done", "circle"), "F": ("Queue", "hexagon")})
        edges = [(e["from"], e["to"], e["label"], e["style"]) for e in g["edges"]]
        self.assertIn(("A", "B", "clicks", "arrow"), edges)
        self.assertIn(("B", "D", "", "dotted"), edges)
        self.assertIn(("B", "A", "rows", "arrow"), edges)
        self.assertIn(("E", "F", "", "open"), edges)

    def test_class_lines_with_a_palette_name_colour_the_boxes(self):
        g = graph.flowchart("flowchart LR\n  A --> B --> C\n  classDef amber fill:#fff\n  class A,B amber\n"
                            "  class C fancy\n  class Z teal\n")
        self.assertEqual({n["id"]: n.get("colour") for n in g["nodes"]}, {"A": "amber", "B": "amber", "C": None})

    def test_a_chain_on_one_line_links_each_pair(self):
        g = graph.flowchart("graph TD\n  A --> B --> C\n")
        self.assertEqual(g["dir"], "TD")
        self.assertEqual([(e["from"], e["to"]) for e in g["edges"]], [("A", "B"), ("B", "C")])

    def test_what_it_cannot_lay_out_is_left_to_mermaid(self):
        self.assertIsNone(graph.flowchart("sequenceDiagram\n  A->>B: hi\n"))
        self.assertIsNone(graph.flowchart("flowchart LR\n  A --> \n"))


class Writing(unittest.TestCase):
    def test_mermaid_round_trips_shapes_labels_styles_and_colours(self):
        text = graph.mermaid(DANA)
        self.assertIn('Api["Export #quot;API#quot;"]', text)
        self.assertIn('N4[("Cache")]', text)
        self.assertIn("Api -.-> N4", text)
        self.assertIn('Admin -->|"clicks Export"| Api', text)
        self.assertIn("class Api red", text)
        back = graph.flowchart(text)
        self.assertEqual([(n["id"], n["shape"], n.get("colour")) for n in back["nodes"]],
                         [("Admin", "stadium", None), ("Api", "rect", "red"), ("N4", "cylinder", None)])

    def test_what_a_rewrite_would_drop_is_named(self):
        self.assertEqual(graph.lost("flowchart LR\n  %% note\n  subgraph S\n  A --> B\n  end\n  style A fill:#fff\n"
                                    "  classDef big font-size:20px\n  classDef red fill:#fff\n"),
                         ["comments", "subgraph", "style", "classDef"])
        self.assertEqual(graph.lost("flowchart LR\n  A --> B\n  classDef red fill:#fff\n  class A red\n"), [])

    def test_a_fingerprint_ignores_the_blank_lines_around_a_diagram(self):
        self.assertEqual(graph.fingerprint("\nflowchart LR\n  A --> B\n"), graph.fingerprint("flowchart LR\n  A --> B"))
        self.assertNotEqual(graph.fingerprint("flowchart LR\n  A --> B"), graph.fingerprint("flowchart LR\n  A --> C"))


if __name__ == "__main__":
    unittest.main()
