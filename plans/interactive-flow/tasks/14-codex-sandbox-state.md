# Make flow state writable in a normal Codex session

Type: task
Status: resolved
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

The conductor's state, log and review findings now live in `.feature-flow/state/` at the
top of the worktree (`git rev-parse --show-toplevel`), as `flow-<feature>.state`, `.log` and
`.findings`. `state.state_dir` creates the folder on first use with its own `.gitignore`
holding `*`, so the folder ignores itself and `git status --porcelain` stays empty without
touching the user's `.gitignore` or `.git/info/exclude`. The installer needs no change: the
folder sits beside the installed `.feature-flow/{guides,agents,feature_flow}` and is made at
run time. Both skills save the reviewer's reply to `.feature-flow/state/flow-review-<feature>.txt`
(Claude no longer uses `${TMPDIR:-/tmp}`; Codex no longer uses `.git`, including the optional
`codex exec -o` path).

- Ownership: unchanged. The owner token, takeover and handoff live in the same state file.
- Old runs: when `.git/flow-<f>.state` exists and the new folder has none, the state, log and
  findings are copied over (state last, owner included), so the owning session keeps its
  token and a takeover still needs `FLOW_TAKEOVER=1`. The old files are only read, never
  written, so this works in the Codex sandbox too.
- Clear failure: if the folder cannot be written, every command prints
  `STOP cannot write the flow state in <path>: <reason>. this session must be allowed to write there`.
- The conductor's own commit of review findings (`send_back`) used to ignore a failed
  `git commit`. It now stops with `cannot commit the <source> findings to <ticket>`, instead of
  leaving a dirty tree for the next check to report as something else.

Proof: `tests/py/test_conductor.py` class `StateOutsideGit`. It runs every conductor call with
`.git` at mode 0555: start, a call without the token (STOP), BUILD, REVIEW, verdict from the new
reply path, HANDOFF with `FLOW_TICKETS_PER_SESSION=1`, then a new `start` without takeover and
BUILD of ticket 02. It ends with a clean `git status --porcelain` and no `flow-*` file under
`.git`. Other tests in the class cover a state folder that cannot be made (a file in its place) and
moving a run kept under `.git`. Run as a non-root user, the new tests fail on the old code and
pass on this one. Root ignores the 0555 mode, so as root the no-`flow-*`-under-`.git`
assertion is what holds the line. `bash tests/run.sh`: 517
passed, 0 failed (also checks that neither skill writes under `.git`).

Not checked here: a real `codex -C <repo>` session. The automated test stands in for the
sandbox's refusal of `.git`. The real run is ticket 13. A sandboxed builder still needs
`git commit`, which writes `.git`. Ticket 02's probe saw a child commit, but only in the
Codex desktop app; ticket 13 will show whether a normal CLI session asks to approve it.
