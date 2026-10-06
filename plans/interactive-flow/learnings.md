# Learnings: interactive-flow

Things a fresh worker would otherwise waste time rediscovering: a command that works, a
trap, a quirk of the environment. Append one or two lines, newest last, tagged with your
ticket number. Never edit or delete another line. Keep it short; a human prunes it.

- (NN) <what you found, and what to do about it>
- (01) A subagent's session-start git status is frozen, so tell prompts to run `git log` and `git status` themselves. `git show '<rev>:path/*'` does not glob and exits 0 with the HEAD commit and the ticket's Answer hunk; resolve the path with `git ls-files` first.
- (12) An unattended `claude -p` session cannot write under `.git`: Bash `cat > .git/x` is refused as a sensitive file, and a command chaining it with other commands is refused as "multiple operations". Write replies to `${TMPDIR:-/tmp}` and keep one command per Bash call. Codex's sandbox blocks `.git` even for the conductor's own state (ticket 14).
- (14) Keep runtime files out of `.git` and out of `git status`: a folder whose own `.gitignore` is `*` ignores itself, so no user file has to change.
