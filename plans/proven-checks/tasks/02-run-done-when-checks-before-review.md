# Run the Done when checks before REVIEW

Type: task
Status: resolved
Blocked by: 01
Test first: yes

Add `run_checks(checks, timeout)` to `feature_flow/proof.py`: run each check's command with `gate.shell` and `proc.run` (output to a temporary file, `timeout` in minutes), compare the exit code (`"nonzero"` means any non-zero) and every `prints` substring against the output (`\r\n` read as `\n`), run all of them, and return `(ok, report)`. The report names each failing command, what was wanted, what happened (exit code, or "timed out after N minutes"), and the last lines of its output via `gate.tail`. Use the parser from ticket 01.

Call it in `Conductor.judge_build`, after the floor guard passes and before `hand_out_review`, only when `self.gate_on`. Read the ticket text at the base commit as `flow_edit_allowed` does (`git show <base>:<ticket>`; fall back to the working copy cut at `## Answer` when that fails). Then:

- a `ParseError` → `Stop("<ticket> has a check block the conductor cannot read: <message>")`;
- no checks → log `DONEWHEN-SKIP` and add the note `the conductor ran no Done when checks: the ticket has no check block` for the reviewer;
- a failure → log `DONEWHEN-FAIL` and `send_back("done when", report)`;
- all pass → log `DONEWHEN-PASS` and add the note `the conductor ran N Done when check(s) and all passed`.

After the checks, if `git.changes()` is not empty, `Stop` naming the files (a check command must not change the tree). Rename the run-state key `guard_warning` to `review_notes` (one note per line; the floor guard's warning becomes one of them, cleared at each pick as today) and have `prompts.build` print each note as `The conductor notes: <note>` in the review task. Command lines run from the repo's top folder with `self.gate_timeout`.

All tests go in `tests/py/test_proof.py`, so `-k proof` selects them. They drive the conductor through `helpers.Repo` (a gate `Test:` and check commands built from `sys.executable` so they run under bash and cmd.exe; no skip decorators).

## Not in this ticket

- The test-first check: ticket 03.
- Splitting the review into two passes: ticket 04.
- Telling planners and builders about the block: ticket 06.

## Done when

- `python3 -m unittest discover -s tests/py -k proof` passes, including: a resolved ticket whose check exits 1 is sent back (the next line is `BUILD`, the ticket has `## Review findings (round 1, done when)` naming the command) and no `REVIEW` line was printed before it; the same ticket with a passing check gets `REVIEW` and the log has `DONEWHEN-PASS`; a ticket with no block gets `REVIEW`, the log has `DONEWHEN-SKIP`, and `prompt` contains `ran no Done when checks`.
- `python3 -m unittest discover -s tests/py -k proof` passes, including tests that: a check that sleeps past a 0.02 minute timeout (passed as the float argument to `run_checks`) is reported as timed out; a check block the parser rejects gives a single `STOP ... cannot read ...` line; a check that writes a file gives a `STOP` naming it.
- `python3 -m unittest discover -s tests/py -k proof` passes, including a test that with `FLOW_GATE=off` a ticket whose check would fail is not checked (no `DONEWHEN-` line in the log) and reaches `REVIEW`.
- All existing tests still pass: `python3 -m unittest discover -s tests/py && bash tests/run.sh` (the floor guard warning still reaches the reviewer).

## Reference

- spec.md § Design, § Edge cases, § Interfaces
- feature_flow/conductor.py (`judge_build`, `flow_edit_allowed`, `pick_ticket`, `prompt`), feature_flow/prompts.py (`build`), feature_flow/proc.py (`run`), feature_flow/gate.py (`shell`, `tail`), tests/py/helpers.py, tests/py/test_conductor.py (`GuardWarning`), tests/py/test_timeout.py

## Answer

Work started at 67c254e9eb96b2a1d4b12581c5e5e79f986d6014.

**Built**

- `feature_flow/proof.py`: `run_checks(checks, timeout)` returns `(ok, report)`; runs all checks through `gate.shell` and `proc.run`, output in a temp file, `\r\n` read as `\n`, report per failing command with wanted, got (exit code or "timed out after N minutes") and `gate.tail`.
- `feature_flow/conductor.py`: `ticket_at_base`, `run_done_when`, called from `judge_build` after the floor guard and only when `gate_on`; `review_notes` replaces `guard_warning`; `NOTE_SEP`.
- `feature_flow/prompts.py`: `build(..., notes=())` prints each as `The conductor notes: <note>` in the review task.
- `tests/py/test_proof.py`: 9 new tests (`RunChecks`, `Conducted`), written first and seen failing (`no attribute 'run_checks'`, no `DONEWHEN-` lines).
- `tests/py/test_conductor.py`: the `GuardWarning` assertions follow the mandated rename (`guard_warning` to `review_notes`, `The floor guard warns:` to `The conductor notes:`); same checks, new names.

**Proof**

- `python3 -m unittest discover -s tests/py -k proof`: `Ran 26 tests ... OK`. It covers the sent-back case (next line `BUILD`, `## Review findings (round 1, done when)` naming the command, no `REVIEW` in the log), the pass case (`REVIEW`, `DONEWHEN-PASS`), and the no-block case (`REVIEW`, `DONEWHEN-SKIP`, prompt has `ran no Done when checks`).
- Same command: timeout test (0.02 minutes, "timed out after 0.02 minutes"), the single-line `STOP ... cannot read ...`, and the check that writes a file giving a `STOP` naming it all pass.
- Same command: `FLOW_GATE=off` with a failing check reaches `REVIEW` with no `DONEWHEN-` line.
- `python3 -m unittest discover -s tests/py`: `Ran 195 tests ... OK`; `bash tests/run.sh`: `441 passed, 0 failed`, exit 0.

**Decisions**

- The state file keeps one line per key (`state.save` turns newlines into spaces), so `review_notes` is stored tab separated and split again in `prompt`; each note is its own line in the review task.
- The check-wrote-files `STOP` is checked before the DONEWHEN log line, so a dirty tree stops before any verdict is logged.
- The tree check runs only when the ticket has checks; commands run from the current directory, which the flow already requires to be the top folder.
- The Stop message uses the ticket's short name (`01-a`), like the other Stop messages.

**Shortcuts taken**

- Tab as the note separator: breaks if a note ever contains a tab (floor guard warnings and the conductor's notes do not). A list-valued state would be the upgrade.
- `flow_edit_allowed` was left alone, so the `git show <base>:<ticket>` call exists twice; folding them is a refactor the ticket did not ask for.

**For later tickets**

- 03 and 04 add their own notes: append to the `notes` list in `judge_build` (`notes.append(...)`), and keep the order floor warning, Done when, then later ones.
- `review_notes` is cleared at each pick. Ticket 04's `review_pass` handout can reuse it unchanged.

