import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

sys.path.insert(0, str(helpers.ROOT))
from feature_flow import install  # the package under test, from this checkout


class TransformTests(unittest.TestCase):
    def test_codex_header_keeps_name_and_quotes_the_description(self):
        src = b'---\nname: q\ndescription: \t Says "hi" \\ there: ok \t\nargument-hint: "[a]"\n---\n\nbody\n'
        self.assertEqual(install.codex_header(src),
                         b'---\nname: q\ndescription: "Says \\"hi\\" \\\\ there: ok"\n---\n\nbody\n')

    def test_codex_header_adds_a_final_newline_and_keeps_a_body_without_header(self):
        self.assertEqual(install.codex_header(b"text\n---\nlast"), b"text\n---\nlast\n")
        self.assertEqual(install.codex_header(b""), b"")

    def test_codex_header_keeps_a_carriage_return(self):
        self.assertEqual(install.codex_header(b"---\r\nname: q\r\n"), b"---\r\nname: q\r\n")

    def test_role_body_drops_the_frontmatter_and_the_blank_lines_after_it(self):
        self.assertEqual(install.role_body(b"---\ntools: x\n---\n\n\nYou are.\n\nmore\n"), b"You are.\n\nmore\n")
        self.assertEqual(install.role_body(b"\nplain\n"), b"\nplain\n")

    def test_role_body_drops_the_frontmatter_of_a_windows_checkout_too(self):
        self.assertEqual(install.role_body(b"---\r\ntools: x\r\n---\r\n\r\nYou are.\r\nmore\r\n"),
                         b"You are.\r\nmore\r\n")


class RunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_install(self, *args):
        out, err = [], []
        code = install.run([str(self.target)] + list(args), helpers.ROOT, out.append, err.append)
        return code, "\n".join(out), "\n".join(err)

    def test_dry_run_writes_nothing_and_says_what_it_would_add(self):
        code, out, _ = self.run_install("--dry-run", "--agent", "all")
        self.assertEqual(code, 0)
        self.assertIn("dry run: nothing will be written", out)
        self.assertIn("would add ", out)
        self.assertEqual(list(self.target.iterdir()), [])

    def test_a_changed_file_is_kept_unless_forced(self):
        self.run_install()
        skill = self.target / ".claude" / "skills" / "feature-flow" / "SKILL.md"
        skill.write_bytes(skill.read_bytes() + b"my own edit\n")
        code, out, _ = self.run_install()
        self.assertEqual(code, 0)
        self.assertIn("  kept    %s/.claude/skills/feature-flow/SKILL.md (differs" % self.target, out)
        self.assertIn(b"my own edit", skill.read_bytes())
        _, out, _ = self.run_install("--force")
        self.assertIn("  update  ", out)
        self.assertNotIn(b"my own edit", skill.read_bytes())

    def test_the_installed_list_names_every_written_file_and_keeps_earlier_runs(self):
        self.run_install("--agent", "codex")
        listed = (self.target / ".feature-flow" / "installed.txt").read_text(encoding="utf-8").split()
        self.assertIn(".feature-flow/installed.txt", listed)
        self.assertIn(".agents/skills/feature-flow/SKILL.md", listed)
        self.assertIn("scripts/flow.py", listed)
        self.assertNotIn(".claude/skills/feature-flow/SKILL.md", listed)
        skill = self.target / ".agents" / "skills" / "feature-flow" / "SKILL.md"
        skill.write_bytes(skill.read_bytes() + b"my own edit\n")
        self.run_install("--agent", "claude")
        listed = (self.target / ".feature-flow" / "installed.txt").read_text(encoding="utf-8").split()
        self.assertIn(".claude/skills/feature-flow/SKILL.md", listed)
        self.assertIn(".agents/skills/feature-flow/SKILL.md", listed)
        files = sorted(p.relative_to(self.target).as_posix() for p in self.target.rglob("*") if p.is_file())
        self.assertEqual(sorted(listed), files)

    def test_an_upgrade_replaces_files_nobody_edited_and_keeps_edited_ones(self):
        self.run_install("--agent", "all")
        skill = self.target / ".agents" / "skills" / "feature-flow" / "SKILL.md"
        guide = self.target / ".feature-flow" / "guides" / "build.md"
        role = self.target / ".claude" / "agents" / "ticket-builder.md"
        # an earlier version wrote this skill and recorded its hash
        skill.write_bytes(b"skill from an earlier version\n")
        hashes = self.target / ".feature-flow" / "installed.sha256"
        lines = [l for l in hashes.read_text(encoding="utf-8").splitlines()
                 if not l.endswith("  .agents/skills/feature-flow/SKILL.md")]
        lines.append("%s  .agents/skills/feature-flow/SKILL.md" % install._sha256(b"skill from an earlier version\n"))
        hashes.write_text("\n".join(lines) + "\n", encoding="utf-8")
        # 0.1.1 kept no record: its files are known by the released hashes
        guide.write_bytes(b"guide from 0.1.1\n")
        role.write_bytes(role.read_bytes() + b"my own edit\n")
        released = install.RELEASED
        install.RELEASED = frozenset([install._sha256(b"guide from 0.1.1\n")])
        try:
            code, out, _ = self.run_install("--agent", "all")
        finally:
            install.RELEASED = released
        self.assertEqual(code, 0)
        self.assertIn("  update  %s/.agents/skills/feature-flow/SKILL.md" % self.target, out)
        self.assertNotIn(b"earlier version", skill.read_bytes())
        self.assertNotIn(b"0.1.1", guide.read_bytes())
        self.assertIn(b"my own edit", role.read_bytes())
        self.assertIn("kept    %s/.claude/agents/ticket-builder.md" % self.target, out)
        recorded = dict(reversed(l.split("  ", 1)) for l in hashes.read_text(encoding="utf-8").splitlines())
        self.assertEqual(recorded[".agents/skills/feature-flow/SKILL.md"], install._sha256(skill.read_bytes()))

    def user_env(self):
        home = Path(self.tmp.name) / "home"
        saved = dict((k, os.environ.get(k)) for k in ("HOME", "CLAUDE_HOME", "AGENTS_HOME", "FEATURE_FLOW_HOME"))
        os.environ["HOME"] = str(home)
        os.environ["CLAUDE_HOME"] = str(home / ".claude")
        os.environ["AGENTS_HOME"] = str(home / ".agents")
        os.environ["FEATURE_FLOW_HOME"] = str(home / ".feature-flow")

        def restore():
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        self.addCleanup(restore)
        return home

    def test_a_user_level_upgrade_replaces_a_skill_nobody_edited(self):
        home = self.user_env()
        self.run_install("--user")
        record = home / ".claude" / "feature-flow.sha256"
        skill = home / ".claude" / "skills" / "feature-flow" / "SKILL.md"
        self.assertIn("  skills/feature-flow/SKILL.md\n", record.read_text(encoding="utf-8"))
        skill.write_bytes(b"skill from an earlier version\n")
        record.write_text("%s  skills/feature-flow/SKILL.md\n" % install._sha256(skill.read_bytes()),
                          encoding="utf-8")
        _, out, _ = self.run_install("--user")
        self.assertIn("  update  %s/skills/feature-flow/SKILL.md" % (home / ".claude"), out)
        self.assertNotIn(b"earlier version", skill.read_bytes())
        self.assertFalse((self.target / ".feature-flow").exists())
        self.assertFalse((home / ".agents").exists())

    def test_a_user_install_puts_the_whole_flow_in_the_home_folder_and_nothing_in_the_repo(self):
        home = self.user_env()
        code, out, _ = self.run_install("--user", "--agent", "all")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines()[0], "installing into %s (all)" % (home / ".feature-flow"))
        flow = home / ".feature-flow"
        for name in ("scripts/flow.py", "guides/build.md", "agents/ticket-builder.md",
                     "feature_flow/__init__.py", "feature-flow.sha256"):
            self.assertTrue((flow / name).is_file(), name)
        self.assertFalse((flow / "feature_flow" / "_bundle").exists())
        self.assertEqual([p.name for p in self.target.iterdir()], ["home"])
        self.assertNotIn("next: commit the installed files", out)
        self.assertNotIn("not a git repository", out)
        _, again, _ = self.run_install("--user", "--agent", "all")
        self.assertIn("added 0, updated 0, already current", again)
        self.assertIn("kept 0", again)

    def test_a_user_install_keeps_an_edited_home_file_and_force_replaces_it(self):
        home = self.user_env()
        self.run_install("--user")
        guide = home / ".feature-flow" / "guides" / "build.md"
        original = guide.read_bytes()
        guide.write_bytes(original + b"my own edit\n")
        _, out, _ = self.run_install("--user")
        self.assertIn("kept    %s" % guide, out)
        self.assertIn(b"my own edit", guide.read_bytes())
        _, out, _ = self.run_install("--user", "--force")
        self.assertIn("update  %s" % guide, out)
        self.assertEqual(guide.read_bytes(), original)

    def test_a_user_install_updates_an_unedited_home_file_from_an_older_recorded_hash(self):
        home = self.user_env()
        self.run_install("--user")
        guide = home / ".feature-flow" / "guides" / "build.md"
        record = home / ".feature-flow" / "feature-flow.sha256"
        guide.write_bytes(b"guide from an earlier version\n")
        lines = [l for l in record.read_text(encoding="utf-8").splitlines() if not l.endswith("  guides/build.md")]
        lines.append("%s  guides/build.md" % install._sha256(guide.read_bytes()))
        record.write_text("\n".join(lines) + "\n", encoding="utf-8")
        _, out, _ = self.run_install("--user")
        self.assertIn("update  %s" % guide, out)
        self.assertNotIn(b"earlier version", guide.read_bytes())

    def test_a_user_codex_install_writes_no_roles_into_the_repo(self):
        home = self.user_env()
        self.run_install("--user", "--agent", "codex")
        self.assertFalse((self.target / ".agents").exists())
        self.assertTrue((home / ".feature-flow" / "agents" / "ticket-reviewer.md").is_file())

    @unittest.skipIf(sys.platform == "win32", "symlinks need extra rights on Windows")
    def test_an_upgrade_never_writes_through_a_symlink(self):
        self.run_install()
        skill = self.target / ".claude" / "skills" / "feature-flow" / "SKILL.md"
        shared = self.target / "shared-skill.md"
        shared.write_bytes(b"skill from 0.1.1\n")
        skill.unlink()
        skill.symlink_to(shared)
        released = install.RELEASED
        install.RELEASED = frozenset([install._sha256(b"skill from 0.1.1\n")])
        try:
            _, out, _ = self.run_install()
        finally:
            install.RELEASED = released
        self.assertIn("kept    %s/.claude/skills/feature-flow/SKILL.md" % self.target, out)
        self.assertEqual(shared.read_bytes(), b"skill from 0.1.1\n")

    def test_an_upgrade_never_writes_through_a_hard_link(self):
        self.run_install()
        skill = self.target / ".claude" / "skills" / "feature-flow" / "SKILL.md"
        shared = self.target / "shared-skill.md"
        shared.write_bytes(b"skill from 0.1.1\n")
        skill.unlink()
        os.link(str(shared), str(skill))
        released = install.RELEASED
        install.RELEASED = frozenset([install._sha256(b"skill from 0.1.1\n")])
        try:
            _, out, _ = self.run_install()
        finally:
            install.RELEASED = released
        self.assertIn("kept    %s/.claude/skills/feature-flow/SKILL.md" % self.target, out)
        self.assertEqual(shared.read_bytes(), b"skill from 0.1.1\n")

    def test_the_hash_record_is_never_written_through_a_link(self):
        self.run_install()
        record = self.target / ".feature-flow" / "installed.sha256"
        shared = self.target / "shared.sha256"
        shared.write_text("keep\n", encoding="utf-8")
        record.unlink()
        os.link(str(shared), str(record))
        self.run_install()
        self.assertEqual(shared.read_text(encoding="utf-8"), "keep\n")
        self.assertIn("  .claude/skills/feature-flow/SKILL.md", record.read_text(encoding="utf-8"))
        self.assertFalse((self.target / ".feature-flow" / "installed.sha256.tmp").exists())

    def git(self, *args):
        return helpers.subprocess.run(["git", "-C", str(self.target)] + list(args), check=True,
                                      stdout=helpers.subprocess.PIPE, universal_newlines=True).stdout

    def test_a_private_install_stays_out_of_git_and_keeps_the_users_excludes(self):
        self.git("init", "-q")
        exclude = self.target / ".git" / "info" / "exclude"
        exclude.write_text("mine.log\n", encoding="utf-8")
        _, out, _ = self.run_install("--private", "--agent", "all")
        self.assertIn("kept out of git: the install is listed in .git/info/exclude", out)
        self.assertNotIn("next: commit the installed files", out)
        self.assertEqual(self.git("status", "--porcelain"), "")
        lines = exclude.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[:2], ["mine.log", install.EXCLUDE_BEGIN])
        self.assertIn("/scripts/flow.py", lines)
        # a later install without the flag keeps it private and the block appears once
        (self.target / "scripts" / "flow.py").unlink()
        _, out, _ = self.run_install("--agent", "all")
        self.assertNotIn("next: commit the installed files", out)
        self.assertEqual(exclude.read_text(encoding="utf-8").splitlines(), lines)
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_a_private_install_over_a_committed_one_says_how_to_untrack_it(self):
        self.git("init", "-q")
        self.run_install()
        self.git("add", "--pathspec-from-file=.feature-flow/installed.txt")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "install")
        _, out, _ = self.run_install("--private")
        self.assertIn("note: git still tracks the install from before", out)
        self.git("rm", "-r", "-q", "--cached", "--ignore-unmatch", "--pathspec-from-file=.feature-flow/installed.txt")
        self.assertEqual(self.git("status", "--porcelain", "--untracked-files=all").splitlines(),
                         sorted("D  " + n for n in
                                (self.target / ".feature-flow" / "installed.txt").read_text(encoding="utf-8").split()))
        self.assertTrue((self.target / "scripts" / "flow.py").is_file())

    def test_an_install_into_a_git_repo_says_how_to_commit_it(self):
        helpers.subprocess.run(["git", "init", "-q", str(self.target)], check=True)
        _, out, _ = self.run_install()
        self.assertIn("next: commit the installed files: git -C ", out)
        self.assertIn(" add --pathspec-from-file=.feature-flow/installed.txt && git -C ", out)

    def test_the_python_commands_are_installed_and_no_bash_scripts(self):
        self.run_install()
        scripts = sorted(p.name for p in (self.target / "scripts").iterdir())
        self.assertEqual(scripts, ["floor-guard.py", "flow-status.py", "flow-view.html", "flow-view.py",
                                   "flow.py", "gate.py"])

    def test_an_old_skill_that_runs_the_ticket_script_is_named(self):
        for name, text in (("old-review", "End with `REVIEW: PASS`.\n"), ("old-py", "run python3 scripts/flow-status.py f\n"),
                           ("mine", "my own skill\n")):
            (self.target / ".claude" / "skills" / name).mkdir(parents=True)
            (self.target / ".claude" / "skills" / name / "SKILL.md").write_text(text, encoding="utf-8")
        _, out, _ = self.run_install()
        self.assertIn("no longer installed: old-py old-review.", out)
        self.assertNotIn("mine", out)

    @unittest.skipIf(os.name == "nt", "file modes are POSIX only")
    def test_a_generated_codex_file_is_mode_644(self):
        self.run_install("--agent", "codex")
        role = self.target / ".agents" / "flow-roles" / "ticket-builder.md"
        self.assertEqual(role.stat().st_mode & 0o777, 0o644)

    def test_usage_errors(self):
        for args in (["--nonsense"], ["--agent"], ["--agent", "nonsense"], ["--agent="]):
            code, _, err = self.run_install(*args)
            self.assertEqual(code, 2, args)
            self.assertTrue(err.startswith(("unknown", "--agent needs a value")), err)
        out, err = [], []
        self.assertEqual(install.run([str(self.target / "missing")], helpers.ROOT, out.append, err.append), 2)
        self.assertEqual(err, ["no such directory: %s" % (self.target / "missing")])
        self.assertEqual(install.run(["--help", "--nonsense"], helpers.ROOT, out.append, err.append), 0)
        self.assertTrue(out[0].startswith("usage: python3 install.py"))


