# Finish the conductor, the review verdict, the finish and the stops

Type: task
Status: open
Blocked by: 03
Test first: yes

Extend `scripts/flow.sh` with `bash scripts/flow.sh <feature> verdict <file>`. It takes the reviewer's reply, saved to a file by the session, and completes the review half of the policy, mirroring `review()` and `send_back` in `scripts/auto-flow.sh`.

`verdict` only works while a review is pending (the last thing `next` printed was REVIEW); otherwise it changes nothing and exits 2. It reads the last line of the file matching `^REVIEW: (PASS|FAIL)[[:space:]]*$`, prints `OK`, or `RETRY no review verdict` when there is none, and logs `VERDICT-PASS`, `VERDICT-FAIL` or `VERDICT-NONE`. Then `next` decides:

- PASS: the ticket is done. `next` prints the next `BUILD`, or a line starting with `DONE ` when `flow-status.sh --next` exits 10. Tickets left but none ready is `STOP stuck: ...` and exit 1.
- FAIL: append the first 120 lines of the file under `## Review findings (round N, independent review)`, reopen and commit like the gate send-back, print BUILD. The round counter is the one the gate and guard use.
- No verdict: REVIEW again; after `FLOW_MAX_RETRIES` tries, `STOP no review verdict for 01-a after 2 attempt(s)`.
- STOP when a tracked file changed during the review (`the reviewer changed tracked files, which a reviewer must never do`) and when builder plus reviewer runs pass `total * 2 * MAX_RETRIES * (MAX_ROUNDS + 1) + 1`.

## Not in this ticket

- `start`, `prompt` and `HANDOFF`: later tickets.
- The skill: later.

## Done when

- With a review pending, `verdict` on a file ending `REVIEW: PASS` prints `OK`; the next `next` prints `BUILD` for the next ticket, or on the last ticket a line starting `DONE ` with exit 0. The log has `VERDICT-PASS`.
- A file ending `REVIEW: FAIL` appends `## Review findings (round 1, independent review)` with the file's text and commits; after the 4th failure `next` prints `STOP 01-a still fails the independent review after 3 round(s)` and exits 1.
- Two files with no verdict line lead to `STOP no review verdict for 01-a after 2 attempt(s)`, exit 1.
- The reviewer-edit and run-limit STOPs print their messages and exit 1. `verdict` with no review pending exits 2 and leaves the state file and `git status` unchanged.
- `bash tests/run.sh` exits 0 with a check for every bullet in the `flow.sh` section.

## Reference

- spec.md § Interfaces, Edge cases
- scripts/auto-flow.sh (read only; `review`, `send_back`, `count_run`, the final loop)
- tests/run.sh (the `flow.sh` section)

## Answer
