"""Steps and choices (forkboard/doc.py, page.py, live.py): a page that grows through steps shown as tabs, a done step
with its summary and a Change button, the current step with an Approve button, and choices whose picks land in the
page's state for the tool when their step is approved."""

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
                (lambda d: d["steps"].append({"name": "Style"}), "two steps share a name"),
                (lambda d: d["steps"][0].update(state="soon"), "a state of done, current, later"),
                (lambda d: d["sections"][2].update(step="Build"), "names the step Build"),
                (lambda d: d["sections"][0]["choices"][0].update(value="huge"), "not one of its options"),
                (lambda d: d["sections"][1]["choices"][0].update(value=["ux", "security", "artistic"]), "more than its max"),
                (lambda d: d["sections"][1]["choices"][0].update(kind="many"), "a kind of one, some"),
                (lambda d: d["sections"][0]["choices"][0].update(options=[]), "needs options"),
                (lambda d: d["sections"][2].update(ask_about="01"), "ask_about must be a list")):
            d = helpers.fixture("steps")
            change(d)
            with self.assertRaises(ValueError, msg=says) as caught:
                docs.check(d)
            self.assertIn(says, str(caught.exception))


class Page(unittest.TestCase):
    def setUp(self):
        self.html = page.render(helpers.fixture("steps"), CSS, "route")

    def test_the_steps_are_tabs_opened_on_the_current_one(self):
        self.assertIn('<div class="tabs" role="tablist" aria-label="Steps">', self.html)
        self.assertIn('<button type="button" role="tab" class="tab current" id="tab-2" aria-controls="step-2" '
                      'aria-selected="true">', self.html)
        self.assertIn('<button type="button" role="tab" class="tab done" id="tab-1" aria-controls="step-1" '
                      'aria-selected="false" tabindex="-1">', self.html)
        style = self.html[self.html.index('<section class="step done"'):self.html.index('<section class="step current"')]
        self.assertIn('role="tabpanel" id="step-1" aria-labelledby="tab-1" data-step="Style" hidden>', style)
        self.assertIn('<span class="sum">type learn, scouts web=deep</span>', style)
        self.assertIn('<button type="button" class="change" data-change="Style" hidden>Change</button>', style)
        self.assertNotIn("approve", style)  # a done step is changed with Change, not approved again
        self.assertIn('id="step-2" aria-labelledby="tab-2" data-step="Team">', self.html)  # open
        self.assertIn('<section class="step later" role="tabpanel" id="step-3" aria-labelledby="tab-3" data-step="Options" hidden>',
                      self.html)
        self.assertNotIn("details", self.html.split('role="tablist"')[1].split("<script")[0])

    def test_the_current_step_with_choices_has_an_approve_button(self):
        team = self.html[self.html.index('<section class="step current"'):self.html.index('<section class="step later"')]
        self.assertIn('<button type="button" class="approve" data-approve="Team" disabled>Approve Team</button>', team)
        self.assertEqual(self.html.count('class="approve"'), 1)
        self.assertNotIn('class="choice-hint"', self.html)  # the Approve row says it once

    def test_options_and_a_sections_subjects_can_be_asked_about(self):
        self.assertIn('<article class="opt" id="a-stream-it" data-about="A. Stream it">', self.html)
        self.assertIn('<div class="ask-about" hidden><script type="application/json">["01 Export button", "02 CSV writer"]'
                      '</script></div>', self.html)
        self.assertNotIn("ask-about", page.render(helpers.fixture("csv"), CSS, "route"))

    def test_choices_show_the_tools_value_and_wait_for_the_live_layer(self):
        self.assertIn('<fieldset class="choice" data-key="web" data-kind="one">', self.html)
        self.assertIn('<button type="button" data-value="deep" aria-pressed="true" disabled>Deep</button>', self.html)
        self.assertIn('<button type="button" data-value="off" aria-pressed="false" disabled>Off</button>', self.html)
        self.assertIn('data-key="lens" data-kind="some" data-max="2"', self.html)
        self.assertIn('<input type="checkbox" value="ux" checked disabled> UX', self.html)
        self.assertIn('<span class="most">up to 2</span>', self.html)
        self.assertIn("Reply ok in the chat", self.html)
        self.assertIn('class="choice-hint"', page.render(dict(helpers.fixture("steps"), steps=[], sections=[
            dict(s, step=None) for s in helpers.fixture("steps")["sections"]]), CSS, "route"))  # no steps: no Approve

    def test_a_page_without_steps_has_none_of_it(self):
        plain = page.render(helpers.fixture("csv"), CSS, "route")
        for part in ('class="tabs"', "fieldset", "tabpanel", ".choice{", "approve"):
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
        st["asks"] = [{"by": "u_me", "at": "t", "figure": None, "step": "Style", "text": "Change the step Style"}]
        self.assertIn("ask 1 from u_me at t to change the step Style:", live.asks(st))
        st["asks"] = [{"by": "u_me", "at": "t", "figure": None, "about": "02 CSV writer", "text": "Why after 01?"}]
        self.assertIn('ask 1 from u_me at t about "02 CSV writer":\n  Why after 01?', live.asks(st))

    def test_approvals_are_kept_across_rounds_and_an_approve_is_an_ask(self):
        st = live.state(helpers.fixture("steps"))
        self.assertEqual(st["approved"], {})
        st["approved"] = {"Style": {"by": "u_me", "at": "t"}, "Team": "not an approval"}
        st["asks"] = [{"by": "u_me", "at": "t", "figure": None, "step": "Style", "approve": True,
                       "text": "Approved Style: Web scouts: light"}]
        again = live.state(helpers.fixture("steps"), json.loads(live.dump(st)))
        self.assertEqual(live.approved(again), {"Style": {"by": "u_me", "at": "t"}})
        self.assertIn("ask 1 from u_me at t to approve the step Style:\n  Approved Style: Web scouts: light", live.asks(again))


if __name__ == "__main__":
    unittest.main()
