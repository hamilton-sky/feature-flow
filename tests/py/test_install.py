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
