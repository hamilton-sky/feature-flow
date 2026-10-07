# Time limit for the gate and the smoke test, and a log for a failed smoke test

Type: task
Status: open
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

