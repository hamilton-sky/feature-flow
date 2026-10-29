# Make the acceptance tests pass, round 1

Type: task
Status: resolved
Blocked by: —
Test first: no
Level: 2
Check: none the conductor runs the acceptance tests again once every ticket is resolved

Every ticket is resolved, but the acceptance tests fail. The tester wrote them in `plans/conductor-rebuild/acceptance/` from spec.md before the build, so they check what the product owner asked for, not how it was built. Fix the code so they pass. You may run them with `python3 -m unittest discover -s plans/conductor-rebuild/acceptance -v`.

If you are sure a test asks for something spec.md does not say, do not work around it, and do not change the test: the floor guard fails any change under `plans/conductor-rebuild/acceptance/`. Add a `## Ask: po` section to this ticket that names the test, what it expects and the spec.md line it disagrees with, and stop. The product owner rules on it. A test it rules wrong is left failing here and goes back to the tester once this ticket is resolved.

## Not in this ticket

- Any file under `plans/conductor-rebuild/acceptance/`.

## Done when

- `python3 -m unittest discover -s plans/conductor-rebuild/acceptance -v` passes, apart from tests the product owner ruled wrong in this ticket.
- commands.md's Test command passes.

## The failing run

       'Smoke: `"/usr/bin/python3" -c "pass"`\n'
       'Test: `"/usr/bin/python3" -c "pass"`\n'
       'Acceptance: `"/usr/bin/python3" plans/f/acceptance/check.py`\n',
       'plans/f/learnings.md:\n# Learnings: f\n\n- (NN) <what you found>\n',
       'plans/f/map.md:\n'
       '# Map: f\n'
       '\n'
       '## Decisions so far\n'
       '\n'
       '<One line per resolved ticket.>\n',
       'plans/f/spec.md:\n# Spec\n\n## Stories\n\n- [ ] every ticket is built\n',
       'plans/f/tasks/01-t.md:\n'
       '# T1\n'
       '\n'
       'Type: task\n'
       'Status: open\n'
       'Blocked by: —\n'
       'Test first: no\n'
       'Touches: t01/\n'
       '\n'
       'body\n'
       '\n'
       '## Done when\n'
       '\n'
       '- x\n'
       '\n'
       '```check\n'
       '$ "/usr/bin/python3" -c "print(\'fine\')"\n'
       'prints fine\n'
       '```\n'
       '\n'
       '## Answer\n',
       'plans/f/tasks/02-t.md:\n'
       '# T2\n'
       '\n'
       'Type: task\n'
       'Status: open\n'
       'Blocked by: 01\n'
       'Test first: no\n'
       'Touches: t02/\n'
       '\n'
       'body\n'
       '\n'
       '## Done when\n'
       '\n'
       '- x\n'
       '\n'
       '```check\n'
       '$ "/usr/bin/python3" -c "print(\'fine\')"\n'
       'prints fine\n'
       '```\n'
       '\n'
       '## Answer\n',
       'commits on the branch:\nplan\ninit',
       'all commits:\ninit\nplan'] : the run left different files on the current code
    
    ----------------------------------------------------------------------
    Ran 48 tests in 157.084s
    
    FAILED (failures=13)

## Answer

**Built** (in 2a5124f, from 52b85d9; nothing new in this pass): `feature_flow/codehash.py` (`flow_code(scripts, cwd=None)` finds the repo top with `git.toplevel(cwd=cwd)`), `feature_flow/conductor/workspace.py` (`Workspace.flow_code` passes `cwd=self.folder`), `tests/py/test_workspace.py` (the lane snapshot test now finds the main role's hash under its absolute key, the same key the old code wrote). This pass sets the Status, writes this Answer and adds the map line.

**Proof** (run fresh at b2bea3b, after the PO ruling):
- `python3 -m unittest discover -s plans/conductor-rebuild/acceptance -v`: `Ran 48 tests`, `FAILED (failures=13)`, exit 1. The 13 that fail are exactly the 13 the PO ruled wrong under Consulted (po) (3 in test_rebuild_lanes, 3 in test_rebuild_modes, 7 in test_rebuild_user, names as listed in the Ask). The other 35 pass, A3 and A4 among them. In each of the 13 diffs the two sides are equal once the `"(<TMP-REPO>/)?feature_flow/conductor[^"]*": "<SHA>"` entries are removed, so the only difference left is the package file names in `code_files`, which is what the ruling covers.
- `bash tests/run.sh` (the Test command): `466 passed, 0 failed`, exit 0.

**Decisions**: per the PO ruling (option a) I changed no code for the `code_files` file names. They follow the move to `feature_flow/conductor/` (spec.md lines 17, 38, 180). The lane key fix stays: it made lane keys match the old code's (absolute for the main worktree's files), so a package name is now the only thing left in each diff.

