# Build the conductor script, the build and check phases

Type: task
Status: open
Blocked by: 01
Test first: yes

Add `scripts/flow-step.sh`, a bash 3.2 script (no associative arrays, no mapfile, no empty array expansion under `set -u`; it must work with mawk, gawk and BSD awk). It owns the order of phases for a session that drives the flow itself. This ticket covers everything up to asking for a review. The review half is the next ticket.

Usage: `bash scripts/flow-step.sh <feature> next`. It reads `plans/<feature>` (honouring `FLOW_DIR` and `FLOW_TICKETS` like the other scripts), calls `scripts/flow-status.sh`, `scripts/gate.sh` and `scripts/floor-guard.sh`, and keeps its state in `.git/flow-step-<feature>.state` as key=value lines: the ticket, the base sha, the phase, the attempt, the review round and the number of runs so far. It also appends one line `HH:MM:SS,<NN>,<EVENT>` to `.git/flow-step-<feature>.log` for every line it prints. Both files live under `.git`, so the tree stays clean. It prints exactly one line:

- `BUILD <ticket-path> <NN> <base-sha>` when a builder must run. `<base-sha>` is `git rev-parse HEAD`, taken when the ticket is first handed out.
- `REVIEW <ticket-path> <NN> <base-sha>` after the ticket is resolved, the tree is clean, and the gate and the floor guard have both passed. The script runs them itself. The session never does.
- On a problem, `STOP <reason>` on stdout and exit 1, with the same wording `auto-flow.sh` uses.

Judge from the repo, never from the caller. After a `BUILD`, the next `next` looks at the ticket file, using the same state words as `auto-flow.sh` (`resolved`, `done` and `closed` count as done; `claimed` and `in-progress` are reset to `open`), and at `git status`. Take the limits from the same variables as `auto-flow.sh` (`FLOW_MAX_RETRIES` 2, `FLOW_MAX_REVIEW_ROUNDS` 3, `FLOW_GATE`, `FLOW_SMOKE`) and run the smoke command before the first BUILD of each ticket. A failing gate or floor guard writes its output into the ticket as `## Review findings (round N, gate)` or `(round N, floor guard)`, sets the ticket open, commits `chore(<feature>): NN review findings, round N` as `send_back` does in `auto-flow.sh`, and prints BUILD again.

Read `scripts/auto-flow.sh` first. This is the same policy written as a state machine, and its names and messages are the reference. Do not change it.

## Not in this ticket

- The reviewer's verdict, `verdict FILE`, the finish (`DONE`) and the dirty tree and run limit stops: ticket 03.
- The skill that calls this script: ticket 04.
- Any change to `scripts/auto-flow.sh`.

## Done when

- On a fresh plan in a temp repo, `bash scripts/flow-step.sh f next` prints exactly `BUILD plans/f/tasks/01-a.md 01 <sha>` where `<sha>` equals `git rev-parse HEAD`, exits 0, creates `.git/flow-step-f.state`, appends a `BUILD` line to `.git/flow-step-f.log`, and leaves `git status --porcelain` empty.
- After the ticket is set to `resolved` and committed, `next` runs the gate and the floor guard itself and prints `REVIEW plans/f/tasks/01-a.md 01 <the same sha>`.
- If the ticket is still `claimed` the next time, it is reset to `open` and BUILD is printed again. After `FLOW_MAX_RETRIES` attempts `next` prints `STOP 01-a is still unresolved after 2 attempt(s)` and exits 1.
- A failing `Test:` in commands.md, or a floor guard violation, appends `## Review findings (round 1, gate)` (or `floor guard`) to the ticket, commits `chore(f): 01 review findings, round 1`, and prints BUILD again. After `FLOW_MAX_REVIEW_ROUNDS` rounds `next` prints `STOP 01-a still fails the gate after 3 round(s)` and exits 1.
- `bash tests/run.sh` exits 0, and its output has a `flow-step.sh` section with a check for each bullet above.

## Reference

- spec.md § Interfaces, Edge cases
- scripts/auto-flow.sh (read only; `implement`, `send_back`, `ticket_state`, `set_open`, `smoke_command`)
- scripts/flow-status.sh, scripts/gate.sh, scripts/floor-guard.sh (read only)
- tests/run.sh (the `newrepo` and `flow` helpers; add a section after the `auto-flow.sh` ones)

## Answer

