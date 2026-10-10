"""Ticket 08 of trusted-checks (the acceptance bar): drive a two-ticket plan only through the loader
line pinned in skills/feature-flow/SKILL.md, the way the skill says (TRUST digest passed on to the
next call, `--after-build <ticket> <sha>` on the `next` after each BUILD), and show that an
untampered drive reaches DONE while every tamper ends in a STOP naming what changed."""

import importlib.util
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import helpers
from helpers import Repo
from test_skill_trust import SKILLS, loader_line

T1 = "plans/f/tasks/01-a.md"
T2 = "plans/f/tasks/02-b.md"
STATE = ".feature-flow/state/flow-f.state"
REPLY = ".feature-flow/state/flow-review-f.txt"
SKILL = ".claude/skills/feature-flow/SKILL.md"
ROLE = ".claude/agents/ticket-builder.md"
GUIDE = ".feature-flow/guides/build.md"
TRUST = re.compile(r"^TRUST ([0-9a-f]{16}\.[0-9a-f]{16})$")
CHANGED = "STOP flow files changed since the last step: "
DURING = "STOP flow code changed during next: "

# Double quotes, which both bash -c and cmd.exe read (as in test_fixture_drive.py).
PYTHON = '"%s"' % sys.executable
COMMANDS = ("# Commands: f\n\n"
            "Build: `%s -c \"pass\"`\n"
            "Smoke: `%s -c \"pass\"`\n"
            "Test: `%s t.py`\n") % ((PYTHON,) * 3)
# Hole (c): the builder's committed test script edits the conductor when the gate runs it.
EVIL_TEST = ("with open('feature_flow/conductor.py', 'ab') as handle:\n"
             "    handle.write(b'\\n# edited by t.py\\n')\n")


