# Add the size ratchet and prove the bar end to end

Type: task
Status: resolved
Blocked by: 13, 16
Test first: no
Level: 3
Touches: tests/py/test_conductor_package.py

Step 10 of the design, and the acceptance ticket. Add the ratchet to `tests/py/test_conductor_package.py` (new in ticket 03): a test method named `test_ratchet` checks that `feature_flow/conductor/facade.py` (new in ticket 03 too) is under 300 lines and every other `.py` file under `feature_flow/conductor/` is under 400, each failure naming the file and its count. `Test first: no`: ticket 16 already brought the sizes down, so the test cannot fail before it is written.

Then run the bar of map.md and the acceptance tests (spec.md § Acceptance tests, A1 to A4, which the tester wrote before ticket 01; A3 proves a run paused at a `HANDOFF` on the old code resumes on the new; A4 that a run paused mid-ticket meets today's `check_code` STOP), and record in the Answer: each check's last line, and `git log --oneline -- tests/py/golden`, which must list only ticket 01's commits. If anything fails, do not fix it here: record it in the Answer. The conductor's end-of-run acceptance run turns acceptance failures into fix tickets.

## Not in this ticket

- Any code change under `feature_flow/`: the tickets before this one.
- `tests/py/golden/` and `plans/conductor-rebuild/acceptance/`: never changed by a builder.

## Done when

- `python3 -m unittest discover -s tests/py -p "test_conductor_package.py" -v` lists `test_ratchet` and prints `OK`.
- `python3 -c "import feature_flow.conductor as c; print(c.Conductor, c.Stop, c.NoPhase)"` prints the three classes, and `feature_flow/conductor.py` does not exist.
- `python3 -m unittest discover -s plans/conductor-rebuild/acceptance -v` has been run, and the Answer records its last line, that A3 (a run paused at a `HANDOFF` on the old code resumes on the new) and A4 (a run paused mid-ticket meets today's `check_code` STOP) pass, and each failing test with its cause. The failures themselves are not this ticket's to fix: once every ticket is resolved the conductor runs the acceptance tests and turns any failure into a fix ticket, where the product owner rules on a test that disagrees with spec.md.
- `bash tests/run.sh` prints `0 failed` and exits 0.
- The Answer shows `git log --oneline -- tests/py/golden` listing only ticket 01's commits.

```check
# The conductor runs this block before review.
$ python3 -m unittest discover -s tests/py -p "test_conductor_package.py" -v
prints test_ratchet
prints OK
$ python3 -c "import feature_flow.conductor as c; print(c.Conductor, c.Stop, c.NoPhase)"
prints NoPhase
$ python3 -c "import os,sys; gone = not os.path.exists('feature_flow/conductor.py'); print('conductor.py gone:', gone); sys.exit(0 if gone else 1)"
prints conductor.py gone: True
$ bash tests/run.sh
prints , 0 failed
```

## Reference

- map.md § Destination (the bar), spec.md § Goal and the bar, § Acceptance tests, § Edge cases (a run paused on the old code)
- `tests/py/test_conductor_package.py` and `tests/py/test_golden.py` (new in tickets 03 and 01)

## Answer

**Built**: `tests/py/test_conductor_package.py` `test_ratchet` (one `subTest` per `.py` under `feature_flow/conductor/`, skipping `__pycache__`; `facade.py` under 300, every other file under 400; the message is `<path> has N lines, the limit is under L`). It was written and committed in 6c14287 by the last attempt. This build made no code change. It reran every check at e7cb19c, after the plan owner changed the acceptance bullet, and recorded the results.

**Proof** (all run fresh in this build):
- `python3 -m unittest discover -s tests/py -p "test_conductor_package.py" -v`: `test_ratchet ... ok`, `Ran 6 tests`, `OK`, exit 0. facade.py has 296 lines.
- `python3 -c "import feature_flow.conductor as c; print(c.Conductor, c.Stop, c.NoPhase)"`: `<class 'feature_flow.conductor.facade.Conductor'> <class 'feature_flow.conductor.errors.Stop'> <class 'feature_flow.conductor.errors.NoPhase'>`, exit 0. The check block's gone command prints `conductor.py gone: True`, exit 0.
- `python3 -m unittest discover -s plans/conductor-rebuild/acceptance -v`: last line `FAILED (failures=13)` (`Ran 48 tests`), exit 1. A3 `test_a3_a_run_paused_at_a_handoff_on_the_old_code_goes_on_with_the_new_code ... ok` and A4 `test_a4_a_run_paused_mid_ticket_meets_the_flow_code_changed_stop ... ok`. All 13 failures are `support.twins` `Lists differ`. Every differing line is in the state's `code_files`. They match the failures the Attempt note below lists:
  - Package file names in `code_files` (`feature_flow/conductor/__init__.py`, ... where the old code had `feature_flow/conductor.py`). This is the file move itself, so the flow code cannot remove it. 11 tests have it: test_rebuild_lanes `test_a_lane_run_leases_merges_and_finishes_as_today`; test_rebuild_modes `test_other_commands_ignore_a_bad_flow_lanes`, `test_patching_check_code_on_the_class_turns_the_code_check_off`, `test_batch_preconditions`; test_rebuild_user `test_state_log_findings_ticket_sections_and_followups_are_the_same`, `test_the_17_commands_print_the_same_lines_with_the_same_exit_codes`, `test_a_batch_is_judged_as_today`, `test_a_fast_run_defers_reviews_to_one_feature_review_then_done`, `test_a_serial_run_with_acceptance_tests_ends_with_the_same_done_line`, `test_relay_hands_off_after_each_phase`, `test_serial_run_hands_out_the_tests_before_the_first_ticket`.
  - Lane `L<n>.code_files` keys are repo-relative (`agents/flow-architect.md`) where the old code had absolute ones (`<TMP-REPO>/agents/flow-architect.md`). The likely cause is ticket 15's removal of `os.chdir`: `Workspace.flow_code` now hashes from the main top. 2 tests have it: test_rebuild_lanes `test_a_lane_worktree_that_is_gone_stops_as_today`, `test_guides_and_roles_come_from_the_main_worktree`.
  These go to the conductor's end-of-run acceptance as fix tickets, as the ticket says. This ticket does not fix them.
- `bash tests/run.sh`: `466 passed, 0 failed`, exit 0.
- `git log --oneline -- tests/py/golden`: one line, ticket 01's commit: `065b00c test(conductor-rebuild): 01 Record golden runs of the conductor before anything moves`.

**Decisions**: kept the test from 6c14287 unchanged. It already does what the ticket asks.

**Shortcuts taken**: none.

**For later tickets**: the acceptance fix tickets need a ruling on `code_files`. Cause 1 can only pass if the twins comparison normalises the file list, which is a tester or product-owner call on a frozen acceptance test. Cause 2 is a real state-value change that a codehash naming fix in the lane workspace could undo.

## Attempt note

Attempt at 868f29c (auto). Stopped: the acceptance bullet fails, and every fix is outside this ticket's `Touches:`.

**Built (not committed as resolved):** `tests/py/test_conductor_package.py` now has `test_ratchet`. It walks `feature_flow/conductor/**/*.py` (skipping `__pycache__`) and uses one `subTest` per file. `facade.py` must be under 300 lines and every other file under 400. A failure prints `<path> has N lines, the limit is under L`. Sizes now: facade.py 296, workspace.py 363, schedulers/lane.py 312.

**Proof, run fresh at the end of this attempt:**
- `python3 -m unittest discover -s tests/py -p "test_conductor_package.py" -v`: lists `test_ratchet ... ok`, `Ran 6 tests`, `OK`, exit 0.
- `python3 -c "import feature_flow.conductor as c; print(c.Conductor, c.Stop, c.NoPhase)"`: `<class 'feature_flow.conductor.facade.Conductor'> <class 'feature_flow.conductor.errors.Stop'> <class 'feature_flow.conductor.errors.NoPhase'>`. The check block's gone command prints `conductor.py gone: True`, exit 0.
- `bash tests/run.sh`: `466 passed, 0 failed`, exit 0.
- `git log --oneline -- tests/py/golden` prints one line, ticket 01's commit: `065b00c test(conductor-rebuild): 01 Record golden runs of the conductor before anything moves`.
- **FAILS:** `python3 -m unittest discover -s plans/conductor-rebuild/acceptance -v`: `Ran 48 tests`, `FAILED (failures=13)`, exit 1. A3 (`test_a3_a_run_paused_at_a_handoff_on_the_old_code_goes_on_with_the_new_code`) and A4 (`test_a4_a_run_paused_mid_ticket_meets_the_flow_code_changed_stop`) both ran and passed. Ticket 16's Answer already reported the same 13 failures, so they were there before this attempt.

**What fails:** all 13 failures come from `support.twins` (`the run left different files on the current code`). Every differing line of the snapshot is in the state's `code_files` (I grepped the diff and found no differing line without `<SHA>`). There are two causes:
1. In serial and batch runs (10 tests: test_rebuild_lanes `test_a_lane_run_leases_merges_and_finishes_as_today`, test_rebuild_modes ×3, test_rebuild_user ×7), `code_files` lists `feature_flow/conductor/*.py` where the old code listed `feature_flow/conductor.py`. This is the file move itself, so the flow code cannot remove it. Only a twins comparison that ignores or normalises the `code_files` file list would pass, and `plans/conductor-rebuild/acceptance/` is frozen for builders. This is learnings (04)/(05).
2. In lane runs (test_rebuild_lanes `test_a_lane_worktree_that_is_gone_stops_as_today`, `test_guides_and_roles_come_from_the_main_worktree`, and the lane part of the first one), `L1.code_files` now has repo-relative keys (`agents/flow-architect.md`). The old code had absolute ones (`<TMP-REPO>/agents/flow-architect.md`). My reading of the code: the old code did `os.chdir` into the lane, so `codehash.flow_code`'s `git.toplevel()` was the lane and the main repo's roles were named by absolute path. Since ticket 15 (no chdir), `Workspace.flow_code` runs from the main top, so the names are relative and `L1.code_sha` changes with them. This changes a state value: spec.md § Edge cases says the state keys and format do not change. It belongs to ticket 15 (or 12), with codehash naming as the fix. Ticket 15's Answer recorded these lane failures as "the same way at 6871fde". I did not check this cause against older commits.

**What is needed (a human decides):** for cause 1, either the acceptance twins comparison changes (a tester or human edit, since acceptance is frozen), or the bar accepts these 13 as known. For cause 2, either reopen ticket 15 to keep the old absolute lane names in `code_files`, or accept the difference. The ticket body says to reopen the owning ticket. The builder rules forbid me to edit another ticket, so I did neither. Once this is settled, the ticket can be resolved again with no change to `test_ratchet`.
