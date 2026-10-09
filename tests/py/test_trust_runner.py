"""Ticket 03 of trusted-checks: scripts/flow-trust.py hashes the flow's files, refuses to call the
conductor when they changed since the digest the session passed in, and prints the new digest."""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import helpers
from helpers import Repo

T1 = "plans/f/tasks/01-a.md"
STATE = ".feature-flow/state/flow-f.state"
TRUST = re.compile(r"^TRUST ([0-9a-f]{16}\.[0-9a-f]{16})$")
CHANGED = "STOP flow files changed since the last step:"


def load_runner():
    """scripts/flow-trust.py as a module, without running main(). Loading it outside -I drops
    sys.path[0] when that is the scripts folder, so sys.path is put back afterwards."""
    saved = list(sys.path)
    try:
        spec = importlib.util.spec_from_file_location("flow_trust", str(helpers.ROOT / "scripts" / "flow-trust.py"))
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
    finally:
        sys.path[:] = saved
    return runner


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

    def test_a_usage_error_of_its_own_is_a_stop_on_stdout_with_exit_1(self):
        for args in (("f",), ("--after-build", "01"), ("../x", "next")):
            rc, out, err = self.trust(*args, FLOW_TRUST="new")
            self.assertEqual(rc, 1, (args, out, err))
            self.assertTrue(out.startswith("STOP usage: FLOW_TRUST="), (args, out))
            self.assertIn("FLOW_SESSION=<token>", out)
            self.assertEqual(err, "", args)
            self.assertFalse(self.repo.path(STATE).exists())


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

    def test_loaded_from_another_folder_it_leaves_sys_path_alone(self):
        """Only its own folder is taken off sys.path; here sys.path[0] is the tests' folder."""
        saved = list(sys.path)
        try:
            spec = importlib.util.spec_from_file_location("flow_trust_kept", str(helpers.ROOT / "scripts" / "flow-trust.py"))
            spec.loader.exec_module(importlib.util.module_from_spec(spec))
            self.assertEqual(sys.path, saved)
        finally:
            sys.path[:] = saved

    def test_the_names_it_hashes_match_the_ones_the_conductor_looks_up(self):
        runner = load_runner()
        sys.path.insert(0, str(helpers.ROOT))
        try:
            from feature_flow import prompts
        finally:
            sys.path.remove(str(helpers.ROOT))
        self.assertEqual(set(runner.ROLES), set(prompts.ROLES.values()))
        self.assertEqual(set(runner.GUIDES), set(prompts.GUIDES.values()) | {"debug.md"})

    def test_it_names_every_guide_and_template_feature_flow_ships(self):
        runner = load_runner()
        guides = helpers.ROOT / "guides"
        shipped = {p.name for p in guides.iterdir() if p.is_file()}
        self.assertEqual(set(runner.GUIDES) | set(runner.SKILL_GUIDES), shipped)
        self.assertEqual(set(runner.TEMPLATES), {p.name for p in (guides / "templates").iterdir() if p.is_file()})


class Trips(Base):
    """Each change between calls makes the next call STOP, naming the path."""

    def prepare(self):
        self.write(self.repo.path(".feature-flow/guides/build.md"), "# guide\n")
        self.write(self.repo.path(".claude/agents/ticket-builder.md"), "# role\n")
        self.write(self.repo.path(".claude/skills/feature-flow/SKILL.md"), "# skill\n")
        self.write(self.repo.path("guides/build.md"), "# root guide\n")
        self.write(self.repo.path("guides/brief.md"), "# root brief\n")
        self.write(self.repo.path("guides/templates/ticket.md"), "# root template\n")
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

    def test_an_edited_template_in_the_root(self):
        self.begin()
        self.append(self.repo.path("guides/templates/ticket.md"))
        self.assertStops("guides/templates/ticket.md")

    def test_an_edited_skill_guide_in_the_root(self):
        self.begin()
        self.append(self.repo.path("guides/brief.md"))
        self.assertStops("guides/brief.md")

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
        runner = load_runner()
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
        environ = mock.patch.dict(os.environ)
        environ.start()
        self.addCleanup(environ.stop)
        os.environ.pop("AGENTS_HOME", None)
        rc, lines, err = self.passed("start", HOME=home.name)
        self.assertEqual(rc, 0, (lines, err))
        self.append(skill)
        rc, out, err = self.call("start", HOME=home.name, FLOW_TAKEOVER="1")
        self.assertEqual(rc, 1, (out, err))
        self.assertTrue(out.startswith(CHANGED), out)
        self.assertIn(skill.resolve().as_posix(), out)