**Shortcuts taken**: none.

**For later tickets**: the tester has to change `support.twins` so that the `code_files` / `L<k>.code_files` values match when the only difference is `feature_flow/conductor.py` against the package files, as the PO ruled. Once that change is in, all 48 acceptance tests should pass on this code. Anything else that differs in the snapshot would need its own ruling.

## Attempt note

Attempt from 52b85d9 (auto). Status left open: the acceptance bullet still fails, on 13 tests that need a product-owner ruling (Ask below).

**Fixed (cause 2 of ticket 14's Answer, lane `code_files` keys):** `codehash.flow_code(scripts, cwd=None)` now finds the repo top with `git.toplevel(cwd=cwd)` (falling back to `cwd`, else the working folder), and `Workspace.flow_code` passes `cwd=self.folder`. So a lane names files relative to the lane's own repo, as the old code did after `os.chdir` into the lane: the main worktree's files get absolute paths (`<TMP-REPO>/agents/flow-architect.md`), which is what the old code wrote. The file list itself is unchanged (still the main top's roles and guides, ticket 12's review fix). The main worktree passes `folder=None`, so serial, batch and run-wide snapshots are unchanged. `tests/py/test_workspace.py` `test_a_lane_snapshot_names_the_main_worktrees_role` asserted the relative key that the acceptance tests show is a state change; it now looks up the same hash under the main role's absolute path (same check, same strength; the `lane-1` check is unchanged).

**Proof, run fresh after the last edit:**
- `bash tests/run.sh`: `466 passed, 0 failed`, exit 0.
- `python3 -m unittest discover -s plans/conductor-rebuild/acceptance -v`: `Ran 48 tests`, `FAILED (failures=13)`, exit 1; A3 and A4 ok. The same 13 names still fail, but every one now differs only in package file names: a script that joins each failure's diff lines and removes every `"(<TMP-REPO>/)?feature_flow/conductor[^"]*": "<SHA>"` entry finds old and new equal for all 13 (it found them different for `test_guides_and_roles_come_from_the_main_worktree` before the fix, the relative vs absolute keys).
- `python3 -m unittest test_golden` (from tests/py): 14 tests OK.

## Ask: po

All 13 remaining acceptance failures are the `support.twins` snapshot assertion (`the run left different files on the current code`), and the only difference left is the file list in the state's `code_files` (and `L<k>.code_files`): the old code lists `feature_flow/conductor.py`, the current code lists `feature_flow/conductor/__init__.py`, `facade.py`, ... (the package files). Tests:

- test_rebuild_lanes: `test_a_lane_run_leases_merges_and_finishes_as_today`, `test_a_lane_worktree_that_is_gone_stops_as_today`, `test_guides_and_roles_come_from_the_main_worktree`
- test_rebuild_modes: `test_other_commands_ignore_a_bad_flow_lanes`, `test_patching_check_code_on_the_class_turns_the_code_check_off`, `test_batch_preconditions`
- test_rebuild_user: `test_state_log_findings_ticket_sections_and_followups_are_the_same`, `test_the_17_commands_print_the_same_lines_with_the_same_exit_codes`, `test_a_batch_is_judged_as_today`, `test_a_fast_run_defers_reviews_to_one_feature_review_then_done`, `test_a_serial_run_with_acceptance_tests_ends_with_the_same_done_line`, `test_relay_hands_off_after_each_phase`, `test_serial_run_hands_out_the_tests_before_the_first_ticket`

**What they expect:** the state file left by a run on the new code equals the old code's byte for byte after `World.norm` (shas, tokens, temp paths), including the `code_files` value, which names every flow file.

**Where spec.md disagrees:** line 11 (`feature_flow/conductor.py` becomes the package `feature_flow/conductor/`), line 17 (`feature_flow/conductor.py` no longer exists) and line 180 (`feature_flow/codehash.py` hash every file under `feature_flow/`, recursively, ... picks the package up without changes; the trust digest of a run changes once, when the files change). Line 38 asks for the same keys and the same `key=value` format, which holds: the key `code_files` and its JSON format are the same, only the file names inside the value follow the move. No code change can make the value name `feature_flow/conductor.py` while that file must not exist and codehash must hash the package files.

**Options I see:** (a) rule these 13 wrong as written: the twins snapshot should normalise the file names inside `code_files` (or the package entries against `feature_flow/conductor.py`), a tester change; (b) accept them as known failures for this feature. I changed nothing under `plans/conductor-rebuild/acceptance/`.

## Consulted (po)

**Question:**

All 13 remaining acceptance failures are the `support.twins` snapshot assertion (`the run left different files on the current code`), and the only difference left is the file list in the state's `code_files` (and `L<k>.code_files`): the old code lists `feature_flow/conductor.py`, the current code lists `feature_flow/conductor/__init__.py`, `facade.py`, ... (the package files). Tests:

- test_rebuild_lanes: `test_a_lane_run_leases_merges_and_finishes_as_today`, `test_a_lane_worktree_that_is_gone_stops_as_today`, `test_guides_and_roles_come_from_the_main_worktree`
- test_rebuild_modes: `test_other_commands_ignore_a_bad_flow_lanes`, `test_patching_check_code_on_the_class_turns_the_code_check_off`, `test_batch_preconditions`
- test_rebuild_user: `test_state_log_findings_ticket_sections_and_followups_are_the_same`, `test_the_17_commands_print_the_same_lines_with_the_same_exit_codes`, `test_a_batch_is_judged_as_today`, `test_a_fast_run_defers_reviews_to_one_feature_review_then_done`, `test_a_serial_run_with_acceptance_tests_ends_with_the_same_done_line`, `test_relay_hands_off_after_each_phase`, `test_serial_run_hands_out_the_tests_before_the_first_ticket`

**What they expect:** the state file left by a run on the new code equals the old code's byte for byte after `World.norm` (shas, tokens, temp paths), including the `code_files` value, which names every flow file.

**Where spec.md disagrees:** line 11 (`feature_flow/conductor.py` becomes the package `feature_flow/conductor/`), line 17 (`feature_flow/conductor.py` no longer exists) and line 180 (`feature_flow/codehash.py` hash every file under `feature_flow/`, recursively, ... picks the package up without changes; the trust digest of a run changes once, when the files change). Line 38 asks for the same keys and the same `key=value` format, which holds: the key `code_files` and its JSON format are the same, only the file names inside the value follow the move. No code change can make the value name `feature_flow/conductor.py` while that file must not exist and codehash must hash the package files.

**Options I see:** (a) rule these 13 wrong as written: the twins snapshot should normalise the file names inside `code_files` (or the package entries against `feature_flow/conductor.py`), a tester change; (b) accept them as known failures for this feature. I changed nothing under `plans/conductor-rebuild/acceptance/`.

**Answer:**

Option (a). The 13 twins snapshot failures are wrong as written, and the tester should fix them. The builder changes no code.

spec.md promises the same keys and the same format for the state file, not the same values, and it says the flow's file set changes:
- Line 38: "The state file has the same keys and the same `key=value` format; the log has the same events; findings files, the ticket sections and `followups.md` text the conductor writes are the same."
- Line 180: "`scripts/flow-trust.py` and `feature_flow/codehash.py` hash every file under `feature_flow/`, recursively) picks the package up without changes; the trust digest of a run changes once, when the files change, as it does for any upgrade."
- Line 17: "`feature_flow/conductor.py` no longer exists."

The `code_files` value lists the flow's files, so it has to follow the move. Line 38 is met because the key, its JSON format and the key=value line are unchanged.

For the tester: `support.twins` should treat `code_files` and `L<k>.code_files` values as matching when the only difference is `feature_flow/conductor.py` against the `feature_flow/conductor/` package files (mask the file list, or map package entries to the old single file), and still check the keys and JSON format are unchanged. Everything else in the snapshot stays byte for byte after `World.norm`. This ruling covers only `code_files`; any other difference needs its own ruling.

The product owner ruled the test wrong: leave it failing and finish the rest. The tester changes it once this ticket is resolved.
