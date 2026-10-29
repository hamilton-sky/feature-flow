"""Settings: the run settings read once into a frozen dataclass, and MODE_RULES, the one table of which modes
may run together, each row a condition and the STOP text it raises (or none)."""

import dataclasses
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow.conductor.errors import Stop  # the package under test, from this checkout
from feature_flow.conductor.settings import MAX_BATCH, MAX_LANES, MODE_RULES, Settings, mode_ok

TOP = Path("/repo")
GOOD = {"lanes": 1, "relay": False, "cwd": TOP, "top": TOP, "driver": "", "fast": "",
        "size": 3, "fast_mode": True, "gate_on": True}


class ModeRules(unittest.TestCase):
    # (rule, facts that differ from GOOD, the exact STOP text, or None for no STOP, or "" when the rule holds)
    ROWS = (
        ("lanes_range", {"lanes": 1}, ""),
        ("lanes_range", {"lanes": MAX_LANES}, ""),
        ("lanes_range", {"lanes": 9}, "FLOW_LANES must be 1 to 4, not 9"),
        ("lanes_range", {"lanes": 0}, "FLOW_LANES must be 1 to 4, not 0"),
        ("lanes_relay", {"lanes": 2, "relay": True},
         "FLOW_RELAY hands off after every phase, which lanes cannot do. drop one of them"),
        ("lanes_relay", {"lanes": 1, "relay": True}, ""),
        ("lanes_relay", {"lanes": 2}, ""),
        ("lanes_top", {"lanes": 2, "cwd": TOP / "sub"},
         "run the conductor from the top of the repo (%s) to use lanes" % TOP),
        ("lanes_top", {"lanes": 1, "cwd": TOP / "sub"}, ""),
        ("lanes_top", {"lanes": 2}, ""),
        ("driver", {"driver": "robot"}, "FLOW_DRIVER must be person or agent, not robot"),
        ("driver", {"driver": ""}, ""),
        ("driver", {"driver": "person"}, ""),
        ("driver", {"driver": "agent"}, ""),
        ("fast", {"fast": "2"}, "FLOW_FAST must be 1 or 0, not 2"),
        ("fast", {"fast": ""}, ""),
        ("fast", {"fast": "0"}, ""),
        ("fast", {"fast": "1"}, ""),
        ("batch", {}, ""),
        ("batch", {"size": 1}, None),
        ("batch", {"fast_mode": False}, None),
        ("batch", {"gate_on": False}, None),
        ("batch", {"relay": True}, None),
        ("batch", {"lanes": 2}, None),
    )

    def test_the_table_has_the_six_rules(self):
        self.assertEqual([rule.name for rule in MODE_RULES],
                         ["lanes_range", "lanes_relay", "lanes_top", "driver", "fast", "batch"])
        self.assertEqual([rule.stop is None for rule in MODE_RULES], [False] * 5 + [True])

    def test_each_row_gives_its_condition_and_stop_text(self):
        for name, change, want in self.ROWS:
            facts = dict(GOOD, **change)
            with self.subTest(rule=name, facts=change):
                if want == "":
                    self.assertTrue(mode_ok(name, **facts))
                elif want is None:
                    self.assertFalse(mode_ok(name, **facts))
                else:
                    with self.assertRaises(Stop) as caught:
                        mode_ok(name, **facts)
                    self.assertEqual(str(caught.exception), want)

    def test_an_unknown_rule_is_a_programming_error(self):
        with self.assertRaises(KeyError):
            mode_ok("nope", **GOOD)


