"""Ticket 06 of trusted-checks: both skills pin the sha256 of scripts/flow-trust.py in one loader
line and call the conductor only through it."""

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import helpers
from helpers import Repo

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import gate  # the package under test, from this checkout

SKILLS = ("skills/feature-flow/SKILL.md", "adapters/codex/feature-flow/SKILL.md")
# spec.md § Interfaces, up to the pinned sha
LOADER = (r'''python3 -I -c "import hashlib,sys;b=open(sys.argv[1],'rb').read().replace(b'\r\n',b'\n');'''
          r'''sys.exit(exec(compile(b,'flow-trust','exec')) if hashlib.sha256(b).hexdigest()==sys.argv[2] '''
          r'''else 'flow-trust.py does not match this skill')" <S>/flow-trust.py ''')
LINE = re.compile(r"^[ \t]*(python3 -I -c .*<S>/flow-trust\.py ([0-9a-f]{64}))[ \t]*$", re.M)
PINNED = re.compile(r"flow-trust\.py ([0-9a-f]{64})")
TRUST = re.compile(r"^TRUST [0-9a-f]{16}\.[0-9a-f]{16}$")
MISMATCH = "flow-trust.py does not match this skill"


def skill_text(rel):
    return (helpers.ROOT / rel).read_text(encoding="utf-8")


def loader_line(rel):
    """(the loader line, its pinned sha) of one SKILL.md; fails unless there is exactly one."""
    found = LINE.findall(skill_text(rel))
    if len(found) != 1:
        raise AssertionError("%s: expected one loader line, found %d" % (rel, len(found)))
    return found[0]


def runner_sha():
    data = (helpers.ROOT / "scripts" / "flow-trust.py").read_bytes()
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


class SkillLoaderText(unittest.TestCase):
    def test_both_skills_hold_one_identical_loader_line(self):
        first, second = (loader_line(rel)[0] for rel in SKILLS)
        self.assertEqual(first, second)

    def test_the_loader_line_is_the_one_from_the_spec(self):
        line, sha = loader_line(SKILLS[0])
        self.assertEqual(line, LOADER + sha)

    def test_the_pinned_sha_is_the_runners_lf_sha256(self):
        for rel in SKILLS:
            self.assertEqual(loader_line(rel)[1], runner_sha(), rel)

    def test_every_pinned_sha_in_a_skill_is_the_same(self):
        for rel in SKILLS:
            shas = set(PINNED.findall(skill_text(rel)))
            self.assertEqual(shas, {runner_sha()}, rel)

    def test_no_skill_calls_the_conductor_directly(self):
        direct = re.compile(r"flow\.py\"?\s+<feature>\s+(next|prompt|verdict)\b")
        for rel in SKILLS:
            text = skill_text(rel)
            self.assertNotIn("scripts/flow.py <feature> next", text, rel)
            self.assertNotIn("flow.py <feature> next", text, rel)
            self.assertEqual(direct.findall(text), [], rel)


class LoaderRun(unittest.TestCase):
    """The extracted loader line, run through the platform shell the way the gate runs commands."""

    def setUp(self):
        self.repo = Repo()
        self.addCleanup(self.repo.close)
        self.runner = self.repo.path("scripts/flow-trust.py")
        shutil.copy(str(helpers.ROOT / "scripts" / "flow-trust.py"), str(self.runner))
        self.homes = {}
        for name in ("CLAUDE_HOME", "AGENTS_HOME", "FEATURE_FLOW_HOME"):
            folder = tempfile.TemporaryDirectory()
            self.addCleanup(folder.cleanup)
            self.homes[name] = folder.name
        self.repo.git("add", "-A")
        self.repo.git("commit", "-q", "--allow-empty", "-m", "layout")

    def run_loader(self, *args):
        line = loader_line(SKILLS[0])[0]
        self.assertTrue(line.startswith("python3 "))
        # the Windows CI job has `python`, not `python3`
        cmd = '"%s"' % sys.executable + line[len("python3"):]
        cmd = cmd.replace("<S>/flow-trust.py", '"%s"' % self.runner) + " " + " ".join(args)
        env = {k: v for k, v in os.environ.items() if not k.startswith("FLOW_")}
        env.update(self.homes)
        env["FLOW_TRUST"] = "new"
        argv, use_shell = gate.shell(cmd)
        return subprocess.run(argv, shell=use_shell, cwd=str(self.repo.dir), env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

    def assert_started(self, done):
        lines = done.stdout.splitlines()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertGreaterEqual(len(lines), 2, done.stdout + done.stderr)
        self.assertRegex(lines[0], TRUST)
        self.assertTrue(lines[1].startswith("OK "), done.stdout + done.stderr)

    def test_start_prints_trust_then_ok(self):
        self.assert_started(self.run_loader("f", "start"))

    def test_a_planted_hashlib_in_the_repo_root_is_ignored(self):
        self.repo.path("hashlib.py").write_text(
            "import sys\nsys.stdout.write('PLANTED\\n')\nsys.exit(3)\n", encoding="utf-8")
        done = self.run_loader("f", "start")
        self.assert_started(done)
        self.assertNotIn("PLANTED", done.stdout + done.stderr)

    def test_a_runner_with_one_byte_changed_does_not_match(self):
        data = self.runner.read_bytes()
        self.assertIn(b"trusted check", data)
        self.runner.write_bytes(data.replace(b"trusted check", b"trusted checK", 1))
        done = self.run_loader("f", "start")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn(MISMATCH, done.stderr)
        self.assertNotIn("TRUST", done.stdout)
        self.assertNotIn("OK ", done.stdout)

    def test_a_crlf_copy_of_the_runner_still_matches(self):
        data = self.runner.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        self.runner.write_bytes(data)
        self.assertIn(b"\r\n", self.runner.read_bytes())
        self.assert_started(self.run_loader("f", "start"))


if __name__ == "__main__":
    unittest.main()
