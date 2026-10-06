# Learnings: interactive-flow

Things a fresh worker would otherwise waste time rediscovering: a command that works, a
trap, a quirk of the environment. Append one or two lines, newest last, tagged with your
ticket number. Never edit or delete another line. Keep it short; a human prunes it.

- (NN) <what you found, and what to do about it>
- (01) A subagent's session-start git status is frozen, so tell prompts to run `git log` and `git status` themselves. `git show '<rev>:path/*'` does not glob and exits 0 with the HEAD commit and the ticket's Answer hunk; resolve the path with `git ls-files` first.