class KilledInProcess(Base):
    """main() run in this process with a fake conductor result, so no signal has to exist here."""

    def run_main(self, result):
        runner = load_runner()
        out = io.TextIOWrapper(io.BytesIO(), encoding="utf-8", newline="")
        err = io.TextIOWrapper(io.BytesIO(), encoding="utf-8", newline="")
        env = dict(self.env(FLOW_TRUST="new"))
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(runner, "started", return_value=(self.repo.path("scripts").resolve(), ["f", "start"])), \
                mock.patch.object(runner, "toplevel", return_value=Path(str(self.repo.dir)).resolve()), \
                mock.patch.object(runner, "run_conductor", return_value=result) as conductor, \
                mock.patch.object(sys, "stdout", out), mock.patch.object(sys, "stderr", err):
            code = runner.main()
            out.flush()
            err.flush()
        self.assertEqual(conductor.call_count, 1)
        return code, out.buffer.getvalue().decode("utf-8"), err.buffer.getvalue().decode("utf-8")

    def test_a_negative_return_code_is_a_stop_with_exit_1(self):
        """A killed conductor cannot vouch for the state it left: the STOP takes the TRUST line's place."""
        result = types.SimpleNamespace(returncode=-9, stdout=b"OK abc\n", stderr=b"oops\n")
        code, out, err = self.run_main(result)
        self.assertEqual(code, 1, (out, err))
        lines = out.splitlines()
        self.assertEqual(lines[0], "STOP the conductor was killed by signal 9")
        self.assertEqual(lines[1:], ["OK abc"])
        self.assertNotIn("TRUST", out)
        self.assertEqual(err, "oops\n")
        self.assertFalse(self.repo.path(".feature-flow/state/flow-f.trust").exists())

    def test_a_normal_return_code_is_passed_through(self):
        result = types.SimpleNamespace(returncode=3, stdout=b"STOP x\n", stderr=b"flow-state none none\n")
        code, out, err = self.run_main(result)
        self.assertEqual(code, 3, (out, err))
        self.assertNotIn("killed", out)


class FakeLinks:
    """A tiny file system for tree() and hash_files(): folders, files and folder links,
    served through mocks of os.listdir, os.path.realpath and Path.is_symlink/is_dir/is_file/read_bytes,
    so no real link is needed on any platform."""

    def __init__(self, root, folders, files, links):
        self.root = Path(root)
        self.folders = {self.root / f for f in folders}
        self.files = {self.root / f for f in files}
        self.links = {self.root / k: self.root / v for k, v in links.items()}

    def real(self, path):
        path = Path(path)
        for _ in range(50):
            for link, target in self.links.items():
                if path == link or link in path.parents:
                    path = target / path.relative_to(link)
                    break
            else:
                return path
        raise AssertionError("fake realpath did not settle: %s" % path)

    def realpath(self, path):
        return str(self.real(path))

    def listdir(self, path):
        real = self.real(path)
        if real not in self.folders:
            raise FileNotFoundError(str(path))
        return [p.name for p in self.folders | self.files | set(self.links) if p.parent == real]

    def patches(self):
        fake = self
        cls = type(Path())
        return [
            mock.patch("os.path.realpath", side_effect=self.realpath),
            mock.patch("os.listdir", side_effect=self.listdir),
            mock.patch.object(cls, "is_symlink", lambda p: fake.real(p.parent) / p.name in fake.links),
            mock.patch.object(cls, "is_dir", lambda p: fake.real(p) in fake.folders),
            mock.patch.object(cls, "is_file", lambda p: fake.real(p) in fake.files),
            mock.patch.object(cls, "read_bytes", lambda p: fake.real(p).as_posix().encode("utf-8")),
            mock.patch("os.readlink", side_effect=lambda p: str(fake.links[fake.real(Path(p).parent) / Path(p).name])),
        ]