class Drive(unittest.TestCase):
    """A fresh fixture repo per test, driven only through the skill's loader line."""

    def setUp(self):
        self.repo = Repo()
        self.addCleanup(self.repo.close)
        self.runner = self.repo.path("scripts/flow-trust.py")
        shutil.copy(str(helpers.ROOT / "scripts" / "flow-trust.py"), str(self.runner))
        # the installed guides, roles and skill a session runs from, as install.py lays them out
        for folder in ("guides", "agents"):
            shutil.copytree(str(helpers.ROOT / folder), str(self.repo.path(".feature-flow/" + folder)))
        self.repo.path(".claude/agents").mkdir(parents=True)
        shutil.copy(str(helpers.ROOT / "agents" / "ticket-builder.md"), str(self.repo.path(ROLE)))
        shutil.copytree(str(helpers.ROOT / "skills" / "feature-flow"), str(self.repo.path(".claude/skills/feature-flow")))
        self.repo.path("plans/f/commands.md").write_text(COMMANDS, encoding="utf-8")
        self.repo.path("t.py").write_text("print('fine')\n", encoding="utf-8")
        self.homes = {}
        for name in ("CLAUDE_HOME", "AGENTS_HOME", "FEATURE_FLOW_HOME"):
            folder = tempfile.TemporaryDirectory()
            self.addCleanup(folder.cleanup)
            self.homes[name] = folder.name
        self.repo.commit("layout")
        self.loader = loader_line(SKILLS[0])[0]
        self.digest = "new"
        self.token = None
        self.build = None  # (ticket, sha) of the last BUILD, for --after-build

    # -- calling the conductor the way the skill does

    def run_loader(self, *args):
        """The extracted loader line (python3 as the running interpreter, <S> as the fixture's
        scripts folder) through the platform shell; returns (exit code, stdout lines, stderr)."""
        env = {k: v for k, v in os.environ.items() if not k.startswith("FLOW_")}
        env.update(self.homes)
        env["FLOW_TRUST"] = self.digest
        env["FLOW_INVOKE"] = "/feature-flow"
        if self.token:
            env["FLOW_SESSION"] = self.token
        done = helpers.run_loader(self.loader, self.runner, args, self.repo.dir, env)
        return done.returncode, done.stdout.splitlines(), done.stderr

    def call(self, command, *args):
        """One conductor command; `next` right after a BUILD carries --after-build."""
        before = []
        if command == "next" and self.build:
            before = ["--after-build", self.build[0], self.build[1]]
            self.build = None
        return self.run_loader(*(before + ["f", command] + list(args)))

    def passed(self, command, *args):
        """A call the runner trusts: keep its digest, return the conductor's lines after TRUST."""
        rc, lines, err = self.call(command, *args)
        self.assertTrue(lines, "no output; stderr: %s" % err)
        match = TRUST.match(lines[0])
        self.assertIsNotNone(match, "first line is not TRUST: %r (stderr %r)" % (lines, err))
        self.digest = match.group(1)
        self.assertEqual(rc, 0, (lines, err))
        lines = lines[1:]
        self.assertTrue(lines, err)
        if lines[0].startswith("BUILD "):
            words = lines[0].split()
            self.build = (words[1], words[3])
        return lines

    def stopped(self, command="next"):
        """A call that ends in the runner's STOP: exit 1, STOP first, no TRUST anywhere."""
        rc, lines, err = self.call(command)
        self.assertEqual(rc, 1, (lines, err))
        self.assertTrue(lines and lines[0].startswith("STOP "), (lines, err))
        self.assertFalse(any(TRUST.match(line) for line in lines), lines)
        return lines

    def begin(self):
        """start, then the first next: BUILD of ticket 01."""
        lines = self.passed("start")
        self.assertTrue(lines[0].startswith("OK "), lines)
        self.token = lines[0].split()[1]
        lines = self.passed("next")
        self.assertEqual(lines, ["BUILD %s 01 %s" % (T1, self.repo.head())])

    def review(self, ticket):
        """Both review passes of one ticket, each as REVIEW -> prompt -> reply saved -> verdict."""
        for name in ("spec", "quality"):
            lines = self.passed("next")
            self.assertTrue(lines[0].startswith("REVIEW %s " % ticket), (name, lines))
            prompt = self.passed("prompt")
            self.assertIn("(%s pass)" % name, "\n".join(prompt))
            self.repo.path(REPLY).write_text("fine\nREVIEW: PASS\n", encoding="utf-8")
            self.assertEqual(self.passed("verdict", REPLY), ["OK"])

    # -- tampering

    def append(self, rel, data=b"\n# edited\n"):
        with open(str(self.repo.path(rel)), "ab") as handle:
            handle.write(data)

    def named(self, line):
        """The paths a `STOP flow files changed since the last step: a, b` line names."""
        self.assertTrue(line.startswith(CHANGED), line)
        return line[len(CHANGED):].split(", ")

    def assert_stops_naming(self, rel):
        lines = self.stopped()
        self.assertIn(rel, self.named(lines[0]))
        self.assertFalse(any(line.startswith(("BUILD", "REVIEW", "DONE")) for line in lines), lines)


class Untampered(Drive):
    def test_both_tickets_built_reviewed_and_done(self):
        self.begin()
        self.repo.resolve(T1)
        self.review(T1)
        lines = self.passed("next")
        self.assertTrue(lines[0].startswith("BUILD %s 02 " % T2), lines)
        self.repo.resolve(T2)
        self.review(T2)
        lines = self.passed("next")
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("DONE f is complete"), lines)

    def test_a_new_pycache_file_and_the_review_reply_do_not_stop(self):
        self.begin()
        self.repo.path("feature_flow/__pycache__").mkdir(exist_ok=True)
        self.repo.path("feature_flow/__pycache__/junk.cpython-99.pyc").write_bytes(b"junk")
        self.repo.path(REPLY).write_text("anything\nREVIEW: PASS\n", encoding="utf-8")
        self.repo.resolve(T1)
        lines = self.passed("next")
        self.assertTrue(lines[0].startswith("REVIEW %s 01 " % T1), lines)


