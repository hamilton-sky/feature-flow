# Make flow state writable in a normal Codex session

Type: task
Status: open
Blocked by: —
Test first: yes

A normal interactive `codex -C <repo>` session can write the worktree but not
the repository's `.git` directory. Move the conductor's mutable state, flow
log and saved review reply to a persistent repo-local location that the normal
Codex workspace sandbox can write without making `git status --porcelain`
dirty. Install the ignore rule or runtime directory needed for that location.
Keep state shared across handoff sessions, and preserve the session-owner,
takeover and clean-tree guarantees.

Update the skills, guides, tests and documentation that name `.git/flow-*`.
If compatibility with an existing `.git/flow-*` run is possible without
weakening ownership, migrate or read it; otherwise stop with a clear recovery
message.

## Not in this ticket

- Re-running the paid Codex acceptance demo: ticket 13.
- Changing the builder/reviewer subagent mode chosen by ticket 02.

## Done when

- In a prepared demo, `codex -C <repo>` can run `$feature-flow hello` past
  `start` without permission to write `.git`.
- State and the review reply survive closing one Codex session and starting the
  next session from a `HANDOFF` line.
- The runtime files do not appear in `git status --porcelain`.
- Automated tests cover an unwritable `.git` directory, owner enforcement and
  handoff resumption, and `bash tests/run.sh` exits 0.

## Reference

- plans/interactive-flow/tasks/13-codex-hand-run.md (failed hand attempt)
- feature_flow/conductor.py (state and log paths)
- adapters/codex/feature-flow/SKILL.md (review reply and sandbox failure text)
- install.sh (installed runtime layout)

## Answer
