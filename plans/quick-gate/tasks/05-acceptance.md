# Acceptance: the quick gate runs on middle tickets and the full gate where it must

Type: task
Status: resolved
Blocked by: 01, 02, 03, 04
Test first: no

Make sure `tests/py/test_quick_gate.py` (ticket 02) is the bar: if ticket 02 left any case in the spec's bar out, add it. Add one drive in `tests/py/test_quick_gate_drive.py`, using `helpers.Repo` and the real `agents/` and `guides/` as `tests/py/test_small_drive.py` does, over a four-ticket plan with `Test` and `Quick` commands that append to a log file, driven with `start`, `next`, `prompt` and `verdict` the way the skill does (set `FLOW_TICKETS_PER_SESSION=99` so no handoff intrudes): tickets 01 to 03 log `quick`, ticket 04 logs `test`, and the drive ends in `DONE`. Run it again with `FLOW_GATE_FULL=1`: every ticket logs `test`.

## Not in this ticket

- A real agent run in Claude Code or Codex: not from the cloud.

## Done when

- `python3 -m unittest discover -s tests/py -p "test_quick_gate_drive.py" -v` prints `OK`.
- `python3 -m unittest discover -s tests/py -p "test_quick_gate.py"` prints `OK`.
- The whole suite passes: the conductor's gate runs it after the build.

```check
# The conductor runs this block before review.
$ python3 -m unittest discover -s tests/py -p "test_quick_gate_drive.py" -v
prints OK
$ python3 -m unittest discover -s tests/py -p "test_quick_gate.py"
prints OK
```

## Reference

- map.md § The bar
- `tests/py/test_small_drive.py`, `tests/py/test_quick_gate.py`

## Answer

**Built**: `tests/py/test_quick_gate_drive.py` (new). Ticket 02's `test_quick_gate.py` already covered every case of the bar (quick on a middle ticket; full on the last, before a handoff, under `FLOW_GATE_FULL=1`, without `Quick:`; also gate off and a failing quick), so I added nothing to it.

**Proof**:
- `python3 -m unittest discover -s tests/py -p "test_quick_gate_drive.py" -v`: 2 tests, `OK` (default drive logged `quick quick quick test`; `FLOW_GATE_FULL=1` logged `test` four times; both end in DONE).
- `python3 -m unittest discover -s tests/py -p "test_quick_gate.py"`: 7 tests, `OK`.
- Whole suite: left to the conductor's gate, as instructed.

**Decisions**: tickets have no check block so each gets the two-review path; the drive loops on REVIEW until DONE rather than counting reviews. Logger script and logs live outside the Repo dir.

**Shortcuts taken**: none.

**For later tickets**: none.
