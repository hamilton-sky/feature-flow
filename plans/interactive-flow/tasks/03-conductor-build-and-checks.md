# Build the conductor, the build and check phases

Type: task
Status: open
Blocked by: —
Test first: yes

Add `scripts/flow.sh`, a bash 3.2 script (no associative arrays, no mapfile, no empty array expansion under `set -u`; it must work with mawk, gawk and BSD awk). It owns the order of phases for a session that drives the flow. This ticket covers `next` up to asking for a review.

Usage: `bash scripts/flow.sh <feature> next`. It reads `plans/<feature>` (honouring `FLOW_DIR` and `FLOW_TICKETS`), calls `scripts/flow-status.sh`, `scripts/gate.sh` and `scripts/floor-guard.sh`, and keeps its state in `.git/flow-<feature>.state` as key=value lines: ticket, base sha, phase, attempt, round (one counter shared by gate, floor guard and review), runs so far. It appends `HH:MM:SS,<NN>,<EVENT>` to `.git/flow-<feature>.log` for every line it prints and for each check it runs (`GATE-PASS`, `GATE-FAIL`, `GUARD-PASS`, `GUARD-FAIL`). Both files live under `.git`, so the tree stays clean. It prints exactly one line:

- `BUILD <ticket-path> <NN> <base-sha>` when a builder must run. `<base-sha>` is `git rev-parse HEAD` when the ticket is first handed out.
- `REVIEW <ticket-path> <NN> <base-sha>` after the ticket is resolved, the tree is clean, and the gate and the floor guard both passed. The script runs them; the session never does.
- `STOP <reason>` and exit 1 on a problem.

Judge from the repo, never from the caller. After a BUILD, the next `next` reads the ticket's Status (`resolved`, `done`, `closed` are done; `claimed` and `in-progress` are reset to `open`) and `git status`. A resolved ticket with a dirty tree is `STOP working tree is dirty after <name>, it should have been committed`. Run the smoke command before the first BUILD of each ticket. A failing gate or floor guard appends its output to the ticket as `## Review findings (round N, gate)` or `(round N, floor guard)`, sets the ticket open, commits `chore(<feature>): NN review findings, round N`, and prints BUILD again. STOP comes on the failure after `FLOW_MAX_REVIEW_ROUNDS` send-backs, as in `auto-flow.sh`.

`scripts/auto-flow.sh` is the reference for names, limits and messages (`implement`, `send_back`, `ticket_state`, `set_open`, `smoke_command`). Copy its policy; do not change it. It is deleted later in this plan, so `flow.sh` must not call it or source it.

## Not in this ticket

- The reviewer's verdict, `DONE`, and the reviewer-edit and run-limit stops: ticket 04.
- `start`, `prompt` and `HANDOFF`: later tickets.

## Done when

- On a fresh plan in a temp repo, `bash scripts/flow.sh f next` prints exactly `BUILD plans/f/tasks/01-a.md 01 <sha>` with `<sha>` equal to `git rev-parse HEAD`, exits 0, creates `.git/flow-f.state`, appends a `BUILD` line to `.git/flow-f.log`, and leaves `git status --porcelain` empty.
- After the ticket is set to `resolved` and committed, `next` prints `REVIEW plans/f/tasks/01-a.md 01 <the same sha>` and the log has `GATE-PASS` and `GUARD-PASS` lines.
- A ticket still `claimed` is reset to `open` and BUILD is printed again; after `FLOW_MAX_RETRIES` attempts `next` prints `STOP 01-a is still unresolved after 2 attempt(s)` and exits 1.
- A failing `Test:` in commands.md appends `## Review findings (round 1, gate)`, commits `chore(f): 01 review findings, round 1`, and prints BUILD; on the 4th failure `next` prints `STOP 01-a still fails the gate after 3 round(s)` and exits 1. A resolved ticket with an uncommitted file prints the dirty-tree STOP.
- `bash tests/run.sh` exits 0 and has a `flow.sh` section with a check for each bullet above.

## Reference

- spec.md § Interfaces, Edge cases
- scripts/auto-flow.sh (read only)
- scripts/flow-status.sh, scripts/gate.sh, scripts/floor-guard.sh (read only)
- tests/run.sh (the `newrepo` and `flow` helpers)
- plans/in-session-mode/tasks/02-conductor-build-and-checks.md (the earlier version)

## Answer
