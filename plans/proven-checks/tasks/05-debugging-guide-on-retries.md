# Add a debugging guide to the build prompt after a send-back

Type: task
Status: resolved
Blocked by: —
Test first: yes

Write `guides/debug.md`, short (about 30 lines), runtime neutral (no skill invocation such as `/feature-flow`): you were sent back; read every finding; **reproduce** the failure with the exact command named in it before changing code; **isolate** the cause (smallest failing case, one hypothesis at a time, read the code path, do not guess); **fix** the cause, not the symptom, and never by weakening a check; **prove** it by re-running the command that failed and then the ticket's Done when; after two failed fixes of the same error, stop as the build guide says.

In `feature_flow/prompts.py` give `build` a `retry=False` argument: when it is true and the phase is `build`, append `The debugging guide follows. Follow it before you change any code.` and the body of `guides/debug.md` (found with `find_file`). `Conductor.prompt` passes `retry=self.num("round") > 0`. Include `debug.md` in the `codehash` fingerprint.

## Not in this ticket

- A new skill or agent for debugging: the brief rules it out.
- Adding the guide on an unresolved attempt that was not sent back: spec.md § Decisions.

## Done when

- `python3 -m unittest discover -s tests/py -k debug` passes with tests: the first `BUILD` prompt does not contain `The debugging guide follows`; after a failing gate sends the ticket back, the `BUILD` prompt contains it and the words reproduce, isolate, fix and prove.
- `tests/run.sh`'s check that guides name no runtime's skill invocation covers `guides/debug.md` (add `debug` to its list) and passes.
- All existing tests still pass: `python3 -m unittest discover -s tests/py && bash tests/run.sh`.

## Reference

- spec.md § Design (Debugging guide)
- feature_flow/prompts.py (`build`, `find_file`), feature_flow/conductor.py (`prompt`, `send_back`), feature_flow/codehash.py (`_files`), guides/build.md (Failure handling), tests/run.sh (section `flow.py, guides and prompt`)

## Answer


**Built**: `guides/debug.md` (32 lines, no skill invocation); `feature_flow/prompts.py` (`build(..., retry=False)` appends the intro line and the `debug.md` body after the task when `retry` and phase is `build`); `feature_flow/conductor.py` (`prompt` passes `retry=self.num("round") > 0`); `feature_flow/codehash.py` (`debug.md` in `_files`); `tests/run.sh` (`debug` added to the guide list); `tests/py/test_debug.py` (new).

**Proof**:
- `python3 -m unittest discover -s tests/py -k debug`: 2 tests, OK. Before the code, the retry test failed with `'The debugging guide follows' not found in ...` (right reason); the first-build test passed.
- `bash tests/run.sh`: `ok guides/debug.md exists`, `ok guides/debug.md names no runtime's skill invocation`; 446 passed, 0 failed.
- `python3 -m unittest discover -s tests/py && bash tests/run.sh`: 219 tests OK, then 446 passed 0 failed, both exit 0.

**Decisions**: the guide follows the task block at the end of the prompt, so it is the last thing read. The retry test drives a real failing gate (`FAILING` file with a Test command), as the ticket says. `retry` applies only to phase `build`, so reviewer prompts never get it.

**Shortcuts taken**: none.

**For later tickets**: ticket 06 may reference `guides/debug.md` from `guides/build.md`; build.md's Failure handling already says to stop after two failed fixes. Ticket 08 (README) can list `guides/debug.md`.
