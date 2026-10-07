# Prove a Test first ticket had a failing test before the code

Type: task
Status: open
Blocked by: 02
Test first: yes

Add `test_first(base, test_command, plan_dir, timeout, remember)` to `feature_flow/proof.py` and call it in `Conductor.judge_build` right after the Done when checks from ticket 02, only when `self.gate_on` and the ticket at base says `Test first: yes` (read the line from the same base text ticket 02 reads). The red run happens in place in the user's working copy (the user's decision, spec.md § Decisions); never in a temporary worktree.

- No Test command (`tickets.commands_value(self.commands, "Test")` empty) → log `TESTFIRST-SKIP`, note `the conductor did not check test first: commands.md has no Test command`.
- Candidates: commits from `git rev-list --reverse --first-parent <base>..HEAD` whose changed paths (`git diff-tree --no-commit-id --name-only -r <sha>`), leaving out paths under the plan folder, are non-empty and all match `floorguard.DELETED_TEST`. None → `send_back("test first", ...)` saying no commit between base and HEAD changes only test files, and that the failing test must be committed alone before the code. A rebuild after a send-back keeps the same base, so an earlier test-only commit still counts.
- For each candidate in order: `value` is the current branch (`git symbolic-ref -q --short HEAD`; it exits non-zero when HEAD is detached, then use `git rev-parse HEAD`); `remember(value)` saves it as `restore` in the run state before the switch; `git checkout -q --detach <sha>`, run Test from the repo's top folder (`git.toplevel()`), then in a `finally` `git checkout -q <value>` and `remember("")`.
  Run Test with `gate.shell`/`proc.run` and the timeout. A non-zero exit that is not a timeout proves red: log `TESTFIRST-PASS`, note `the conductor saw <short sha> fail the Test command before the code`.
- Every candidate passed or timed out → log `TESTFIRST-FAIL`, `send_back("test first", ...)` naming the commits and saying the test passes without the production change (or timed out).
- A failed switch or a failed way back → `Stop` naming the git error and what to undo by hand.

At the top of `Conductor.next` (after `check_owner`), if the state has `restore`, undo it (`git checkout -q <restore>`) and clear it before anything else, so a run killed mid-check resumes cleanly. Green at HEAD needs no run: the gate's Test already passed.

All tests go in `tests/py/test_proof.py`, so `-k proof` selects them.

## Not in this ticket

- Running only the new tests, or requiring the parent commit to be green: spec.md § Decisions and § Risks.
- The builder's instructions for making the test commit: ticket 06.

## Done when

- `python3 -m unittest discover -s tests/py -k proof` passes, including tests that: a `Test first: yes` ticket built in one commit (test and code together) is sent back with `## Review findings (round 1, test first)` and the log has `TESTFIRST-FAIL`; a ticket whose test-only commit already passes is sent back; a ticket with a failing test-only commit, then a code commit, reaches `REVIEW`, the log has `TESTFIRST-PASS`, and afterwards `git symbolic-ref --short HEAD` names the original branch and `git status --porcelain` prints nothing.
- `python3 -m unittest discover -s tests/py -k proof` passes, including tests that: a test-only commit whose Test command sleeps past a 0.02 minute timeout does not count as red and the ticket is sent back with a `test first` finding; a rebuild after a send-back, whose `base..HEAD` still holds the earlier failing test-only commit and adds only a code commit, reaches `REVIEW` with `TESTFIRST-PASS`.
- `python3 -m unittest discover -s tests/py -k proof` passes, including tests that: with `FLOW_GATE=off` a `Test first: yes` ticket built in one commit reaches `REVIEW` and the log has no `TESTFIRST-` line; a `Test first: no` ticket reaches `REVIEW` with no `TESTFIRST-` line; a plan without a `Test:` command reaches `REVIEW` with `TESTFIRST-SKIP` and `prompt` contains `did not check test first`.
- `python3 -m unittest discover -s tests/py -k proof` passes, including tests that: a run state with `restore` set (HEAD detached at the red commit, `restore` naming the branch) is put right by the next `next` before it prints anything else; a switch or way back that fails (the git call patched to raise) gives a single `STOP` line naming the git error.
- All existing tests still pass: `python3 -m unittest discover -s tests/py && bash tests/run.sh`.

## Reference

- spec.md § Design (Test first), § Decisions, § Edge cases
- map.md § Decisions so far (git commands, with sources)
- feature_flow/conductor.py (`judge_build`, `next`, `send_back`), feature_flow/floorguard.py (`DELETED_TEST`), feature_flow/git.py (`_git`), feature_flow/tickets.py (`commands_value`), feature_flow/proof.py

## Answer