class LinkedFolders(unittest.TestCase):
    """tree() follows linked folders and lists them; a loop ends. Checked in this process on a fake
    file system, so it runs the same everywhere."""

    ROOT = Path(tempfile.gettempdir()) / "fake-flow"

    def setUp(self):
        self.runner = load_runner()

    def fs(self, links):
        return FakeLinks(self.ROOT, ["feature_flow", "feature_flow/__pycache__", "outside"],
                         ["feature_flow/conductor.py", "feature_flow/__pycache__/conductor.pyc", "outside/evil.py"],
                         links)

    def walk(self, fs):
        with contextlib.ExitStack() as stack:
            for patch in fs.patches():
                stack.enter_context(patch)
            found = self.runner.tree(self.ROOT / "feature_flow")
            each = self.runner.hash_files(found, self.ROOT)
        return [p.relative_to(self.ROOT).as_posix() for p in found], each

    def test_a_linked_folder_is_listed_and_followed(self):
        found, each = self.walk(self.fs({"feature_flow/linked": "outside"}))
        self.assertEqual(found, ["feature_flow/conductor.py", "feature_flow/linked", "feature_flow/linked/evil.py"])
        target = "link " + str(self.ROOT / "outside")
        self.assertEqual(each["feature_flow/linked"], hashlib.sha256(target.encode("utf-8")).hexdigest())
        self.assertIn("feature_flow/linked/evil.py", each)

    def test_adding_a_linked_folder_changes_the_code_part(self):
        _, without = self.walk(self.fs({}))
        _, linked = self.walk(self.fs({"feature_flow/linked": "outside"}))
        self.assertNotEqual(self.runner.part(without), self.runner.part(linked))

    def test_a_link_to_nothing_is_hashed_by_its_target_text(self):
        found, each = self.walk(self.fs({"feature_flow/gone": "missing"}))
        self.assertEqual(found, ["feature_flow/conductor.py", "feature_flow/gone"])
        target = "link " + str(self.ROOT / "missing")
        self.assertEqual(each["feature_flow/gone"], hashlib.sha256(target.encode("utf-8")).hexdigest())
        _, swapped = self.walk(self.fs({"feature_flow/gone": "elsewhere"}))
        self.assertNotEqual(self.runner.part(each), self.runner.part(swapped))

    def test_a_looping_link_is_listed_but_not_entered_again(self):
        found, each = self.walk(self.fs({"feature_flow/loop": "feature_flow"}))
        self.assertEqual(found, ["feature_flow/conductor.py", "feature_flow/loop"])
        self.assertIn("feature_flow/loop", each)


# Double quotes, which both bash -c and cmd.exe read.
PYTHON = '"%s"' % sys.executable
DURING = "STOP flow code changed during %s: %s"
STATE_CHANGED = "STOP the run state was changed by something other than the conductor during %s"
NO_REPORT = "STOP the conductor did not report its state (it crashed?) during %s"


class HoleC(Base):
    """Hole (c): the gate's Test command runs the builder's t.py inside `next`, and t.py edits
    feature_flow/conductor.py. The code must be the same after the call as before it."""

    def prepare(self):
        self.write(self.repo.path("plans/f/commands.md"), "# Commands: f\n\nTest: `%s t.py`\n" % PYTHON)

    def test_a_test_command_that_edits_the_conductor_stops(self):
        self.begin()
        self.write(self.repo.path("t.py"),
                   "with open('feature_flow/conductor.py', 'ab') as handle:\n"
                   "    handle.write(b'\\n# edited by t.py\\n')\n")
        self.repo.resolve(T1)
        before = self.repo.path("feature_flow/conductor.py").read_bytes()
        rc, out, err = self.call("next")
        self.assertNotEqual(self.repo.path("feature_flow/conductor.py").read_bytes(), before, "t.py did not run")
        self.assertEqual(rc, 1, (out, err))
        self.assertEqual(out.splitlines()[0], DURING % ("next", "feature_flow/conductor.py"))
        self.assertNotRegex(out, r"(?m)^TRUST ")

    def test_a_test_command_that_edits_nothing_goes_through(self):
        self.begin()
        self.write(self.repo.path("t.py"), "print('fine')\n")
        self.repo.resolve(T1)
        rc, lines, err = self.passed("next")
        self.assertEqual(rc, 0, (lines, err))
        self.assertTrue(lines[0].startswith("REVIEW "), (lines, err))


STAND_IN = """import hashlib, os, sys
from pathlib import Path
mode = os.environ["STAND_IN"]
folder = Path(".feature-flow") / "state"
folder.mkdir(parents=True, exist_ok=True)
data = b"phase=build\\n"
(folder / ("flow-%s.state" % sys.argv[1])).write_bytes(data)
real = hashlib.sha256(data).hexdigest()
if mode == "findings":
    (folder / ("flow-%s.findings" % sys.argv[1])).write_bytes(b"late\\n")
print("OK stand-in")
sys.stdout.flush()
if mode in ("right", "findings"):
    sys.stderr.write("flow-state %s none\\n" % real)
elif mode == "wrong":
    sys.stderr.write("flow-state %s none\\n" % ("0" * 64))
"""


