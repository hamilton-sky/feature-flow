"""Brainstorm types and scout levels: a brainstorm's `Type:` and `Scouts:` header lines set how far the code and
web scouts look and how many helpers it may use, and the plan's and the build's scouts follow the same levels.
FLOW_SCOUTS=off still turns every scout off."""

import os
import shutil
import subprocess
import sys
import unittest

import helpers
from helpers import ROOT, Repo

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import brainstorm_mode, scouts  # the package under test, from this checkout
from feature_flow.brainstorm_mode import BadMode
from test_scouts_drive import SCOUT


class Header(unittest.TestCase):
    def test_it_reads_the_type_and_the_scout_levels_from_the_header_only(self):
        text = ("# Brainstorm: g\n\nPicked by: person\nStyle: route\nType: Learn\nScouts: web=off code=deep\n\n"
                "## Idea\n\nType: map\n")
        self.assertEqual(brainstorm_mode.parse(text), {"type": "learn", "code": "deep", "web": "off"})
        self.assertEqual(brainstorm_mode.parse("# B\n\nType: <standard|learn|map|quick|explore>\n"
                                               "Scouts: <code=... web=...>\n"), {})  # the template's placeholders
        self.assertEqual(brainstorm_mode.parse(""), {})

    def test_it_refuses_a_value_it_does_not_know(self):
        for text in ("Type: fast\n", "Scouts: code=huge\n", "Scouts: tests=deep\n", "Scouts: deep\n"):
            with self.assertRaises(BadMode, msg=text):
                brainstorm_mode.parse(text)

    def test_the_helpers_line_reads_names_and_lenses_and_writes_back(self):
        self.assertEqual(brainstorm_mode.parse("Helpers: architect PO skeptic lens=ux,security\n")["helpers"],
                         ("architect", "po", "skeptic", "ux", "security"))
        self.assertEqual(brainstorm_mode.parse("Helpers: none\n")["helpers"], ())
        self.assertNotIn("helpers", brainstorm_mode.parse("Helpers: <the helpers you will ask>\n"))
        for bad in ("Helpers: scout\n", "Helpers: lens=pretty\n", "Helpers: wizard\n"):
            with self.assertRaises(BadMode, msg=bad):
                brainstorm_mode.parse(bad)
        self.assertEqual(brainstorm_mode.helpers_text(("ux", "po", "architect")), "architect po lens=ux")
        self.assertEqual(brainstorm_mode.helpers_text(()), "none")
        caps = brainstorm_mode.limits("", {"code": "normal", "web": "normal"}, "standard")
        self.assertIsNone(brainstorm_mode.over(("architect", "po", "skeptic", "ux", "security"), caps))
        self.assertEqual(brainstorm_mode.over(("architect", "po", "designer"), caps), ("consult", 3, 2))

    def test_no_type_is_named_fast(self):
        self.assertNotIn("fast", brainstorm_mode.TYPES)  # fast already means no brainstorm at all


class Credit(unittest.TestCase):
    def test_tags_count_per_helper_and_a_link_is_not_a_tag(self):
        text = ("# B\n\n## Options\n\n### A. One\n\n- idea [ux]\n- [security](https://x) is a link\n\n"
                "### B. Two\n\n- idea [web] [ux]\n\n## Chosen\n\nB, because of [po]\n")
        self.assertEqual(brainstorm_mode.credit(text), {"ideas": {"ux": 2, "web": 1}, "chosen": {"web": 1, "ux": 1, "po": 1}})
        self.assertEqual(brainstorm_mode.credit(""), {"ideas": {}, "chosen": {}})