if __name__ == "__main__":
    unittest.main()


class PackageTests(unittest.TestCase):
    """The installed package: the assets sit in feature_flow/_bundle/, which is never installed into a repo."""

    def test_the_source_root_of_a_checkout_is_the_checkout(self):
        self.assertEqual(Path(install.source_root()), helpers.ROOT)

    def test_an_installed_package_installs_from_its_bundle_and_leaves_the_bundle_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / "site" / "feature_flow"
            shutil.copytree(str(helpers.ROOT / "feature_flow"), str(package),
                            ignore=shutil.ignore_patterns("__pycache__"))
            bundle = package / install.BUNDLE
            for name in ("skills", "agents", "guides", "scripts"):
                shutil.copytree(str(helpers.ROOT / name), str(bundle / name))
            shutil.copytree(str(helpers.ROOT / "adapters"), str(bundle / "adapters"))
            target = Path(tmp) / "repo"
            target.mkdir()
            out = []
            installer = install.Installer(str(bundle), str(target), "all", False, False, False, out.append)
            installer.package = str(package)
            self.assertEqual(installer.run(), 0)
            self.assertTrue((target / ".feature-flow" / "feature_flow" / "conductor.py").is_file())
            self.assertTrue((target / ".claude" / "skills" / "feature-flow" / "SKILL.md").is_file())
            self.assertTrue((target / ".agents" / "skills" / "feature-flow" / "SKILL.md").is_file())
            self.assertFalse((target / ".feature-flow" / "feature_flow" / install.BUNDLE).exists())


class CommandTests(unittest.TestCase):
    def test_version_and_usage(self):
        from feature_flow import __version__, command
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(command.main(["--version"]), 0)
        self.assertEqual(out.getvalue().strip(), "feature-flow " + __version__)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(command.main(["nonsense"]), 2)
            self.assertEqual(command.main([]), 2)
        self.assertIn("unknown command: nonsense", err.getvalue())
        self.assertIn("usage: feature-flow install", err.getvalue())
