# Finish the conductor, the review verdict, the finish and the stops

Type: task
Status: resolved
Blocked by: 03
Test first: yes

Extend `scripts/flow.py` with `python3 scripts/flow.py <feature> verdict <file>`. It takes the reviewer's reply, saved to a file by the session, and completes the review half of the policy, mirroring `review()` and `send_back` in `scripts/auto-flow.sh`.

`verdict` only works while a review is pending (the last thing `next` printed was REVIEW); otherwise it changes nothing and exits 2. It reads the last line of the file matching `^REVIEW: (PASS|FAIL)[[:space:]]*$`, prints `OK`, or `RETRY no review verdict` when there is none, and logs `VERDICT-PASS`, `VERDICT-FAIL` or `VERDICT-NONE`. Then `next` decides:

- PASS: the ticket is done. `next` prints the next `BUILD`, or a line starting with `DONE ` when `flow-status.sh --next` exits 10. Tickets left but none ready is `STOP stuck: ...` and exit 1.
- FAIL: append the first 120 lines of the file under `## Review findings (round N, independent review)`, reopen and commit like the gate send-back, print BUILD. The round counter is the one the gate and guard use.
- No verdict: REVIEW again; after `FLOW_MAX_RETRIES` tries, `STOP no review verdict for 01-a after 2 attempt(s)`.
- STOP when the worktree or index is dirty, or when `HEAD` differs from the review sha saved when REVIEW was emitted (`the reviewer changed tracked files, which a reviewer must never do`). This catches a reviewer commit as well as an uncommitted edit. Also STOP when builder plus reviewer runs pass `total * 2 * MAX_RETRIES * (MAX_ROUNDS + 1) + 1`.

## Not in this ticket

- `start`, `prompt` and `HANDOFF`: later tickets.
- The skill: later.

## Done when

- With a review pending, `verdict` on a file ending `REVIEW: PASS` prints `OK`; the next `next` prints `BUILD` for the next ticket, or on the last ticket a line starting `DONE ` with exit 0. The log has `VERDICT-PASS`.
- A file ending `REVIEW: FAIL` appends `## Review findings (round 1, independent review)` with the file's text and commits; after the 4th failure `next` prints `STOP 01-a still fails the independent review after 3 round(s)` and exits 1.
- Two files with no verdict line lead to `STOP no review verdict for 01-a after 2 attempt(s)`, exit 1.
- The reviewer-edit STOP is covered twice: once for an uncommitted tracked edit and once for a reviewer-created commit that leaves the tree clean. Both print the message and exit 1. The run-limit STOP does the same. `verdict` with no review pending exits 2 and leaves the state file, `HEAD` and `git status` unchanged.
- `bash tests/run.sh` exits 0 with a check for every bullet in the `flow.py` section.

## Reference

- spec.md § Interfaces, Edge cases
- scripts/auto-flow.sh (read only; `review`, `send_back`, `count_run`, the final loop)
- tests/run.sh (the `flow.py` section)

## Answer

Built: `python3 scripts/flow.py <feature> verdict <file>` and the review half of `next` in `feature_flow/conductor.py` (`verdict`, `judge_review`), plus the `verdict` command in `cli.py`. `verdict` reads the last line matching `^REVIEW: (PASS|FAIL)\s*$`, records `pass`, `fail` or `none` in the state, logs `VERDICT-PASS`, `VERDICT-FAIL` or `VERDICT-NONE`, and prints `OK` or `RETRY no review verdict`. With no review pending it prints the reason on stderr and exits 2 without changing anything. A FAIL saves the first 120 lines to `.git/flow-<f>.findings`. The next `next` appends them under `## Review findings (round N, independent review)`, using the same round counter and commit message as the gate send-back.

Proven: `bash tests/run.sh` 464 passed, 0 failed. Its `flow.py, review verdict and finish` section has a check for each Done when: PASS leads to the next BUILD and then DONE, FAIL rounds stop on the 4th failure, two replies with no verdict stop, an uncommitted edit stops, a reviewer commit stops, the run limit stops, and `verdict` with no review pending exits 2 and leaves state, HEAD and status unchanged. `git status --porcelain` was empty afterwards.

For later tickets:
- `next` checks the reviewer before it reads the verdict. Any tracked change (worktree or index), or a HEAD that differs from `review_sha`, is a STOP. Untracked files don't count here, but after a PASS, `next` requires a fully clean tree before it hands out the next ticket. The session must therefore save the reviewer's reply outside the tree. Ticket 01 checks whether `.git/flow-review-<feature>.txt` works.
- A verdict is used once: `next` clears it. A REVIEW handed out again with no new `verdict` call counts as a reply with no verdict.
- DONE reads `DONE <feature> is complete: N ticket(s) resolved in this run`.
