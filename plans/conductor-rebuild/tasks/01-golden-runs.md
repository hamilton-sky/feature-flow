# Record golden runs of the conductor before anything moves

Type: task
Status: resolved
Blocked by: —
Test first: no
Level: 3
Touches: tests/py/test_golden.py, tests/py/golden/

Write a new test, `tests/py/test_golden.py` (new), and its recordings in `tests/py/golden/` (new), on the conductor as it is now. Every later ticket is held to these recordings, so they must be made before ticket 03 moves any code. `Test first: no`: the test passes on the current code by design.

Each scenario builds a throwaway repo with `helpers.Repo` (`tests/py/helpers.py`, which copies the whole `feature_flow/` folder, so it keeps working once that holds a package), writes a small plan and commands.md, plays the session with `repo.flow(...)` (the way `tests/py/test_lanes_drive.py` and `tests/py/test_fast_drive.py` drive it: resolve tickets, save reviewer replies, run `verdict`, `next`, `prompt`, `scouts`), and records, per call: the command, its exit code and its stdout. At the end it records the log events (the scenario repo's run log, without the timestamp column) and the sorted keys of the final state file (keys only, not values). One test method per scenario, at least these 13:

- `test_serial`: default mode, two tickets, one review FAIL round (send back), `scouts` and `prompt` for a build and a review, and a session handoff (`FLOW_TICKETS_PER_SESSION=1`) then `start` again
- `test_relay`: `FLOW_RELAY=1`
- `test_fast`: `FLOW_FAST=1`, reviews deferred, the feature review passes
- `test_fast_batch`: fast mode with a batch of two tickets (`Touches:` lines that do not overlap)
- `test_lanes`: `FLOW_LANES=2`
- `test_fast_lanes`
- `test_acceptance`: an `Acceptance:` line; the tester writes a failing test, then the feature passes it
- `test_lanes_acceptance`
- `test_agent`: `FLOW_DRIVER=agent`
- `test_agent_budget`: agent driver with a budget that runs out (`BUDGET-FAST`)
- `test_ask_in_a_lane`: a builder's `## Ask: architect` in a lane, answered with `ANSWER: GIVEN`
- `test_failing_feature_review`: fast mode, the feature review fails once, the fix ticket is built, the second review passes
- `test_mode_errors`: the STOP lines of `start` with `FLOW_LANES=2` and `FLOW_RELAY=1`, `FLOW_LANES=9`, `FLOW_LANES=x`, `FLOW_DRIVER=robot`, `FLOW_FAST=2`, lanes run from a subfolder

Make the output stable before comparing: replace commit shas, the session token from `OK <token>`, the temp repo path and the lane worktree paths with placeholders, use `/` in paths, and read files with universal newlines, so it passes on Linux, macOS and the Windows CI job (no platform skips: CONTRIBUTING.md). For `prompt` output, write small fixture role and guide files into the scenario repo instead of copying the real `guides/` and `agents/`, so a later guide edit never changes a recording. Keep the whole test under about two minutes.

`python3 tests/py/test_golden.py --record` (a command line argument, no new environment variable) rewrites the recordings; plain unittest runs compare and, on a mismatch, show the scenario, the first differing line and both versions. Add one small test that the comparison catches a changed output line, a missing log event and an extra state key.

## Not in this ticket

- Any change under `feature_flow/`: tickets 03 to 16.
- The ratchet test: ticket 14.

## Done when

- `python3 -m unittest discover -s tests/py -p "test_golden.py" -v` lists the 13 scenario tests (among them `test_ask_in_a_lane` and `test_failing_feature_review`) and prints `OK`.
- At least 13 recording files are committed under `tests/py/golden/`, made by this code, before any file under `feature_flow/` changes.
- A reviewer reading three recordings (serial, lanes, failing feature review) finds BUILD, REVIEW, WAIT, DONE lines, log events and state keys, with no raw sha, token or temp path left in them.
- `bash tests/run.sh` passes (the gate runs it).

```check
# The conductor runs this block before review.
$ python3 -m unittest discover -s tests/py -p "test_golden.py" -v
prints test_ask_in_a_lane
prints test_failing_feature_review
prints test_mode_errors
prints OK
$ python3 -c "import pathlib,sys; n=len([p for p in pathlib.Path('tests/py/golden').rglob('*') if p.is_file()]); print('recordings', n); sys.exit(0 if n >= 13 else 1)"
prints recordings
```

## Reference

- spec.md § Design (Decisions: golden test drives the CLI, fixture guides, guarding the recordings)
- `tests/py/helpers.py` (`Repo`), `tests/py/test_lanes_drive.py` (`Drive`), `tests/py/test_fast_drive.py`, `tests/py/test_tester_drive.py`, `tests/py/test_ask_drive.py`, `tests/py/test_budget_drive.py`, `tests/py/test_batch_drive.py`
- `feature_flow/conductor.py` (read only): `start`, `next`, `lane_next`, `dispatch`

## Answer

- **Built**: `tests/py/test_golden.py` (new) and 13 recordings in `tests/py/golden/` (new, `test_<scenario>.txt`), all made on commit 6ea4a74's conductor; nothing under `feature_flow/` changed.
- **Proof**:
  - `python3 -m unittest discover -s tests/py -p "test_golden.py" -v`: lists the 13 scenario tests (`test_serial`, `test_relay`, `test_fast`, `test_fast_batch`, `test_lanes`, `test_fast_lanes`, `test_acceptance`, `test_lanes_acceptance`, `test_agent`, `test_agent_budget`, `test_ask_in_a_lane`, `test_failing_feature_review`, `test_mode_errors`) plus `test_the_comparison_catches_each_kind_of_change`; `Ran 14 tests in 35.460s`, `OK`, exit 0.
  - The recordings check prints `recordings 13`, exit 0.
  - In `test_serial.txt`, `test_lanes.txt` and `test_failing_feature_review.txt` there are BUILD, REVIEW, HANDOFF, WAIT and DONE lines, a `=== log events ===` section and a `=== state keys ===` section. `grep -rnE "[0-9a-f]{8,}|/tmp|tmp[a-z0-9_]{6}|/usr/bin|python3\.[0-9]" tests/py/golden/` finds nothing.
  - Stability: the compare run passes again with a longer `TMPDIR`, and with `TMPDIR` behind a symlink (the macOS `/var` case) under `/usr/bin/python3.11` (a different interpreter path): `OK` both times.
  - `bash tests/run.sh`: `466 passed, 0 failed`, exit 0.
- **Decisions**:
  - One `Session` class drives every scenario through `helpers.Repo.flow`. It records `$ <extra env> <args>`, `exit <rc>`, the cleaned stdout, and `# ...` notes for what the test itself did (built, replied, spent). At the end come the log events (timestamp column dropped) and the sorted state keys. The recording format is plain text, one file per scenario.
  - Normalisation, all in `Session.clean`, in this order:
    1. The repo path, in every form (as given, `resolve()`, `realpath`, git's `--show-toplevel`, each with `/` and `\`), becomes `<repo>`. The lane worktrees and the reply file sit under it or beside it, so they become `<repo>/.feature-flow/lanes/f/lane-1` and `<repo>-reply.txt`.
    2. `sys.executable` becomes `<python>`.
    3. 40-hex shas become `<sha>`. This runs before the token step, so a token never cuts into a sha.
    4. Session tokens become `<token>`; their owner hash and its 8-character prefix become `<owner>`.
    5. Remaining `\` become `/`.
    6. The single quotes `shlex.quote` puts around a Windows path are dropped.
  - Fixture roles and guides: every role and guide name `prompts.py` knows, plus `debug.md`. Each is written with front matter, every placeholder the conductor fills in, and a `python3 scripts/flow-status.py` line, so the lane rewrite of that line to `<repo>/scripts/...` is recorded too.
  - "Lanes run from a subfolder" runs `<repo>/scripts/flow.py` from `<repo>/sub` with `FLOW_DIR=<repo>/plans`. Without it, `start` finds no plan there and prints `PLAN` before it ever reaches the lanes rule.
  - Beyond the ticket's list, the recordings also hold:
    - the ticket text after a FAIL send-back (serial) and the feature review's fix ticket (`Session.show`);
    - `scout-prompt` output;
    - a successful `start` after the refused ones in `test_mode_errors`, so its state keys are recorded.
  - `compare()` finds the first differing line and names its section: calls, log events or state keys, judged by where that line sits in the recording. It shows the recorded and the current line plus a unified diff. A CRLF copy compares equal.
- **Shortcuts taken**:
  - `test_agent_budget` writes `spent` into the state file, as `test_budget_drive.py` does, and records `31 of 30 active minute(s)`. That holds as long as less than 60 seconds pass between that write and the `budget` call; today it is about 2 seconds.
  - Windows normalisation (8.3 short paths, `shlex` quoting, backslashes) is reasoned from the code, not run here. The first Windows CI run is its proof.
- **For later tickets**: the recordings are frozen (map.md). On a mismatch the failure names the scenario and the first differing line: fix the code, never the recording. A changed `prompt` output in a lane (ticket 12, Workspace) shows up in `test_lanes.txt` and `test_ask_in_a_lane.txt`. The state keys are recorded sorted and without values, so ticket 05 must keep every key name and add none.