class SettingsLoad(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(self.dir))

    def load(self, **env):
        env.setdefault("FLOW_DIR", str(self.dir))
        return Settings.load("f", env), env

    def test_settings_are_frozen(self):
        settings, _ = self.load()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            settings.max_retries = 9
        with self.assertRaises(dataclasses.FrozenInstanceError):
            settings.per_session = 0

    def test_the_defaults(self):
        s, _ = self.load()
        self.assertEqual((s.root, s.profile, s.max_retries, s.max_rounds, s.gate_timeout, s.gate_on, s.per_session,
                          s.small_files, s.small_lines, s.batch_size, s.scouts_on, s.relay, s.invoke),
                         (self.dir, "", 2, 3, 30, True, 4, 3, 60, MAX_BATCH, True, False, "/feature-flow"))
        self.assertEqual(Settings.load("f", {}).root, Path("plans"))

    def test_the_values_it_reads(self):
        s, _ = self.load(FLOW_MAX_RETRIES="5", FLOW_MAX_REVIEW_ROUNDS="6", FLOW_GATE_TIMEOUT="7", FLOW_GATE="off",
                         FLOW_TICKETS_PER_SESSION="2", FLOW_SMALL_FILES="1", FLOW_SMALL_LINES="0", FLOW_BATCH="9",
                         FLOW_SCOUTS="off", FLOW_RELAY="1", FLOW_INVOKE="$feature-flow")
        self.assertEqual((s.max_retries, s.max_rounds, s.gate_timeout, s.gate_on, s.per_session, s.small_files,
                          s.small_lines, s.batch_size, s.scouts_on, s.relay, s.invoke),
                         (5, 6, 7, False, 2, 1, 0, MAX_BATCH, False, True, "$feature-flow"))
        self.assertEqual(self.load(FLOW_BATCH="3")[0].batch_size, 3)

    def test_the_profile_comes_from_commands_md_and_fills_the_environment(self):
        (self.dir / "f").mkdir()
        (self.dir / "f" / "commands.md").write_text("Profile: fast\n", encoding="utf-8")
        s, env = self.load()
        self.assertEqual(s.profile, "fast")
        self.assertEqual((s.per_session, s.scouts_on), (6, False))
        self.assertEqual(env["FLOW_FAST"], "1")  # filled for the code that reads it later, as before

    def test_the_agent_driver_has_no_session_limit_unless_it_set_one(self):
        self.assertEqual(self.load()[0].session_limit("person"), 4)
        self.assertEqual(self.load()[0].session_limit("agent"), 0)
        self.assertEqual(self.load(FLOW_PROFILE="fast")[0].session_limit("agent"), 0)  # a profile's 6 does not count
        self.assertEqual(self.load(FLOW_PROFILE="fast")[0].session_limit("person"), 6)
        self.assertEqual(self.load(FLOW_TICKETS_PER_SESSION="2")[0].session_limit("agent"), 2)

    def test_a_bad_whole_number_stops_with_todays_text(self):
        with self.assertRaises(Stop) as caught:
            self.load(FLOW_SMALL_FILES="many")
        self.assertEqual(str(caught.exception), "FLOW_SMALL_FILES must be a whole number, not many")

    def test_settings_does_not_read_flow_lanes(self):
        s, _ = self.load(FLOW_LANES="x", FLOW_DRIVER="robot", FLOW_FAST="2")  # only start checks these
        self.assertEqual(s.max_retries, 2)

    def test_two_bad_values_give_the_first_stop_in_todays_order(self):
        cases = (
            ({"FLOW_PROFILE": "bogus", "FLOW_MAX_RETRIES": "x"}, "the profile must be careful, fast, normal, not bogus"),
            ({"FLOW_SMALL_LINES": "y", "FLOW_MAX_RETRIES": "x"}, "FLOW_MAX_RETRIES must be a whole number, not x"),
            ({"FLOW_SMALL_LINES": "y", "FLOW_GATE_TIMEOUT": "z"}, "FLOW_GATE_TIMEOUT must be a whole number, not z"),
            ({"FLOW_BATCH": "b", "FLOW_TICKETS_PER_SESSION": "t"},
             "FLOW_TICKETS_PER_SESSION must be a whole number, not t"),
        )
        for env, want in cases:
            with self.subTest(env=env):
                with self.assertRaises(Stop) as caught:
                    self.load(**env)
                self.assertEqual(str(caught.exception), want)


if __name__ == "__main__":
    unittest.main()
