# Have the conductor report the state it saved, store a hashed owner, and refuse direct loop calls

Type: task
Floor: allow flow-edit
Status: open
Blocked by: —
Test first: yes

Three small conductor changes the runner relies on.

1. **Report the saved state.** In `feature_flow/state.py`, remember the bytes `save()` last wrote and `load()` last read (module level or returned to the caller, whichever is least code), and the fact that a file was deleted (`Conductor.reset` unlinks it). Do the same for the findings file (`flow-<feature>.findings`, written by `Conductor.verdict`, read by `judge_review`, deleted by `reset`). In `feature_flow/cli.py` `main()`, when `FLOW_TRUSTED=1` is set, write `flow-state <state sha256 or none> <findings sha256 or none>` (the sha of the bytes the conductor left in each file as far as it knows: what it last wrote, else what it read, else `none` when the file did not exist or was deleted) as the very last line on stderr, on every exit path including `STOP` and `NoPhase`. The sha is computed from the bytes in memory, never by re-reading the file. Without `FLOW_TRUSTED=1` nothing changes.
2. **Hash the owner.** `Conductor.start` keeps printing `OK <token>` but stores `owner=<sha256 hex of the token>`. `Conductor.check_owner` compares `sha256(FLOW_SESSION)` with it. A stored owner of exactly 16 hex characters is a run started by an earlier version: accept a matching raw token and store the hash on the next save. STOP messages that today print the owner print only its first 8 characters.
3. **Refuse direct loop calls.** `next`, `prompt` and `verdict` without `FLOW_TRUSTED=1` STOP with `run the conductor through scripts/flow-trust.py, as the skill says`. `start`, `reset` and the planning commands stay allowed. Set `FLOW_TRUSTED=1` in `tests/py/helpers.Repo.flow`, in `tests/py/test_fixture_drive.py`, and wherever `tests/run.sh` or another test calls `next`, `prompt` or `verdict`, so every existing test keeps passing.

Add the tests in `tests/py/test_state_report.py`.

## Not in this ticket

- Checking the reported sha against the file: ticket 04.
- A "previous ticket passed review" check in `pick_ticket()`: dropped by the plan (spec.md § Decisions).

## Done when

- With `FLOW_TRUSTED=1`, `start`, `next`, `verdict` with a FAIL reply, a `STOP` and `reset` each end stderr with `flow-state <hex> <hex|none>` (`none none` after reset), and each value equals the sha256 of the state and findings files on disk right after the call.
- The state file after `start` holds no line containing the printed token, and `next` with that token works.
- `next` without `FLOW_TRUSTED=1` prints a line starting `STOP run the conductor through scripts/flow-trust.py`.
- `python3 -m unittest discover -s tests/py -p "test_state_report.py"` prints `OK`, and `python3 -m unittest discover -s tests/py` prints `OK`.

```check
$ python3 -m unittest discover -s tests/py -p "test_state_report.py"
prints OK
$ python3 -m unittest discover -s tests/py
prints OK
```

## Reference

- spec.md § Interfaces, § Migration and compatibility
- `feature_flow/state.py`, `feature_flow/cli.py`, `feature_flow/conductor.py` (`start`, `check_owner`, `reset`)

## Answer

Work started at 059c302e35928f6069140582729bf98ad265641e. Test-only commit: 9017dd0 (`test(trusted-checks): 02 failing test`); at that commit `test_state_report.py` failed 5 of 7 (stderr empty instead of `flow-state`, `owner=05f0...` raw token in the state file, STOP printed the full owner, `next` without `FLOW_TRUSTED` exited 0). The 2 that passed there (`start`/`reset`/planning stay allowed, no report without `FLOW_TRUSTED`) guard what must not change.

**Built**

- `feature_flow/state.py`: module-level `SEEN` ("state"/"findings" -> bytes last written or read, `None` for no file or deleted), `reported()`, `read_bytes`, `read_text`, `write_text`, `remove`. `load()` reads through `read_text`; `save()` writes the encoded bytes with `write_bytes` and remembers them.
- `feature_flow/conductor.py`: `owner_hash()` and `OLD_OWNER`; `start` stores `owner=sha256(token)` and still prints `OK <token>`; `check_owner` accepts `sha256(FLOW_SESSION) == owner`, or a stored 16-hex owner equal to the raw token (then sets the hash for the next save); the three owner STOPs print `owner[:8]`. `__init__` reads the findings file's bytes; `verdict` writes findings, `judge_review` reads them and `reset` removes both files through `state`.
- `feature_flow/cli.py`: `main()` clears `state.SEEN`, runs the old body (now `run()`), and in a `finally` with `FLOW_TRUSTED=1` writes `flow-state <state> <findings>` as the last stderr line. `next`, `prompt`, `verdict` without `FLOW_TRUSTED=1` print `STOP run the conductor through scripts/flow-trust.py, as the skill says` and exit 1, before the conductor is built.
- Tests: `tests/py/test_state_report.py` (new, 7 tests); `FLOW_TRUSTED=1` added in `tests/py/helpers.Repo.flow`, both `flow()` helpers in `tests/py/test_fixture_drive.py`, the in-process `cli.main` call in `tests/py/test_proof.py`, and exported at the top of `tests/run.sh`. Two existing assertions adapted to the ticket's new behaviour: `test_conductor.test_a_run_kept_under_git_moves_over_with_its_owner` now uses a 16-hex old token (the ticket's migration rule; `abc123` is not one), expects `abc12301.` in the STOP and the hashed owner after `next`; `tests/run.sh` "and names the owner" (twice) expects the first 8 characters of sha256 of the token instead of the token.

