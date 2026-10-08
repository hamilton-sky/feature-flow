import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import command, install, uninstall


class UninstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name) / "repo"
        self.target.mkdir()
        subprocess.run(["git", "init", "-q", str(self.target)], check=True)
        self.home = Path(self.tmp.name) / "home"
        self.saved = dict((k, os.environ.get(k)) for k in ("HOME", "CLAUDE_HOME", "AGENTS_HOME"))
        os.environ["HOME"] = str(self.home)
        os.environ["CLAUDE_HOME"] = str(self.home / ".claude")
        os.environ["AGENTS_HOME"] = str(self.home / ".agents")

    def tearDown(self):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def install(self, *args):
        out, err = [], []
        self.assertEqual(install.run([str(self.target)] + list(args), helpers.ROOT, out.append, err.append), 0, err)
        return "\n".join(out)

    def uninstall(self, *args):
        out, err = [], []
        code = uninstall.run(list(args), out.append, err.append)
        return code, "\n".join(out), "\n".join(err)

    def files(self, root=None):
        root = root or self.target
        return sorted(p.relative_to(root).as_posix() for p in Path(root).rglob("*")
                      if p.is_file() and ".git/" not in p.as_posix())

    def test_it_removes_what_the_install_wrote_and_nothing_else(self):
        (self.target / "plans" / "x").mkdir(parents=True)
        (self.target / "plans" / "x" / "spec.md").write_text("mine\n")
        (self.target / "scripts").mkdir()
        (self.target / "scripts" / "mine.sh").write_text("echo mine\n")
        self.install("--agent", "all")
        code, out, _ = self.uninstall(str(self.target))
        self.assertEqual(code, 0)
        self.assertIn("removed ", out)
        self.assertEqual(self.files(), ["plans/x/spec.md", "scripts/mine.sh"])
        self.assertFalse((self.target / ".claude").exists())
        self.assertFalse((self.target / ".agents").exists())
        self.assertFalse((self.target / ".feature-flow").exists())

    def test_an_edited_file_is_kept_and_named_unless_forced(self):
        self.install()
        skill = self.target / ".claude" / "skills" / "feature-flow" / "SKILL.md"
        skill.write_bytes(skill.read_bytes() + b"my own edit\n")
        code, out, _ = self.uninstall(str(self.target))
        self.assertEqual(code, 0)
        self.assertIn("kept    %s (edited" % skill, out)
        self.assertEqual(self.files(), [".claude/skills/feature-flow/SKILL.md", ".feature-flow/installed.sha256",
                                        ".feature-flow/installed.txt"])
        code, out, _ = self.uninstall(str(self.target), "--force")
        self.assertEqual(self.files(), [])

    def test_dry_run_removes_nothing(self):
        self.install()
        before = self.files()
        code, out, _ = self.uninstall(str(self.target), "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("dry run: nothing will be removed", out)
        self.assertIn("would remove ", out)
        self.assertEqual(self.files(), before)

    def test_a_private_install_loses_its_exclude_block_and_keeps_the_users_lines(self):
        exclude = self.target / ".git" / "info" / "exclude"
        exclude.parent.mkdir(exist_ok=True)
        exclude.write_text("*.log\n")
        self.install("--private")
        self.assertIn(install.EXCLUDE_BEGIN, exclude.read_text())
        self.uninstall(str(self.target))
        self.assertEqual(exclude.read_text(), "*.log\n")

    def test_a_partial_uninstall_still_unlists_the_private_block(self):
        exclude = self.target / ".git" / "info" / "exclude"
        exclude.parent.mkdir(exist_ok=True)
        self.install("--private")
        skill = self.target / ".claude" / "skills" / "feature-flow" / "SKILL.md"
        skill.write_bytes(skill.read_bytes() + b"my own edit\n")
        self.uninstall(str(self.target))
        self.assertNotIn(install.EXCLUDE_BEGIN, exclude.read_text())

    def test_bytecode_of_the_users_own_scripts_is_left_alone(self):
        self.install()
        cache = self.target / "scripts" / "__pycache__"
        cache.mkdir()
        (cache / "mine.pyc").write_bytes(b"\0")
        self.uninstall(str(self.target))
        self.assertTrue((cache / "mine.pyc").is_file())

    def test_run_state_is_left_alone(self):
        self.install()
        state = self.target / ".feature-flow" / "state"
        state.mkdir()
        (state / "log").write_text("run\n")
        _, out, _ = self.uninstall(str(self.target))
        self.assertTrue((state / "log").is_file())
        self.assertIn("left alone", out)

    def test_bytecode_does_not_keep_a_folder_alive(self):
        self.install()
        cache = self.target / ".feature-flow" / "feature_flow" / "__pycache__"
        cache.mkdir()
        (cache / "x.pyc").write_bytes(b"\0")
        self.uninstall(str(self.target))
        self.assertFalse((self.target / ".feature-flow").exists())

    def test_no_install_is_reported(self):
        code, out, _ = self.uninstall(str(self.target))
        self.assertEqual(code, 1)
        self.assertIn("no feature-flow install found", out)

    def test_a_listed_path_that_climbs_out_is_skipped(self):
        self.install()
        victim = Path(self.tmp.name) / "victim.txt"
        victim.write_text("keep\n")
        listed = self.target / ".feature-flow" / "installed.txt"
        listed.write_text(listed.read_text() + "../victim.txt\n")
        self.uninstall(str(self.target), "--force")
        self.assertTrue(victim.is_file())

    def test_user_removes_the_home_install_and_leaves_the_repo(self):
        self.install("--user", "--agent", "all")
        self.assertTrue((self.home / ".claude" / "skills" / "feature-flow" / "SKILL.md").is_file())
        in_repo = self.files()
        code, out, _ = self.uninstall("--user")
        self.assertEqual(code, 0)
        self.assertEqual(self.files(self.home), [])
        self.assertEqual(self.files(), in_repo)

    def test_user_without_a_personal_install_says_so(self):
        code, out, _ = self.uninstall("--user")
        self.assertEqual(code, 1)
        self.assertIn("no personal feature-flow install found", out)

    def test_the_command_has_an_uninstall_and_help(self):
        self.assertIn("uninstall", command.COMMANDS)
        code, out, _ = self.uninstall("--help")
        self.assertEqual(code, 0)
        self.assertIn("--user", out)
        code, _, err = self.uninstall("--bogus")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
