# Stop on flow code changed during a conductor call or a state the conductor did not save; allow flow-edit builds

Type: task
Floor: allow flow-edit
Status: open
Blocked by: 02, 03
Test first: yes

Extend `scripts/flow-trust.py` with the checks across the conductor call.

1. **Code unchanged during the call.** Compare the code part of the digest taken before the call with the one taken after. A difference prints `STOP flow code changed during <command>: <paths>` (instead of the `TRUST` line) and exits 1. This catches hole (c): a `Test:` command, Done when check, smoke command or git hook that edits the conductor while `next` runs.
2. **State as saved.** Parse the conductor's final stderr line `flow-state <state> <findings>` (from ticket 02). If it is missing, or either file's sha256 after the call differs from its value (or the file exists when it says `none`), print `STOP the run state was changed by something other than the conductor during <command>` and exit 1.
3. **Flow-edit builds.** With `--after-build <ticket> <sha>`, a difference in the *code* part of the digest between `FLOW_TRUST` and now (the state part must still match exactly; `.trust` is used only to name paths, never to decide) is accepted when `git --no-replace-objects cat-file blob <sha>:<ticket path relative to the repo>` succeeds and its `Floor:` line lists `flow-edit` (parse it the way `floorguard.allow_line` does, reimplemented in a few lines since nothing can be imported). Then print `FLOW-EDIT <paths>` after the `TRUST` line and go on. A difference in the state files is never accepted, flag or not. Without the flag, or when the ticket at `<sha>` has no such line, STOP as before.

Tests in `tests/py/test_trust_runner.py`: hole (c) (a plan whose `commands.md` has `Test: <python> t.py`, where the builder's committed `t.py` edits `feature_flow/conductor.py`) ends in `STOP flow code changed during next`; the state check, driven by a stand-in `flow.py` in a temp conductor folder (a copy of the runner beside a small script that writes the state file, then reports a different sha, or no `flow-state` line at all), ends in `STOP the run state was changed by something other than the conductor`, and a stand-in that reports the right sha goes through; `--after-build` with a ticket that has `Floor: allow flow-edit` at its base accepts an edited `feature_flow/floorguard.py` and prints `FLOW-EDIT feature_flow/floorguard.py`; the same without the line, or with the line added only after the base commit, STOPs; a `git replace` of the ticket blob that adds the line is ignored; a flow-edit build that also appends to `flow-f.state` and rewrites `.trust` to match STOPs.

## Not in this ticket

- The skill text that tells the session when to pass `--after-build`: ticket 06.
- The conductor's own `codehash` tripwire: kept as is.

## Done when

- `python3 -m unittest discover -s tests/py -p "test_trust_runner.py"` prints `OK` with the cases above.
- `python3 -m unittest discover -s tests/py` prints `OK`.

```check
$ python3 -m unittest discover -s tests/py -p "test_trust_runner.py"
prints OK
$ python3 -m unittest discover -s tests/py
prints OK
```

## Reference

- spec.md § Decisions (When to snapshot, State changes during a call), § Edge cases
- `feature_flow/floorguard.py` (`allow_line`), `feature_flow/conductor.py` (`flow_edit_allowed`)
- learnings.md (the hole c repro)

## Answer
