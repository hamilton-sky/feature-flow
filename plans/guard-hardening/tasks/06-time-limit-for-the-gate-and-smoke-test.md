# Time limit for the gate and the smoke test, and a log for a failed smoke test

Type: task
Status: resolved
Blocked by: 05
Test first: yes
Floor: allow flow-edit, skip, suppress

Add `FLOW_GATE_TIMEOUT` (minutes, default 30, `0` for none; a non number is a `STOP` like the other `FLOW_*` numbers, via `_env_int`). One helper in `feature_flow/command.py`-style (new `feature_flow/proc.py` is fine) runs a shell command with output to a file and a timeout, and on timeout kills the whole process tree: POSIX starts the child with `start_new_session=True` and kills the group with `os.killpg`; Windows runs `taskkill /T /F /PID <pid>`. Use it for each gate command (`gate.run`) and for `checks.smoke`. A gate command that times out fails the gate with a line saying which command timed out after how many minutes, and is sent back to the builder like any gate failure. A smoke timeout is a `STOP`. When the smoke test fails or times out, write its output to `.feature-flow/state/<feature>.smoke.log` (state folder, ignored by git) and make the STOP one line: `smoke test failed before <ticket>: the base is already broken. fix it first. command: <cmd>. the last 40 lines are in <path>`.

## Not in this ticket

- The `Smoke` command itself or when it runs.
- README settings table: ticket 09.

## Done when

- `python3 -m unittest discover -s tests/py -k timeout` passes: a gate `Test:` of `python3 -c "import time; time.sleep(60)"` with `FLOW_GATE_TIMEOUT` set to a tiny value (the helper takes minutes as a float, so a test can use 0.02) fails within a few seconds and the tree has no leftover sleeping child process; `FLOW_GATE_TIMEOUT=0` lets a 2 second command finish; `FLOW_GATE_TIMEOUT=abc` stops with a message naming the variable.
- A failing smoke command leaves `<state>/<feature>.smoke.log` with its last output and a single-line STOP naming that path.
- All existing tests still pass, including on Windows (the helper has a Windows branch exercised by the same tests).

## Reference

- spec.md § Design (Goal 4)
- feature_flow/gate.py (`shell`, `run`), feature_flow/checks.py (`smoke`, `gate`), feature_flow/conductor.py (`run_smoke`, `_env_int`), feature_flow/state.py

## Answer


**Built**: `feature_flow/proc.py` (new: `run(args, use_shell, log, minutes)` and `kill_tree`: `start_new_session` + `os.killpg` on POSIX, `taskkill /T /F` on Windows), `feature_flow/gate.py` (`timeout_minutes`, `run(..., timeout=None)`, uses proc), `feature_flow/checks.py` (`gate(..., timeout)`, `smoke(cmd, timeout)` with `Result.timed_out`), `feature_flow/conductor.py` (`FLOW_GATE_TIMEOUT` via `_env_int`, smoke log and one line STOP), `tests/py/test_timeout.py` (6 tests).

**Proof**:
- `python3 -m unittest discover -s tests/py -k timeout`: Ran 6 tests, OK (~5s). Covers: 0.02 minute gate timeout fails in seconds with "gate: Test timed out after 0.02 minutes" and the sleeping pid is gone (POSIX check); `FLOW_GATE_TIMEOUT=0` lets a 2 second command pass; `abc` gives code 2 naming the variable, and the conductor prints STOP naming it; smoke timeout kills and sets `timed_out`.
- Failing smoke: the test asserts a one line `STOP smoke test failed before 01-a: ... command: ... the last 40 lines are in <state>/f.smoke.log` and that the log holds the output. Passes.
- `python3 -m unittest discover -s tests/py`: 165 tests OK. `bash tests/run.sh`: 441 passed, 0 failed. Tests use `sys.executable` and a script file, no bash syntax; the pid and process check is guarded by `sys.platform != "win32"`.

**Decisions**: the env value is whole minutes (`_env_int`), the float only comes through the `timeout` argument that tests pass. The conductor reads it once in `__init__` (so `abc` stops every command) and passes it down; standalone `gate.py` reads the env itself and exits 2 with a message. A timed out gate command prints `gate: <Key> timed out after N minutes, stopped: <cmd>` and returns 1, so it goes back to the builder like any gate failure. Smoke timeout STOP reads `smoke test timed out after N minutes before <ticket>: ...` with the same tail. The log holds the last 40 lines (plus a timeout line).

**Shortcuts taken**: none. Note the smoke timeout is not tested end to end through the conductor (the env is whole minutes, so it would take 1 minute); it is tested through `checks.smoke`.

**For later tickets**: ticket 08 (committed copy under `.feature-flow/`) must re-sync, `feature_flow/proc.py` is a new file. Ticket 09 README settings table: `FLOW_GATE_TIMEOUT` minutes, default 30, 0 for none, also bounds the Smoke run. Log file name is `<feature>.smoke.log` in `.feature-flow/state/`.