class Holes(Drive):
    def test_a_builder_commit_that_makes_check_code_return_early(self):
        self.begin()
        path = self.repo.path("feature_flow/conductor.py")
        marker = b'"""Stop when the files the conductor runs from changed since the ticket was picked."""'
        path.write_bytes(helpers.insert_after_line(path.read_bytes(), marker, b"        return"))
        self.repo.resolve(T1)
        self.assertEqual(self.repo.porcelain(), "")
        self.assert_stops_naming("feature_flow/conductor.py")

    def test_phase_written_into_the_state_after_resolving_01(self):
        self.begin()
        self.repo.resolve(T1)
        self.append(STATE, b"phase=\n")
        build = self.build
        self.assert_stops_naming(STATE)
        # the session stops; a retry with the same digest still never hands out ticket 02
        self.build = build
        lines = self.stopped()
        self.assertIn(STATE, self.named(lines[0]))
        for line in lines:
            self.assertFalse(line.startswith("BUILD"), lines)
            self.assertNotIn("02-b.md", line)

    def test_the_builders_test_script_edits_the_conductor_during_next(self):
        self.begin()
        self.repo.path("t.py").write_text(EVIL_TEST, encoding="utf-8")
        self.repo.resolve(T1)
        before = self.repo.path("feature_flow/conductor.py").read_bytes()
        lines = self.stopped()
        self.assertNotEqual(self.repo.path("feature_flow/conductor.py").read_bytes(), before, "t.py did not run")
        self.assertEqual(lines[0], DURING + "feature_flow/conductor.py")


class Edits(Drive):
    """Each edit a builder makes to the flow's own files during a build stops the next call."""

    def test_a_new_py_file_in_the_package(self):
        self.begin()
        self.repo.path("feature_flow/extra.py").write_bytes(b"x = 1\n")
        self.repo.resolve(T1)
        self.assert_stops_naming("feature_flow/extra.py")

    def test_an_edited_guide(self):
        self.begin()
        self.append(GUIDE)
        self.repo.resolve(T1)
        self.assert_stops_naming(GUIDE)

    def test_an_edited_role(self):
        self.begin()
        self.append(ROLE)
        self.repo.resolve(T1)
        self.assert_stops_naming(ROLE)

    def test_an_edited_skill(self):
        self.begin()
        self.append(SKILL)
        self.repo.resolve(T1)
        self.assert_stops_naming(SKILL)

    def test_an_edited_state_file(self):
        self.begin()
        self.repo.resolve(T1)
        self.append(STATE, b"extra=1\n")
        self.assert_stops_naming(STATE)


class PlantedBytecode(Drive):
    """A .pyc compiled from an edited conductor.py, with the source's mtime and size and the source
    put back, is never run by the drive."""

    HONEST, FORGED = b'"BUILD %s %s %s"', b'"BXILD %s %s %s"'

    def plant(self):
        source = self.repo.path("feature_flow/conductor.py")
        original = source.read_bytes()
        stat = source.stat()
        self.assertIn(self.HONEST, original)
        source.write_bytes(original.replace(self.HONEST, self.FORGED, 1))
        os.utime(str(source), ns=(stat.st_atime_ns, stat.st_mtime_ns))
        py_compile.compile(str(source), cfile=importlib.util.cache_from_source(str(source)), doraise=True,
                           invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)
        source.write_bytes(original)
        os.utime(str(source), ns=(stat.st_atime_ns, stat.st_mtime_ns))
        self.assertEqual(source.read_bytes(), original)

    def test_the_planted_pyc_is_not_run(self):
        lines = self.passed("start")
        self.token = lines[0].split()[1]
        self.plant()
        lines = self.passed("next")
        self.assertEqual(lines, ["BUILD %s 01 %s" % (T1, self.repo.head())])
        # control: the plant is real, the conductor run directly (not isolated) loads it
        env = {k: v for k, v in os.environ.items() if not k.startswith("FLOW_")}
        env.update(self.homes, FLOW_TRUSTED="1", FLOW_SESSION=self.token)
        done = subprocess.run([sys.executable, "scripts/flow.py", "f", "next"], cwd=str(self.repo.dir), env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertTrue(done.stdout.startswith("BXILD "), (done.stdout, done.stderr))


if __name__ == "__main__":
    unittest.main()