class Levels(unittest.TestCase):
    def level(self, kind, mode, filled=(), **env):
        return brainstorm_mode.level(kind, env, filled, mode)

    def test_the_type_sets_the_levels_and_the_header_wins_over_it(self):
        self.assertEqual((self.level("code", {}), self.level("web", {})), ("normal", "normal"))
        for kind, code, web in (("learn", "light", "deep"), ("map", "deep", "light"), ("quick", "light", "light"),
                                ("explore", "light", "normal"), ("standard", "normal", "normal")):
            mode = {"type": kind}
            self.assertEqual((self.level("code", mode), self.level("web", mode)), (code, web), kind)
        self.assertEqual(self.level("web", {"type": "learn", "web": "off"}), "off")

    def test_flow_scouts_off_set_by_you_wins_and_a_profiles_off_does_not(self):
        mode = {"type": "map", "web": "deep"}
        self.assertEqual(self.level("code", mode, FLOW_SCOUTS="off"), "off")
        self.assertEqual(self.level("web", mode, FLOW_SCOUTS="off"), "off")
        self.assertEqual(self.level("code", mode, ["FLOW_SCOUTS"], FLOW_SCOUTS="off"), "deep")  # fast filled it
        self.assertEqual(self.level("code", {}, ["FLOW_SCOUTS"], FLOW_SCOUTS="off"), "off")  # and nothing chose
        self.assertEqual(self.level("code", mode, FLOW_SCOUTS="on"), "deep")

    def test_the_limits_follow_the_profile_the_levels_and_the_type(self):
        normal = {"code": "normal", "web": "normal"}
        self.assertEqual(brainstorm_mode.limits("", normal, "standard"),
                         {"scout": 2, "web": 1, "consult": 2, "skeptic": 1, "lens": 2})
        self.assertEqual(brainstorm_mode.limits("careful", normal, ""),
                         {"scout": 3, "web": 2, "consult": 3, "skeptic": 1, "lens": 3})
        deep = brainstorm_mode.limits("", {"code": "deep", "web": "light"}, "map")
        self.assertEqual((deep["scout"], deep["web"]), (3, 1))
        quick = brainstorm_mode.limits("", {"code": "off", "web": "light"}, "quick")
        self.assertEqual(quick, {"scout": 0, "web": 1, "consult": 1, "skeptic": 0, "lens": 0})


class ByLevel(unittest.TestCase):
    FOUND = [("flow-scout", "builder", "a"), ("flow-scout", "builder", "b"), ("flow-web", "planner", "c")]

    def test_off_asks_nothing_and_light_only_the_first(self):
        self.assertEqual(scouts.by_level(self.FOUND, "normal", "normal"), self.FOUND)
        self.assertEqual(scouts.by_level(self.FOUND, "deep", "deep"), self.FOUND)
        self.assertEqual(scouts.by_level(self.FOUND, "light", "off"), self.FOUND[:1])
        self.assertEqual(scouts.by_level(self.FOUND, "off", "light"), self.FOUND[2:])


