"""The live page's state (forkboard/live.py): figures, people's versions, and asks for the session."""

import unittest

import helpers
from forkboard import live

DANA = {"dir": "LR", "nodes": [{"id": "Admin", "label": "Admin", "shape": "stadium", "colour": ""},
                               {"id": "Api", "label": "Export", "shape": "rect", "colour": "red"},
                               {"id": "N4", "label": "Cache", "shape": "cylinder", "colour": ""}],
        "edges": [{"from": "Admin", "to": "Api", "label": "clicks Export", "style": "arrow"},
                  {"from": "Api", "to": "N4", "label": "", "style": "dotted"}]}


def saved():
    """A state as the page saves it: Dana's version of the sketch and two asks, one answered."""
    st = live.state(helpers.fixture("sketch"))
    st["figures"]["1"]["versions"]["u_dana"] = {"graph": DANA, "pos": {}, "at": "2026-10-26T22:00:00Z", "via": ["hand", "claude"]}
    st["asks"] = [{"by": "u_dana", "at": "2026-10-26T22:01:00Z", "figure": "1", "version": "u_dana", "text": "Is a cache worth it?"},
                  {"by": "u_me", "at": "2026-10-26T22:02:00Z", "figure": None, "version": None, "text": "Old one", "answer": "Done."}]
    return st


class State(unittest.TestCase):
    def test_flowcharts_become_figures_numbered_like_the_page(self):
        st = live.state(helpers.fixture("sketch"))
        self.assertEqual(sorted(st["figures"]), ["1", "3"])  # figure 2 is a sequence diagram: mermaid draws it, nobody edits it
        self.assertEqual(st["figures"]["1"]["title"], "Sketch")
        self.assertEqual(st["figures"]["3"]["title"], "B. In the background")
        self.assertEqual(st["figures"]["3"]["original"]["nodes"][1]["colour"], "amber")
        self.assertEqual((st["feature"], st["round"], st["asks"]), ("csv", 1, []))

    def test_a_new_round_keeps_what_people_saved(self):
        doc = helpers.fixture("sketch")
        doc["sections"][0]["markdown"] = doc["sections"][0]["markdown"].replace("Tasks table", "Tasks")
        again = live.state(doc, saved())
        self.assertEqual(again["round"], 2)
        self.assertIn("u_dana", again["figures"]["1"]["versions"])
        self.assertEqual(again["figures"]["1"]["original"]["nodes"][2]["label"], "Tasks")
        self.assertNotEqual(again["figures"]["1"]["source"], saved()["figures"]["1"]["source"])
        self.assertEqual(len(again["asks"]), 2)
        self.assertEqual(live.state(doc, "junk")["round"], 1)

    def test_other_code_blocks_do_not_count_as_figures(self):
        doc = {"schema": "bundle/1", "id": "f", "sections": [
            {"title": "Code", "markdown": "```python\nx = 1\n```"},
            {"title": "Flow", "markdown": "```mermaid\nflowchart LR\n  A --> B\n```"}]}
        self.assertEqual({n: f["title"] for n, f in live.state(doc)["figures"].items()}, {"1": "Flow"})


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

    def test_a_version_comes_back_with_the_source_it_was_drawn_on(self):
        st = saved()
        graph, source = live.version(st, "1", "u_dana")
        self.assertEqual(graph, DANA)
        self.assertEqual(source, st["figures"]["1"]["source"])
        self.assertEqual(live.version(st, "1", "original")[0]["nodes"][2]["label"], "Tasks table")
        for figure, name in (("1", "u_nobody"), ("2", "original"), ("9", "original")):
            with self.assertRaises(ValueError):
                live.version(st, figure, name)


if __name__ == "__main__":
    unittest.main()