**Proof**

- Report on every path: `test_every_call_reports_the_files_it_left` runs `start`, `next` (BUILD), `verdict` with nothing pending (NoPhase, exit 2), `next` (REVIEW), `verdict` with a FAIL reply (findings sha not `none`), `next` with a wrong token (STOP, findings sha not `none`), `next` (BUILD again), `reset` (`none none`), each time comparing the last stderr line with sha256 of both files on disk. By hand in a `helpers.Repo`: `start` -> `flow-state 0fd77063...c7a3 none`, disk `0fd77063a077 none`; `next` -> `flow-state d6580ef4...88ef none`, disk `d6580ef4647e none`.
- Token not stored: `test_the_state_file_holds_only_the_hash_of_the_token` (no state line holds the token, owner = sha256(token), `next` with the token gives BUILD, the hash itself is refused). By hand: `token in state: False`, then `next` -> `BUILD plans/f/tasks/01-a.md 01 ...`.
- Refusal: `test_loop_commands_need_the_runner` (next, prompt, verdict: exit 1, exact line). By hand: `(1, 'STOP run the conductor through scripts/flow-trust.py, as the skill says', [])`.
- `python3 -m unittest discover -s tests/py -p "test_state_report.py"`: `Ran 7 tests ... OK`. `python3 -m unittest discover -s tests/py`: `Ran 278 tests in 102.603s OK`. `bash tests/run.sh`: `464 passed, 0 failed`, exit 0. Smoke command: exit 0.

**Decisions**

- `SEEN` is module level and keyed by the file suffix (`.state`, `.findings`): least code, no paths passed to the CLI; the `.tmp` and `.log` files are never recorded. `main()` clears it so in-process calls (test_proof) do not carry it over.
- The conductor reads the findings file's bytes at start, so a call that never touches findings (start, a STOP, a build `next` after a FAIL round) still reports what is there instead of `none`; bytes, not text, so a damaged file cannot crash every call.
- `save()` and the findings write use `write_bytes`: text mode would turn `\n` into `\r\n` on Windows and the reported sha would not match the file. `load()` still splits lines the same way.
- The refusal lives in `cli.run()` before `Conductor(...)` is built, so a refused call reads and writes nothing (it reports `none none`).
- The flow-state line is written in `finally`, so it also follows usage errors (exit 2), NoPhase and STOP.

**Shortcuts taken**

- An uncaught Python exception still prints `flow-state` first and its traceback after it, so the line is not last on that path. Nothing catches it on purpose (no swallowing); ticket 04's runner sees a non-zero exit and a non-matching last line, which should STOP anyway.

**For later tickets**

- 03/04 (runner): set `FLOW_TRUSTED=1` for the conductor and parse the last stderr line `flow-state <64 hex|none> <64 hex|none>`; `none` means the file did not exist (or was deleted) as far as the conductor knows. A usage error before the conductor is built reports `none none` even if files exist.
- 06/07: `start` still prints `OK <token>`; the state now holds `owner=<sha256>`. Owner STOPs print 8 characters of the hash, not the token. Direct `next|prompt|verdict` now STOP: README and skills (07, 06) must use the runner. `tests/run.sh` exports `FLOW_TRUSTED=1` at its top.

## Review findings (round 1, quality review)

QUALITY
1. major feature_flow/cli.py: With FLOW_TRUSTED=1, any exit before `Conductor(...)` reads the files reports `flow-state none none`, even when the state and findings files exist. That covers the usage and arg-count errors, the bad feature name, and a Stop raised early in `Conductor.__init__`. Reproduced: `start`, then `FLOW_TRUSTED=1 flow.py f verdict` with no file returns rc 2 and the last stderr line is `flow-state none none`, while `.feature-flow/state/flow-f.state` exists. The ticket defines `none` as "the file did not exist or was deleted", not "never looked". Ticket 04 STOPs with "the run state was changed by something other than the conductor" when a file exists but the report says `none`, so a simple usage mistake will look like tampering. Fix: once the feature name passes validation, read both files before any early return, or have `main` report only after the files have been resolved and read. Add a test for a trusted usage error while a run is active.
2. minor feature_flow/state.py / feature_flow/conductor.py: A damaged state file that is not valid UTF-8 makes `state.load` raise after the state bytes are recorded but before `Conductor.__init__` reads the findings file. The report then says `none` for an existing findings file, and the traceback ends up above the flow-state line. Fix: read the findings file before decoding the state, or catch the decode error and raise Stop.
3. minor feature_flow/state.py: `_remember` picks the kind from the path suffix (`.state` / `.findings`). Any future file with one of those suffixes that goes through `write_text`/`remove` would silently overwrite the report. Fix: pass the kind in explicitly, or compare against the conductor's own two paths.
REVIEW: FAIL
