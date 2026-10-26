import json
import re
import subprocess
import sys
import unittest

from helpers import ROOT

READ_ONLY = ("ticket-reviewer", "plan-reviewer", "flow-scout", "flow-architect", "flow-designer", "flow-po", "flow-skeptic")
WRITERS = ("ticket-builder", "feature-planner")


def hook_code(name):
    """The Python the agent's PreToolUse hook on Bash runs, or None when it has none."""
    text = (ROOT / "agents" / ("%s.md" % name)).read_text(encoding="utf-8")
    front = text.split("\n---\n", 1)[0]
    match = re.search(r"\n          command: \|-\n            python3 -I -c '\n(.*?)\n            '\n", front + "\n", re.S)
    if not match:
        return None
    return "\n".join(line[12:] for line in match.group(1).split("\n"))


def run(code, command):
    return subprocess.run([sys.executable, "-I", "-c", code], input=json.dumps({"tool_input": {"command": command}}),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)


class ReadOnlyHook(unittest.TestCase):
    def test_every_read_only_role_has_the_same_hook_and_no_write_tools(self):
        codes = set()
        for name in READ_ONLY:
            code = hook_code(name)
            self.assertIsNotNone(code, name)
            self.assertNotIn("'", code, name)  # it sits inside a single-quoted shell argument
            codes.add(code)
            front = (ROOT / "agents" / ("%s.md" % name)).read_text(encoding="utf-8").split("\n---\n", 1)[0]
            for tool in ("- Edit", "- Write", "- NotebookEdit"):
                self.assertNotIn(tool + "\n", front + "\n", name)
        self.assertEqual(len(codes), 1)
        for name in WRITERS:
            self.assertIsNone(hook_code(name), name)

    def test_the_hook_blocks_commands_that_change_files_or_the_repository(self):
        code = hook_code("ticket-reviewer")
        for command in ("git commit -m x", "git -C . add x", "cd a && git stash", "git --no-pager checkout -- .",
                        "git reset --hard", "npm test && git stash pop", "sed -i s/a/b/ f", "sed -n -i 's/a/b/' f",
                        "perl -pi -e 1 f", "echo x > f", "cat a >> b", "printf x &> f", "rm -rf x", "mv a b",
                        "x=1 rm f", "(cd d; touch f)", "echo $(rm f)", "ls | tee out", "ls | xargs rm",
                        "find . -name x -delete"):
            result = run(code, command)
            self.assertEqual(result.returncode, 2, command)
            self.assertIn("this role is read only", result.stderr)

    def test_the_hook_lets_read_only_and_check_commands_through(self):
        code = hook_code("ticket-reviewer")
        for command in ("git diff HEAD~1", "git log --format=%s -1", "git status --porcelain", "git grep reset",
                        "git show HEAD:x > /tmp/x", "git branch --show-current", "npm test 2>&1 | tail -5",
                        "python3 -m unittest discover -s tests/py", "ls > /dev/null", "cmd 2>/dev/null",
                        "grep -n \"a > b\" f", "grep -n 'rm -rf' f", "echo 'git commit'", "cat f | grep commit",
                        "node -e \"console.log(1>0)\""):
            result = run(code, command)
            self.assertEqual(result.returncode, 0, (command, result.stderr))


if __name__ == "__main__":
    unittest.main()
