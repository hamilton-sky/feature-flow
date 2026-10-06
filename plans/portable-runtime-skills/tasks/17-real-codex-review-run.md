# Prove the new Codex review path with one real run

Type: task
Status: open
Blocked by: 08, 09
Test first: no

**Manual ticket.** If you were started with `auto` (the unattended loop), stop now: leave `Status: open`, add an `## Attempt note` that says this ticket spends money and is worked by hand, and exit. Do not run anything below.

Tickets 07 and 08 change real Codex behavior (structured output, a writable sandbox in a worktree) that the offline suite proves only against a fake. Run `RUN_REAL=1 FLOW_AGENT=codex bash tests/smoke-real.sh` once, by hand, with the preflight, structured review (if the CLI supports it), worktree review and commit safety all on. Paste its full output into the Answer between two lines of three backticks. The reviewer checks the pasted output and must not run the paid command again.

Then update the "Codex, unattended loop" row of the README's "What is tested" table with the real numbers (tickets, sessions, tokens, checks) and say which review mode ran.

## Not in this ticket

- Fixing problems the real run finds. If it fails, set the ticket back to open, write an Attempt note and open a new ticket for the fix.

## Done when

- The Answer contains the pasted output of one real run: `grep -c '^  ok ' plans/portable-runtime-skills/tasks/17-real-codex-review-run.md` prints at least `11` and `grep -c '^  FAIL' plans/portable-runtime-skills/tasks/17-real-codex-review-run.md` prints `0`.
- The pasted output shows the preflight passing, the review running in a worktree, and the review mode.
- The README's Codex row names the review mode and the numbers from this run.

## Reference

- `tests/smoke-real.sh`
- `references.md`, the "Codex CLI" entry
- README.md, the "What is tested" table

## Answer
