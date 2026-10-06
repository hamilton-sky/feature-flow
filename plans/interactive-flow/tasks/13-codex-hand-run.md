# Run the demo by hand in Codex and record what happened

Type: settle
Status: parked
Blocked by: 02, 14
Test first: no

Prepare the demo with `FLOW_AGENT=codex bash tests/smoke-real.sh --prepare DIR` and run `$feature-flow hello` in an interactive Codex session, in the mode ticket 02 chose, following every `HANDOFF` by starting a new session with the printed line. This is by hand because relay mode needs a person to start sessions. The user decides whether it costs too much to repeat.

Record in the Answer: how many sessions it took, whether both tickets resolved with `REVIEW: PASS`, the last 20 lines of `.git/flow-hello.log`, anything the skill said that confused the user, and the cost or tokens if Codex shows them. Put these lines in the Answer exactly:

```
Codex run finished: yes
Sessions used: <number>
```

## Not in this ticket

- Fixing what the run finds: a new ticket per problem. If the run does not finish, leave this ticket open, add an Attempt note and make each required fix a blocker of this ticket; do not record a resolved `no` result.

## Done when

- `grep -c '^Codex run finished: yes$' plans/interactive-flow/tasks/13-codex-hand-run.md` prints `1` and `grep -cE '^Sessions used: [0-9]+$' plans/interactive-flow/tasks/13-codex-hand-run.md` prints `1`.
- The Answer contains the log lines between two lines of three backticks.

## Reference

- adapters/codex/feature-flow/SKILL.md
- plans/interactive-flow/tasks/02-probe-codex-sessions.md

## Answer

## Attempt 2026-10-06

Prepared `/Users/shammaihamilton/ff-codex-run` with the requested command and
opened Codex 0.147.0 there. The installed `$feature-flow` skill was discovered
and ran its preflight, but its first conductor command failed before a session
token could be created:

```
FLOW_INVOKE='$feature-flow' python3 scripts/flow.py hello start
PermissionError: [Errno 1] Operation not permitted: '/Users/shammaihamilton/ff-codex-run/.git/flow-hello.state.tmp'
```

Codex then stopped with: `feature-flow cannot start because this session is not
permitted to write its state under .git. Please allow .git writes for this
workspace, then run: $feature-flow hello`.

No builder or reviewer session started, no `.git/flow-hello.log` was created,
and no `HANDOFF` line was printed, so there was no line with which to start the
requested new session. The checkout remained clean at its initial commit.
Ticket 14 is the required fix. The parent Codex session reported 16,953 total
tokens (16,208 input, 108,288 cached input, 745 output, 161 reasoning) on exit.

## Skipped 2026-10-06

Waived by the user: no Codex tokens are left for a hand run. The Codex skill
(`adapters/codex/feature-flow/`) stays installed, but its full run is
**unverified by hand**. What is checked: ticket 02's probe of `spawn_agent`/`wait_agent`
in the Codex desktop app, and ticket 14's automated test that the conductor runs
with `.git` unwritable. Not checked: a builder's `git commit` inside a normal
`codex -C` sandbox. The headless-removal ticket no longer waits on this one. Reopen it when
Codex tokens are available.
