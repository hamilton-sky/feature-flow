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
