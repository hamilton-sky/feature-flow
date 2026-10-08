"""Ticket 03 of trusted-checks: scripts/flow-trust.py hashes the flow's files, refuses to call the
conductor when they changed since the digest the session passed in, and prints the new digest."""

import hashlib
import importlib.util
import json
import os
import py_compile
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import helpers
from helpers import Repo

T1 = "plans/f/tasks/01-a.md"
STATE = ".feature-flow/state/flow-f.state"
TRUST = re.compile(r"^TRUST ([0-9a-f]{16}\.[0-9a-f]{16})$")
CHANGED = "STOP flow files changed since the last step:"


class Base(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.addCleanup(self.repo.close)
        shutil.copy(str(helpers.ROOT / "scripts" / "flow-trust.py"), str(self.repo.path("scripts")))
        self.homes = {}
        for name in ("CLAUDE_HOME", "AGENTS_HOME", "FEATURE_FLOW_HOME"):
            folder = tempfile.TemporaryDirectory()
            self.addCleanup(folder.cleanup)
            self.homes[name] = Path(folder.name)
        self.prepare()
        self.repo.git("add", "-A")
        self.repo.git("commit", "-q", "--allow-empty", "-m", "layout")
        self.digest = None
        self.token = None

    def prepare(self):
        """Files that exist before the run starts."""

    def write(self, path, text):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def append(self, path, text="\n# edited\n"):
        with open(str(path), "a", encoding="utf-8") as handle:
            handle.write(text)

    def env(self, **extra):
        full = {k: v for k, v in os.environ.items() if not k.startswith("FLOW_")}
        full.update({k: str(v) for k, v in self.homes.items()})
        full.update(extra)
        return full

    def trust(self, *args, **env):
        """Run the runner directly with -I; returns (exit code, stdout, stderr)."""
        result = subprocess.run([sys.executable, "-I", "scripts/flow-trust.py"] + list(args),
                                cwd=str(self.repo.dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True, env=self.env(**env))
        return result.returncode, result.stdout, result.stderr

    def call(self, command, *args, **extra):
        """A call that passes the last digest (new on the first call) and the session token."""
        env = {"FLOW_TRUST": self.digest or "new"}
        if self.token:
            env["FLOW_SESSION"] = self.token
        env.update(extra)
        return self.trust("f", command, *args, **env)

    def passed(self, command, *args, **extra):
        """A call the runner lets through: TRUST first, then the conductor's output."""
        rc, out, err = self.call(command, *args, **extra)
        lines = out.splitlines()
        self.assertTrue(lines, "no output; stderr: %s" % err)
        match = TRUST.match(lines[0])
        self.assertIsNotNone(match, "first line is not TRUST: %r (stderr %r)" % (out, err))
        self.digest = match.group(1)
        return rc, lines[1:], err

    def begin(self):
        rc, lines, err = self.passed("start")
        self.assertEqual(rc, 0, (lines, err))
        self.assertTrue(lines[0].startswith("OK "), lines)
        self.token = lines[0].split()[1]
        rc, lines, err = self.passed("next")
        self.assertEqual(rc, 0, (lines, err))
        self.assertTrue(lines[0].startswith("BUILD "), lines)

    def assertStops(self, *names):
        rc, out, err = self.call("next")
        self.assertEqual(rc, 1, (out, err))
        first = out.splitlines()[0] if out else ""
        self.assertTrue(first.startswith(CHANGED), (out, err))
        for name in names:
            self.assertIn(name, first)
        self.assertNotIn("BUILD", out)
        self.assertNotIn("REVIEW", out)

    def assertGoesOn(self):
        """The runner calls the conductor: TRUST first, then the conductor's own line (here a STOP
        about the missing role file, which the fixture does not install)."""
        rc, lines, err = self.passed("prompt")
        self.assertTrue(lines, err)
        self.assertFalse(lines[0].startswith(CHANGED), lines)
        self.assertNotIn("flow-state", err)


class FirstCalls(Base):
    def test_a_first_call_prints_trust_then_the_conductor_line(self):
        rc, out, err = self.trust("f", "start", FLOW_TRUST="new")
        self.assertEqual(rc, 0, (out, err))
        lines = out.splitlines()
        self.assertRegex(lines[0], TRUST)
        self.assertRegex(lines[1], r"^OK [0-9a-f]+$")
        self.assertNotIn("flow-state", err)

    def test_a_later_call_with_the_digest_goes_through(self):
        self.begin()
        rc, lines, err = self.passed("next")
        self.assertEqual(rc, 0, (lines, err))
        self.assertTrue(lines[0].startswith("BUILD "), lines)

    def test_a_missing_or_empty_flow_trust_stops(self):
        for env in ({}, {"FLOW_TRUST": ""}):
            rc, out, err = self.trust("f", "start", **env)
            self.assertEqual(rc, 1, (out, err))
            self.assertEqual(out.strip(), "STOP pass FLOW_TRUST: the last TRUST digest, or new on this session's first call")
            self.assertFalse(self.repo.path(STATE).exists())

    def test_a_wrong_digest_stops_before_the_conductor_runs(self):
        rc, out, err = self.trust("f", "start", FLOW_TRUST="0" * 16 + "." + "0" * 16)
        self.assertEqual(rc, 1, (out, err))
        self.assertTrue(out.startswith(CHANGED), out)
        self.assertFalse(self.repo.path(STATE).exists())

    def test_after_build_is_accepted_and_ignored(self):
        rc, out, err = self.trust("--after-build", "01", "abc", "f", "start", FLOW_TRUST="new")
        self.assertEqual(rc, 0, (out, err))
        self.assertRegex(out.splitlines()[1], r"^OK ")

    def test_the_per_file_list_is_written_sorted_and_not_hashed_itself(self):
        self.begin()
        path = self.repo.path(".feature-flow/state/flow-f.trust")
        text = path.read_text(encoding="utf-8")
        each = json.loads(text)
        self.assertEqual(list(each), sorted(each))
        self.assertIn("feature_flow/conductor.py", each)
        self.assertIn("scripts/flow-trust.py", each)
        self.assertIn(STATE, each)
        self.assertNotIn(".feature-flow/state/flow-f.trust", each)
        path.write_text("{}", encoding="utf-8")
        self.assertGoesOn()

    def test_the_conductor_exit_code_and_stderr_pass_through(self):
        rc, out, err = self.trust("f", "bogus", FLOW_TRUST="new")
        self.assertEqual(rc, 2, (out, err))
        self.assertRegex(out.splitlines()[0], TRUST)
        self.assertIn("usage:", err)
        self.assertNotIn("flow-state", err)


class Started(Base):
    def test_it_runs_as_exec_of_its_bytes_by_the_loader(self):
        loader = ("import hashlib,sys;b=open(sys.argv[1],'rb').read().replace(b'\\r\\n',b'\\n');"
                  "sys.exit(exec(compile(b,'flow-trust','exec')) if hashlib.sha256(b).hexdigest()==sys.argv[2] "
                  "else 'flow-trust.py does not match this skill')")
        path = self.repo.path("scripts/flow-trust.py")
        pinned = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        result = subprocess.run([sys.executable, "-I", "-c", loader, str(path), pinned, "f", "start"],
                                cwd=str(self.repo.dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True, env=self.env(FLOW_TRUST="new"))
        self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
        lines = result.stdout.splitlines()
        self.assertRegex(lines[0], TRUST)
        self.assertRegex(lines[1], r"^OK ")

    def test_the_names_it_hashes_match_the_ones_the_conductor_looks_up(self):
        spec = importlib.util.spec_from_file_location("flow_trust", str(helpers.ROOT / "scripts" / "flow-trust.py"))
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        sys.path.insert(0, str(helpers.ROOT))
        try:
            from feature_flow import prompts
        finally:
            sys.path.remove(str(helpers.ROOT))
        self.assertEqual(set(runner.ROLES), set(prompts.ROLES.values()))
        self.assertEqual(set(runner.GUIDES), set(prompts.GUIDES.values()) | {"debug.md"})


class Trips(Base):
    """Each change between calls makes the next call STOP, naming the path."""

    def prepare(self):
        self.write(self.repo.path(".feature-flow/guides/build.md"), "# guide\n")
        self.write(self.repo.path(".claude/agents/ticket-builder.md"), "# role\n")
        self.write(self.repo.path(".claude/skills/feature-flow/SKILL.md"), "# skill\n")
        self.write(self.repo.path("guides/build.md"), "# root guide\n")
        self.write(self.homes["FEATURE_FLOW_HOME"] / "guides" / "build.md", "# home guide\n")
        self.write(self.repo.path(".agents/skills/feature-flow/SKILL.md"), "# skill\n")
        self.write(self.repo.path(".agents/flow-roles/ticket-builder.md"), "# role\n")
        self.write(self.repo.path(".feature-flow/agents/ticket-builder.md"), "# role\n")
        self.write(self.homes["CLAUDE_HOME"] / "skills" / "feature-flow" / "SKILL.md", "# skill\n")
        self.write(self.homes["AGENTS_HOME"] / "skills" / "feature-flow" / "SKILL.md", "# skill\n")

    def test_an_edited_conductor(self):
        self.begin()
        self.append(self.repo.path("feature_flow/conductor.py"))
        self.assertStops("feature_flow/conductor.py")

    def test_a_new_package_file(self):
        self.begin()
        self.write(self.repo.path("feature_flow/extra.py"), "x = 1\n")
        self.assertStops("feature_flow/extra.py")

    def test_an_edited_guide(self):
        self.begin()
        self.append(self.repo.path(".feature-flow/guides/build.md"))
        self.assertStops(".feature-flow/guides/build.md")

    def test_an_edited_role(self):
        self.begin()
        self.append(self.repo.path(".claude/agents/ticket-builder.md"))
        self.assertStops(".claude/agents/ticket-builder.md")

    def test_an_edited_skill(self):
        self.begin()
        self.append(self.repo.path(".claude/skills/feature-flow/SKILL.md"))
        self.assertStops(".claude/skills/feature-flow/SKILL.md")

    def test_a_line_added_to_the_state(self):
        self.begin()
        self.append(self.repo.path(STATE), "extra=1\n")
        self.assertStops(STATE)

    def test_an_edited_guide_in_the_root(self):
        self.begin()
        self.append(self.repo.path("guides/build.md"))
        self.assertStops("guides/build.md")

    def test_a_missing_guide_in_the_root(self):
        self.begin()
        self.repo.path("guides/build.md").unlink()
        self.assertStops("guides/build.md")

    def test_an_edit_under_feature_flow_home(self):
        self.begin()
        path = self.homes["FEATURE_FLOW_HOME"] / "guides" / "build.md"
        self.append(path)
        self.assertStops(path.resolve().as_posix())

    def test_an_edited_agents_skill(self):
        self.begin()
        self.append(self.repo.path(".agents/skills/feature-flow/SKILL.md"))
        self.assertStops(".agents/skills/feature-flow/SKILL.md")

    def test_an_edited_flow_role_under_agents(self):
        self.begin()
        self.append(self.repo.path(".agents/flow-roles/ticket-builder.md"))
        self.assertStops(".agents/flow-roles/ticket-builder.md")

    def test_an_edited_role_under_feature_flow_agents(self):
        self.begin()
        self.append(self.repo.path(".feature-flow/agents/ticket-builder.md"))
        self.assertStops(".feature-flow/agents/ticket-builder.md")

    def test_an_edited_skill_under_claude_home(self):
        self.begin()
        path = self.homes["CLAUDE_HOME"] / "skills" / "feature-flow" / "SKILL.md"
        self.append(path)
        self.assertStops(path.resolve().as_posix())

    def test_an_edited_skill_under_agents_home(self):
        self.begin()
        path = self.homes["AGENTS_HOME"] / "skills" / "feature-flow" / "SKILL.md"
        self.append(path)
        self.assertStops(path.resolve().as_posix())

    def link(self, link, target):
        try:
            os.symlink(str(target), str(link), target_is_directory=True)
        except (OSError, NotImplementedError) as error:  # Windows without the symlink privilege
            self.skipTest("cannot make a folder link here: %s" % error)

    def test_a_linked_folder_in_the_package(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        self.write(Path(outside.name) / "evil.py", "x = 1\n")
        self.begin()
        self.link(self.repo.path("feature_flow/linked"), outside.name)
        self.assertStops("feature_flow/linked")

    def test_an_edit_inside_a_linked_folder(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        self.write(Path(outside.name) / "evil.py", "x = 1\n")
        self.link(self.repo.path("feature_flow/linked"), outside.name)
        self.repo.commit("link")
        self.begin()
        self.append(Path(outside.name) / "evil.py")
        self.assertStops("feature_flow/linked/evil.py")

    def test_a_looping_link_ends_and_trips(self):
        self.begin()
        self.link(self.repo.path("feature_flow/loop"), self.repo.path("feature_flow"))
        self.assertStops("feature_flow/loop")

    def test_hole_a_a_committed_return_in_check_code(self):
        self.begin()
        path = self.repo.path("feature_flow/conductor.py")
        text = path.read_text(encoding="utf-8")
        marker = '        """Stop when the files the conductor runs from changed since the ticket was picked."""\n'
        self.assertIn(marker, text)
        path.write_text(text.replace(marker, marker + "        return\n", 1), encoding="utf-8")
        self.repo.resolve(T1)
        self.assertStops("feature_flow/conductor.py")

    def test_hole_b_phase_written_into_the_state(self):
        self.begin()
        self.repo.resolve(T1)
        self.append(self.repo.path(STATE), "phase=\n")
        self.assertStops(STATE)

    def test_without_an_earlier_list_the_paths_are_not_named(self):
        self.begin()
        self.repo.path(".feature-flow/state/flow-f.trust").unlink()
        self.append(self.repo.path("feature_flow/conductor.py"))
        rc, out, err = self.call("next")
        self.assertEqual(rc, 1, (out, err))
        self.assertEqual(out.strip(), CHANGED + " (no earlier list to name them)")


class NoTrips(Base):
    """Changes to files the flow does not run from never stop the run."""

    def test_the_users_own_guides_and_agents_in_the_root(self):
        self.begin()
        self.write(self.repo.path("guides/notes.md"), "mine\n")
        self.write(self.repo.path("agents/x.md"), "mine\n")
        self.assertGoesOn()

    def test_bytecode_scripts_review_reply_and_log(self):
        self.begin()
        self.write(self.repo.path("feature_flow/__pycache__/x.pyc"), "junk")
        self.write(self.repo.path("scripts/deploy.sh"), "echo hi\n")
        self.write(self.repo.path(".feature-flow/state/flow-review-f.txt"), "REVIEW: PASS\n")
        self.append(self.repo.path(".feature-flow/state/flow-f.log"), "a line\n")
        self.assertGoesOn()


class PlantedBytecode(Base):
    """A .pyc compiled from an edited conductor.py, with the source's mtime and size, is never run."""

    def plant(self):
        source = self.repo.path("feature_flow/conductor.py")
        original = source.read_bytes()
        stat = source.stat()
        honest, forged = b'return "OK %s" % token', b'return "PW %s" % token'
        self.assertIn(honest, original)
        edited = original.replace(honest, forged, 1)
        self.assertEqual(len(edited), stat.st_size)
        source.write_bytes(edited)
        os.utime(str(source), (stat.st_atime, stat.st_mtime))
        cfile = importlib.util.cache_from_source(str(source))
        py_compile.compile(str(source), cfile=cfile, doraise=True,
                           invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)
        source.write_bytes(original)
        os.utime(str(source), (stat.st_atime, stat.st_mtime))

    def test_the_plant_would_run_without_the_runner(self):
        self.plant()
        result = subprocess.run([sys.executable, "scripts/flow.py", "f", "start"], cwd=str(self.repo.dir),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                                env=self.env())
        self.assertTrue(result.stdout.startswith("PW "), (result.stdout, result.stderr))

    def test_the_runner_runs_the_source(self):
        self.plant()
        rc, lines, err = self.passed("start")
        self.assertEqual(rc, 0, (lines, err))
        self.assertTrue(lines[0].startswith("OK "), lines)

    def test_a_plant_between_calls_does_not_trip_and_is_not_run(self):
        rc, lines, err = self.passed("start")
        self.assertTrue(lines[0].startswith("OK "), lines)
        self.plant()
        rc, lines, err = self.passed("start", FLOW_TAKEOVER="1")
        self.assertEqual(rc, 0, (lines, err))
        self.assertTrue(lines[0].startswith("OK "), lines)


class PlantedBytecodeCrlf(PlantedBytecode):
    """The same, with conductor.py checked out with CRLF line endings, as on Windows."""

    def prepare(self):
        path = self.repo.path("feature_flow/conductor.py")
        data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        path.write_bytes(data)
        self.assertIn(b"\r\n", path.read_bytes())


class Homes(Base):
    def test_unset_home_falls_back_like_the_installer(self):
        spec = importlib.util.spec_from_file_location("flow_trust", str(helpers.ROOT / "scripts" / "flow-trust.py"))
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        saved = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(saved)))
        for key in ("HOME", "AGENTS_HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH"):
            os.environ.pop(key, None)
        self.assertEqual(runner.home("AGENTS_HOME", ".agents"), Path("/.agents").resolve())

    def test_the_default_agents_home_is_under_home(self):
        home = tempfile.TemporaryDirectory()
        self.addCleanup(home.cleanup)
        del self.homes["AGENTS_HOME"]
        skill = Path(home.name) / ".agents" / "skills" / "feature-flow" / "SKILL.md"
        self.write(skill, "# skill\n")
        os.environ.pop("AGENTS_HOME", None)
        rc, lines, err = self.passed("start", HOME=home.name)
        self.assertEqual(rc, 0, (lines, err))
        self.append(skill)
        rc, out, err = self.call("start", HOME=home.name, FLOW_TAKEOVER="1")
        self.assertEqual(rc, 1, (out, err))
        self.assertTrue(out.startswith(CHANGED), out)
        self.assertIn(skill.resolve().as_posix(), out)


class Killed(Base):
    @unittest.skipUnless(hasattr(signal, "SIGKILL"), "no SIGKILL on this platform")
    def test_a_conductor_killed_by_a_signal_is_a_stop_with_exit_1(self):
        self.write(self.repo.path("scripts/flow.py"),
                   "import os, signal\nos.kill(os.getpid(), signal.SIGKILL)\n")
        rc, out, err = self.trust("f", "start", FLOW_TRUST="new")
        self.assertEqual(rc, 1, (out, err))
        lines = out.splitlines()
        self.assertRegex(lines[0], TRUST)
        self.assertEqual(lines[-1], "STOP the conductor was killed by signal %d" % signal.SIGKILL)


if __name__ == "__main__":
    unittest.main()
