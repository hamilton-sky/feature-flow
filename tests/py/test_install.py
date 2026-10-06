import os
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

    def test_the_python_commands_are_installed_and_no_bash_scripts(self):
        self.run_install()
        scripts = sorted(p.name for p in (self.target / "scripts").iterdir())
        self.assertEqual(scripts, ["floor-guard.py", "flow-status.py", "flow-view.html", "flow-view.py",
                                   "flow.py", "gate.py"])

    def test_an_old_skill_that_runs_the_ticket_script_is_named(self):
        for name, text in (("old-review", "End with `REVIEW: PASS`.\n"), ("old-py", "run python3 scripts/flow-status.py f\n"),
                           ("mine", "my own skill\n")):
            (self.target / ".claude" / "skills" / name).mkdir(parents=True)
            (self.target / ".claude" / "skills" / name / "SKILL.md").write_text(text)
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
