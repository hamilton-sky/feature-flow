# Stop on flow code changed during a conductor call or a state the conductor did not save; allow flow-edit builds

Type: task
Floor: allow flow-edit
Status: resolved
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

Work started at 8b9240085daa53365bf2368661c96a03db03fd09. Test-only commit: 0582722 (`test(trusted-checks): 04 failing test`). At that commit `test_trust_runner.py` failed 6 of 54 tests, each for the reason the ticket names. Hole (c) printed `TRUST ...` then `REVIEW ...` with exit 0. The three state stand-ins (wrong sha, no `flow-state` line, findings file present while the report says `none`) each printed TRUST with exit 0. The flow-edit accept case printed `STOP flow files changed since the last step: feature_flow/floorguard.py`. The killed conductor still printed TRUST first. The stop-side flow-edit cases passed already at that commit, because the runner stopped on any change before this ticket. They guard what must stay a STOP.

**Built**

- `scripts/flow-trust.py`:
  - `parse()` now returns `--after-build <ticket> <sha>` as a fourth value.
  - `main()` always takes the "before" snapshot, `new` calls included.
  - After the call it checks, in this order:
    1. Code before != code after: `STOP flow code changed during <command>: <paths>`. The paths come from the two in-memory snapshots, not from `.trust`.
    2. Killed by a signal: the existing KILLED STOP.
    3. `state_as_saved()` fails: `STOP the run state was changed by something other than the conductor during <command>`. This happens when the `flow-state` line is missing or malformed, or when either sha differs from the file on disk, or when the line says `none` and the file exists.
  - A STOP takes the TRUST line's place. The conductor's stdout and its stripped stderr still follow, the exit code is 1, and `.trust` is not rewritten, so the next call names paths against the last trusted list.
  - When the digest differs before the call, `flow_edit()` accepts the change only if all three hold: `--after-build` was given, the state part of `FLOW_TRUST` equals the state part now, and `allows_flow_edit()` is true. `allows_flow_edit()` runs `git --no-replace-objects cat-file blob <sha>:<ticket>` (sha must be 4-64 hex; an absolute ticket path must be inside the repo and is made relative) and parses the first `Floor:` line in the first 20 lines with the same regex as `floorguard.allow_line`. When accepted, the runner prints `FLOW-EDIT <paths>` after TRUST. The paths come from `.trust`, for naming only.
- `tests/py/test_trust_runner.py` (13 new tests, 2 adapted):
  - `HoleC`: the `t.py` Test command edits the conductor and the call STOPs; a `t.py` that edits nothing gets REVIEW.
  - `StateAsSaved`: the stand-in `flow.py` beside a copy of the runner; wrong sha, no line and findings present while the report says `none` each STOP; the right sha goes through.
  - `FlowEdit`: accepted, with `FLOW-EDIT feature_flow/floorguard.py`, and the next call with the new digest goes through; without the flag it STOPs; a state append, with or without `.trust` rewritten to match, STOPs with the flag.
  - `FlowEditNoLine`: no line STOPs; the line added only after base STOPs; a `git replace` of the ticket blob STOPs (the test first checks that plain `git cat-file` does see the forged line).
  - Adapted from ticket 03, `KilledInProcess`: the killed case now expects the STOP as the first line instead of TRUST, and no `.trust` written. The pass-through case's fake stderr is now the well-formed `flow-state none none`, because `flow-state f none` is now correctly a STOP.

**Proof**

- `python3 -m unittest discover -s tests/py -p "test_trust_runner.py"`: `Ran 54 tests in 56.640s OK`.
- `python3 -m unittest discover -s tests/py`: `Ran 335 tests in 163.096s OK`, exit 0.
- `bash tests/run.sh` (the gate's Test command): `465 passed, 0 failed`, exit 0. Smoke command: exit 0.
- No added line in `tests/` contains skip, `.only(` or expectedFailure (grep of the diff from 8b92400).

**Decisions**

- After-call checks run in this order: code, killed, state. A code change is the most specific cause. A killed conductor cannot vouch for its state, so it no longer gets a TRUST line.
- On an after-call STOP the conductor's output still follows the STOP line. The spec says "first line TRUST (or STOP), then the conductor's output", and the skill acts on the first line. Seeing what the conductor did helps a human diagnose the STOP.
- `.trust` is written only when TRUST is printed.
- The Floor line is read as text decoded with `replace`. `str.split()` drops a CRLF `\r`, so a Windows-checked-out ticket parses the same.
- The FLOW-EDIT path list is named from `.trust`, like the other STOP lists. The decision itself rests only on the digest's state part and the git blob.

**Shortcuts taken**

- none

**For later tickets**

- 05: the TRUST/STOP choice is in `main()`'s `stop` variable. Add the HANDOFF rewrite only on the TRUST path.
- 06: pass `--after-build <ticket> <base sha>` from the BUILD line (`BUILD <ticket> <num> <base>`) on the `next` after a build. Without it, a flow-edit build STOPs. A non-auto session should show the `FLOW-EDIT` line to the user. An after-call STOP is the first line, and the conductor's line may follow it: the skill must stop on the first line and not act on the conductor's.
- 08: `HoleC` in `test_trust_runner.py` is the hole (c) setup. It uses commands.md `Test: \`"<python>" t.py\``.