class Brainstorm(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.addCleanup(self.repo.close)
        for folder in ("guides", "agents"):
            shutil.copytree(str(ROOT / folder), str(self.repo.path(".feature-flow/" + folder)))
        self.repo.commit("guides")
        self.repo.path("q.md").write_text("How does the code export rows today?\n", encoding="utf-8")

    def header(self, lines):
        path = self.repo.path(".feature-flow/state/brainstorm-g.md")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Brainstorm: g\n\nPicked by: person\n%s\n## Idea\n\nExport rows.\n" % lines,
                        encoding="utf-8")

    def flow(self, *args, **env):
        full = {k: v for k, v in os.environ.items() if not k.startswith("FLOW_")}
        full.update(env)
        done = subprocess.run([sys.executable, "scripts/flow.py", "g"] + list(args), cwd=str(self.repo.dir),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, env=full,
                              encoding="utf-8")
        return done.returncode, done.stdout.strip()

    def used(self, helper, **env):
        """How many of helper the brainstorm allows, asking until the script refuses."""
        for n in range(6):
            rc, out = self.flow("brainstorm-prompt", helper, "q.md", **env)
            if rc:
                self.assertIn("has used its %d" % n, out)
                return n
        self.fail("no limit for %s" % helper)

    def test_map_allows_three_scouts_and_one_web(self):
        self.header("Type: map\n")
        self.assertEqual((self.used("scout"), self.used("web")), (3, 1))

    def test_quick_allows_one_consultant_and_no_skeptic_or_lens(self):
        self.header("Type: quick\n")
        self.assertEqual((self.used("architect"), self.used("skeptic"), self.used("ux")), (1, 0, 0))
        rc, out = self.flow("brainstorm-prompt", "skeptic", "q.md")
        self.assertIn("(normal; type quick, scouts code=light web=light)", out)

    def test_learn_allows_two_web_and_the_scouts_line_wins(self):
        self.header("Type: learn\nScouts: code=off\n")
        self.assertEqual((self.used("web"), self.used("scout")), (2, 0))

    def test_flow_scouts_off_still_turns_them_off(self):
        self.header("Type: map\n")
        self.assertEqual(self.used("scout", FLOW_SCOUTS="off"), 0)

    def test_a_light_scout_gets_no_codeintel_note(self):
        self.header("Type: quick\n")
        rc, out = self.flow("brainstorm-prompt", "scout", "q.md")
        self.assertEqual(rc, 0, out)
        self.assertNotIn("codeintel", out)

    def test_a_bad_header_stops_with_what_to_fix(self):
        self.header("Type: fast\n")
        rc, out = self.flow("brainstorm-prompt", "scout", "q.md")
        self.assertEqual(rc, 1)
        self.assertTrue(out.startswith("STOP Type: must be standard, learn, map, quick, explore, not fast. fix the "
                                       "header of the brainstorm of g"), out)

    def test_a_helpers_line_allows_only_the_helpers_it_picks(self):
        self.header("Helpers: architect lens=ux\n")
        rc, out = self.flow("brainstorm-prompt", "architect", "q.md")
        self.assertEqual(rc, 0, out)
        rc, out = self.flow("brainstorm-prompt", "po", "q.md")
        self.assertEqual(rc, 1)
        self.assertIn("STOP the brainstorm's Helpers: line (architect lens=ux) does not pick po", out)
        self.assertEqual(self.flow("brainstorm-prompt", "ux", "q.md")[0], 0)
        self.assertEqual(self.flow("brainstorm-prompt", "scout", "q.md")[0], 0)  # the scouts follow Scouts:

    def test_a_helpers_line_over_the_limits_stops(self):
        self.header("Type: quick\nHelpers: architect po\n")
        rc, out = self.flow("brainstorm-prompt", "architect", "q.md")
        self.assertEqual(rc, 1)
        self.assertIn("picks 2 consult helper(s), and normal with type quick allows 1", out)

    def test_asked_logs_a_guided_stop_and_refuses_another_word(self):
        rc, out = self.flow("asked", "setup")
        self.assertEqual((rc, out), (0, "OK asked setup"))
        log = self.repo.path(".feature-flow/state/flow-g.log").read_text(encoding="utf-8")
        self.assertIn(",GUIDED-SETUP", log)
        rc, out = self.flow("asked", "build")
        self.assertEqual(rc, 1)
        self.assertIn("STOP asked takes setup, options, plan, not build", out)

    def test_without_a_type_the_brainstorm_is_as_before(self):
        self.assertEqual((self.used("scout"), self.used("web"), self.used("ux")), (2, 1, 2))


class PlanScoutLevels(unittest.TestCase):
    def test_the_plan_scouts_follow_the_brainstorms_levels(self):
        repo = Repo(tickets=())
        self.addCleanup(repo.close)
        for folder in ("agents", "guides"):
            shutil.copytree(str(ROOT / folder), str(repo.path(folder)))
        repo.commit("guides")
        brief = repo.dir.parent / (repo.dir.name + "-brief.md")
        self.addCleanup(brief.unlink, missing_ok=True)
        brief.write_text("What: export CSV\nThe bar: `make test` passes\n", encoding="utf-8")
        state = repo.path(".feature-flow/state/brainstorm-x.md")
        state.parent.mkdir(parents=True, exist_ok=True)
        full = {k: v for k, v in os.environ.items() if not k.startswith("FLOW_")}

        def agents(header):
            state.write_text("# Brainstorm: x\n\n%s\n## Idea\n" % header, encoding="utf-8")
            done = subprocess.run([sys.executable, repo.script, "x", "plan-scouts", str(brief)], cwd=str(repo.dir),
                                  env=full, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            out = done.stdout.strip()
            return [] if out == "NONE" else [SCOUT.match(l).group(2) for l in out.splitlines()]

        self.assertEqual(agents("Type: standard\n"), ["flow-scout", "flow-web"])
        self.assertEqual(agents("Type: learn\nScouts: code=off\n"), ["flow-web"])
        self.assertEqual(agents("Scouts: code=off web=off\n"), [])


if __name__ == "__main__":
    unittest.main()
