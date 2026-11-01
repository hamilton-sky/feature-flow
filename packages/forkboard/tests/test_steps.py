"""Steps and choices (forkboard/doc.py, page.py, live.py): a page that grows through steps, a done step folded into
its summary with a Change button, and choices whose picks land in the page's state for the tool."""

import json
import unittest

import helpers
from forkboard import doc as docs, live, page

CSS = ":root{}"


class Document(unittest.TestCase):
    def test_steps_and_choices_are_optional_and_checked(self):
        docs.check(helpers.fixture("csv"))  # no steps, no choices: as before
        docs.check(helpers.fixture("steps"))
        for change, says in (
                (lambda d: d["steps"].append({"name": "Setup"}), "two steps share a name"),
                (lambda d: d["steps"][0].update(state="soon"), "a state of done, current, later"),
                (lambda d: d["sections"][1].update(step="Build"), "names the step Build"),
                (lambda d: d["sections"][0]["choices"][0].update(value="huge"), "not one of its options"),
                (lambda d: d["sections"][0]["choices"][1].update(value=["ux", "security", "artistic"]), "more than its max"),
                (lambda d: d["sections"][0]["choices"][1].update(kind="many"), "a kind of one, some"),
                (lambda d: d["sections"][0]["choices"][0].update(options=[]), "needs options")):
            d = helpers.fixture("steps")
            change(d)
            with self.assertRaises(ValueError, msg=says) as caught:
                docs.check(d)
            self.assertIn(says, str(caught.exception))


class Page(unittest.TestCase):
    def setUp(self):
        self.html = page.render(helpers.fixture("steps"), CSS, "route")

    def test_a_done_step_folds_into_its_summary_with_a_change_button(self):
        self.assertIn('<ol class="steps" aria-label="Steps">', self.html)
        setup = self.html[self.html.index('<div class="step done" data-step="Setup">'):self.html.index('<div class="step current"')]
        self.assertIn('<span class="sum">type learn, scouts web=deep</span>', setup)
        self.assertIn('<button type="button" class="change" data-change="Setup" hidden>Change</button>', setup)
        self.assertIn('<details class="step-body"><summary>Show Setup</summary>', setup)
        self.assertIn('<div class="step later" data-step="Plan">', self.html)
        self.assertNotIn('<details class="step-body"><summary>Show Options', self.html)  # the current step is open

    def test_choices_show_the_tools_value_and_wait_for_the_live_layer(self):
        self.assertIn('<fieldset class="choice" data-key="web" data-kind="one">', self.html)
        self.assertIn('<button type="button" data-value="deep" aria-pressed="true" disabled>Deep</button>', self.html)
        self.assertIn('<button type="button" data-value="off" aria-pressed="false" disabled>Off</button>', self.html)
        self.assertIn('data-key="lens" data-kind="some" data-max="2"', self.html)
        self.assertIn('<input type="checkbox" value="ux" checked disabled> UX', self.html)
        self.assertIn('<span class="most">up to 2</span>', self.html)
        self.assertIn("Reply ok in the chat", self.html)

    def test_a_page_without_steps_has_none_of_it(self):
        plain = page.render(helpers.fixture("csv"), CSS, "route")
        for part in ('class="steps"', "fieldset", "step-body", ".choice{"):
            self.assertNotIn(part, plain)


class State(unittest.TestCase):
    def test_picks_are_kept_across_rounds_and_read_back(self):
        st = live.state(helpers.fixture("steps"))
        self.assertEqual(st["picks"], {})
        st["picks"] = {"web": {"by": "u_me", "at": "2026-11-01T10:00:00Z", "value": "light"},
                       "lens": {"by": "u_dana", "at": "2026-11-01T10:01:00Z", "value": ["ux", "security"]},
                       "bad": "not a pick"}
        again = live.state(helpers.fixture("steps"), json.loads(live.dump(st)))
        self.assertEqual(live.picks(again), {"web": "light", "lens": ["ux", "security"]})

    def test_a_change_button_is_an_ask_about_its_step(self):
        st = live.state(helpers.fixture("steps"))
        st["asks"] = [{"by": "u_me", "at": "t", "figure": None, "step": "Setup", "text": "Change the step Setup"}]
        self.assertIn("ask 1 from u_me at t to change the step Setup:", live.asks(st))


if __name__ == "__main__":
    unittest.main()