class StateAsSaved(unittest.TestCase):
    """A stand-in flow.py beside a copy of the runner writes the state file, then reports a
    different sha, no flow-state line at all, or the right one."""

    def setUp(self):
        self.repo = Repo(local=False)
        self.addCleanup(self.repo.close)
        conductor = tempfile.TemporaryDirectory()
        self.addCleanup(conductor.cleanup)
        self.folder = Path(conductor.name) / "scripts"
        self.folder.mkdir()
        shutil.copy(str(helpers.ROOT / "scripts" / "flow-trust.py"), str(self.folder))
        (self.folder / "flow.py").write_text(STAND_IN, encoding="utf-8")
        self.homes = {}
        for name in ("CLAUDE_HOME", "AGENTS_HOME", "FEATURE_FLOW_HOME"):
            folder = tempfile.TemporaryDirectory()
            self.addCleanup(folder.cleanup)
            self.homes[name] = folder.name

    def run_mode(self, mode):
        env = {k: v for k, v in os.environ.items() if not k.startswith("FLOW_")}
        env.update(self.homes, FLOW_TRUST="new", STAND_IN=mode)
        result = subprocess.run([sys.executable, "-I", str(self.folder / "flow-trust.py"), "f", "next"],
                                cwd=str(self.repo.dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                universal_newlines=True, env=env)
        self.assertTrue(self.repo.path(STATE).is_file(), result.stderr)
        return result.returncode, result.stdout.splitlines(), result.stderr

    def test_a_different_sha_stops(self):
        rc, lines, err = self.run_mode("wrong")
        self.assertEqual(rc, 1, (lines, err))
        self.assertEqual(lines[0], STATE_CHANGED % "next")
        self.assertNotIn("flow-state", err)

    def test_no_flow_state_line_stops_saying_the_conductor_did_not_report(self):
        rc, lines, err = self.run_mode("silent")
        self.assertEqual(rc, 1, (lines, err))
        self.assertEqual(lines[0], NO_REPORT % "next")

    def test_a_file_that_exists_when_the_report_says_none_stops(self):
        rc, lines, err = self.run_mode("findings")
        self.assertEqual(rc, 1, (lines, err))
        self.assertEqual(lines[0], STATE_CHANGED % "next")

    def test_the_right_sha_goes_through(self):
        rc, lines, err = self.run_mode("right")
        self.assertEqual(rc, 0, (lines, err))
        self.assertRegex(lines[0], TRUST)
        self.assertEqual(lines[1:], ["OK stand-in"])
        self.assertNotIn("flow-state", err)


FLOOR = "Floor: allow flow-edit\n"


def with_floor(data):
    """The ticket's bytes with the Floor line after `Type: task`, in the file's own line ending."""
    return helpers.insert_after_line(data, b"Type: task", FLOOR.strip().encode())


class FlowEditBase(Base):
    """--after-build <ticket> <sha>: a code change is accepted only when the ticket at <sha>
    has `Floor: allow flow-edit`; a state change never is."""

    floor = True

    def prepare(self):
        if self.floor:
            path = self.repo.path(T1)
            path.write_bytes(with_floor(path.read_bytes()))

    def build(self, ticket_edit=None):
        """start, BUILD, then the builder edits feature_flow/floorguard.py and commits; returns the base."""
        rc, lines, err = self.passed("start")
        self.token = lines[0].split()[1]
        rc, lines, err = self.passed("next")
        self.assertTrue(lines[0].startswith("BUILD "), (lines, err))
        base = lines[0].split()[3]
        with open(str(self.repo.path("feature_flow/floorguard.py")), "ab") as handle:
            handle.write(b"\n# a flow-edit build\n")
        if ticket_edit:
            ticket_edit()
        self.repo.resolve(T1)
        return base

    def after_build(self, base):
        rc, out, err = self.trust("--after-build", T1, base, "f", "next",
                                  FLOW_TRUST=self.digest, FLOW_SESSION=self.token)
        return rc, out.splitlines(), err

    def assertStopped(self, rc, lines, err):
        self.assertEqual(rc, 1, (lines, err))
        self.assertTrue(lines[0].startswith(CHANGED), (lines, err))
        self.assertFalse(any(line.startswith("FLOW-EDIT") for line in lines), lines)


class FlowEdit(FlowEditBase):
    def test_a_ticket_that_allows_flow_edit_at_its_base_is_accepted(self):
        base = self.build()
        rc, lines, err = self.after_build(base)
        self.assertEqual(rc, 0, (lines, err))
        self.assertRegex(lines[0], TRUST)
        self.assertEqual(lines[1], "FLOW-EDIT feature_flow/floorguard.py")
        self.assertTrue(lines[2].startswith("REVIEW "), (lines, err))
        self.digest = TRUST.match(lines[0]).group(1)
        rc, lines, err = self.passed("next")
        self.assertFalse(lines[0].startswith(CHANGED), lines)

    def test_without_the_flag_it_stops(self):
        self.build()
        rc, out, err = self.call("next")
        self.assertStopped(rc, out.splitlines(), err)
        self.assertIn("feature_flow/floorguard.py", out)

    def test_a_state_change_with_trust_rewritten_to_match_stops(self):
        base = self.build()
        self.append(self.repo.path(STATE), "phase=\n")
        trust = self.repo.path(".feature-flow/state/flow-f.trust")
        each = json.loads(trust.read_text(encoding="utf-8"))
        for rel in ("feature_flow/floorguard.py", STATE):
            each[rel] = hashlib.sha256(self.repo.path(rel).read_bytes()).hexdigest()
        trust.write_text(json.dumps(each, sort_keys=True, indent=1) + "\n", encoding="utf-8")
        rc, lines, err = self.after_build(base)
        self.assertStopped(rc, lines, err)

    def test_a_state_change_alone_stops_with_the_flag(self):
        base = self.build()
        self.append(self.repo.path(STATE), "phase=\n")
        rc, lines, err = self.after_build(base)
        self.assertStopped(rc, lines, err)
        self.assertIn(STATE, lines[0])


class FlowEditNoLine(FlowEditBase):
    floor = False

    def test_a_ticket_without_the_line_stops(self):
        base = self.build()
        rc, lines, err = self.after_build(base)
        self.assertStopped(rc, lines, err)

    def test_the_line_added_after_the_base_stops(self):
        path = self.repo.path(T1)
        base = self.build(lambda: path.write_bytes(with_floor(path.read_bytes())))
        self.assertIn(FLOOR, path.read_text(encoding="utf-8"))
        rc, lines, err = self.after_build(base)
        self.assertStopped(rc, lines, err)

    def test_a_git_replace_of_the_ticket_blob_is_ignored(self):
        base = self.build()
        old = self.repo.git("rev-parse", "%s:%s" % (base, T1))
        forged = self.repo.dir / ".git" / "forged-ticket"
        forged.write_bytes(with_floor(self.repo.path(T1).read_bytes()))
        new = self.repo.git("hash-object", "-w", str(forged))
        self.repo.git("replace", old, new)
        self.assertIn(FLOOR.strip(), self.repo.git("cat-file", "blob", "%s:%s" % (base, T1)))
        rc, lines, err = self.after_build(base)
        self.assertStopped(rc, lines, err)


class Handoff(Base):
    """Ticket 05: at HANDOFF the runner adds its TRUST digest, and a new session passes it as
    FLOW_TRUST on its first call (start), so the gap between sessions is checked too."""

    ONE = {"FLOW_TICKETS_PER_SESSION": "1"}

    def reply(self, text):
        path = self.repo.dir.parent / (self.repo.dir.name + "-reply.txt")
        path.write_text(text, encoding="utf-8")
        self.addCleanup(path.unlink, missing_ok=True)
        rc, lines, err = self.passed("verdict", str(path), **self.ONE)
        self.assertEqual((rc, lines), (0, ["OK"]), err)

    def to_handoff(self):
        """One ticket built, resolved and passed by both review passes; the next `next` hands off."""
        rc, lines, err = self.passed("start", **self.ONE)
        self.token = lines[0].split()[1]
        rc, lines, err = self.passed("next", **self.ONE)
        self.assertTrue(lines[0].startswith("BUILD "), (lines, err))
        self.repo.resolve(T1)
        for review in ("spec", "quality"):
            rc, lines, err = self.passed("next", **self.ONE)
            self.assertTrue(lines[0].startswith("REVIEW "), (review, lines, err))
            self.reply("fine\nREVIEW: PASS\n")

    def handoff(self):
        """The runner's HANDOFF call; returns the digest on its HANDOFF line."""
        self.to_handoff()
        rc, lines, err = self.passed("next", **self.ONE)
        self.assertEqual(rc, 0, (lines, err))
        self.assertEqual(lines, ["HANDOFF /feature-flow f %s" % self.digest], err)
        return lines[0].split()[3]

    def new_session_start(self, trust):
        rc, out, err = self.trust("f", "start", FLOW_TRUST=trust, **self.ONE)
        return rc, out.splitlines(), err

    def test_the_runner_adds_its_trust_digest_to_handoff(self):
        digest = self.handoff()
        self.assertRegex("TRUST " + digest, TRUST)

    def test_start_with_the_handoff_digest_goes_through(self):
        digest = self.handoff()
        rc, lines, err = self.new_session_start(digest)
        self.assertEqual(rc, 0, (lines, err))
        self.assertRegex(lines[0], TRUST)
        self.assertTrue(lines[1].startswith("OK "), (lines, err))

    def test_an_edited_conductor_between_the_sessions_stops_naming_it(self):
        digest = self.handoff()
        with open(str(self.repo.path("feature_flow/conductor.py")), "ab") as handle:
            handle.write(b"\n# edited between sessions\n")
        rc, lines, err = self.new_session_start(digest)
        self.assertEqual(rc, 1, (lines, err))
        self.assertTrue(lines[0].startswith(CHANGED), (lines, err))
        self.assertIn("feature_flow/conductor.py", lines[0])
        self.assertFalse(any(line.startswith("OK ") for line in lines), lines)

    def test_an_old_style_handoff_with_no_digest_still_starts_with_new(self):
        self.handoff()
        rc, lines, err = self.new_session_start("new")
        self.assertEqual(rc, 0, (lines, err))
        self.assertRegex(lines[0], TRUST)
        self.assertTrue(lines[1].startswith("OK "), (lines, err))

    def test_the_conductor_run_directly_prints_handoff_unchanged(self):
        self.to_handoff()
        env = self.env(FLOW_TRUSTED="1", FLOW_SESSION=self.token, **self.ONE)
        result = subprocess.run([sys.executable, "scripts/flow.py", "f", "next"], cwd=str(self.repo.dir),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.decode("utf-8").splitlines(), ["HANDOFF /feature-flow f"])

    def test_only_a_one_line_handoff_reply_of_next_gets_the_digest(self):
        runner = load_runner()
        self.assertEqual(runner.with_digest(b"HANDOFF /feature-flow f\r\n", "next", "f", "d.e"),
                         b"HANDOFF /feature-flow f d.e\r\n")
        quoted = b"# a prompt\nHANDOFF /feature-flow f\n"
        self.assertEqual(runner.with_digest(quoted, "next", "f", "d.e"), quoted)
        self.assertEqual(runner.with_digest(quoted, "prompt", "f", "d.e"), quoted)
        self.assertEqual(runner.with_digest(b"HANDOFF /feature-flow f\n", "prompt", "f", "d.e"),
                         b"HANDOFF /feature-flow f\n")

    def test_a_stop_after_the_call_leaves_handoff_without_a_digest(self):
        """A digest is only given when the runner trusts the result: an after-call STOP takes the
        TRUST line's place and the conductor's HANDOFF line follows as the conductor printed it."""
        self.to_handoff()
        runner = load_runner()
        top = self.repo.dir.resolve()
        here = top / "scripts"
        result = types.SimpleNamespace(returncode=-9, stdout=b"HANDOFF /feature-flow f\n", stderr=b"")
        out = io.TextIOWrapper(io.BytesIO())
        with mock.patch.object(runner, "started", return_value=(here, ["f", "next"])), \
                mock.patch.object(runner, "toplevel", return_value=top), \
                mock.patch.object(runner, "run_conductor", return_value=result), \
                mock.patch.dict(os.environ, self.env(FLOW_TRUST=self.digest), clear=True), \
                mock.patch.object(sys, "stdout", out), \
                mock.patch.object(sys, "stderr", io.TextIOWrapper(io.BytesIO())):
            rc = runner.main()
        out.flush()
        lines = out.buffer.getvalue().decode("utf-8").splitlines()
        self.assertEqual(rc, 1)
        self.assertEqual(lines, ["STOP the conductor was killed by signal 9", "HANDOFF /feature-flow f"])


if __name__ == "__main__":
    unittest.main()
