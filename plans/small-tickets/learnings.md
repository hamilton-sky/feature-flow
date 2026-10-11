# Learnings: small-tickets

Things a fresh worker would otherwise waste time rediscovering: a command that works, a
trap, a quirk of the environment. Append one or two lines, newest last, tagged with your
ticket number. Never edit or delete another line. Keep it short; a human prunes it.

- (01) `feature_flow.git._git` runs in the cwd: tests that call git helpers must `os.chdir` into the throwaway repo and back (see `tests/py/test_diff_size.py`).
- (03) Editing `scripts/flow-trust.py` means re-pinning its LF sha256 in four SKILL.md files: skills/, adapters/codex/, .claude/skills/, .agents/skills/ (sed the old hash).
