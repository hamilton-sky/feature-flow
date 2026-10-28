# Move lanes into a LaneScheduler with a merge phase

Type: task
Status: open
Blocked by: 09
Test first: yes
Level: 3
Floor: allow flow-edit
Touches: feature_flow/conductor/, tests/py/test_schedulers.py, tests/py/test_trust_drive.py, tests/py/test_trust_runner.py

Step 7 of the design, lanes last. Add `LaneScheduler` to `feature_flow/conductor/schedulers/`: `lane_next`, `dispatch`, `busy_lanes`, `lane_key`, `lane_number`, `lane_dir`, `footprint`, `lease`, `make_worktree`, `integrate`, `merge_in_place`, `refresh`, `rebuild`, `finish` (through ticket 09's `EndOfRun`) and `drop_lanes` (which `reset` calls). A merge phase class (the phase protocol, `lane_scoped` True) holds the `merge` step of a passed lane ticket, and `REGISTRY` gains `merge`; `LaneScheduler.on_passed` queues the merge. The facade picks `LaneScheduler` when the run has lanes, once per call, so `num("lanes") > 1` is decided in one place; the lane checks of `next`, `prompt`, `verdict` and `scouts` with and without a lane argument keep today's STOP texts.

`in_lane` and its `os.chdir` stay as they are here; ticket 12 replaces them.

Extend `tests/py/test_schedulers.py`: which ready ticket `dispatch` leases beside busy lanes (by `Touches:`, `Shared:` and level), `WAIT` with busy lanes when the session is full, and the merge order (a passed lane merges before a new lease).

Four existing tests read a source string from the file that holds it (spec.md § Decisions, Tests that name `conductor.py`): `"BUILD %s %s %s%s"` (`tests/py/test_trust_drive.py`'s `PlantedBytecode`), `return "OK %s" % token` in `start` (`tests/py/test_trust_runner.py`'s `PlantedBytecode.plant`, with `PlantedBytecodeCrlf.prepare` always on the same file), and `check_code`'s docstring (`tests/py/test_trust_drive.py`'s `Holes.test_a_builder_commit_that_makes_check_code_return_early` and `tests/py/test_trust_runner.py`'s `test_hole_a_a_committed_return_in_check_code`). `start`'s line and `check_code` (a `Conductor` method, same docstring, same indent) stay in `facade.py`. If this ticket moves any of these strings anyway, point every test that reads it at the new file in the same commit, and change nothing else in those tests (brief, Decided).

## Not in this ticket

- The Workspace in place of `in_lane`, and `cwd=` in place of `os.chdir`: tickets 12 and 15.
- `lanes.py`'s git and path helpers: unchanged.

## Done when

- `python3 -m unittest discover -s tests/py -p "test_schedulers.py" -v` prints `OK`.
- The lane test `num("lanes") > 1` is written in at most one package file (the check below prints `lane tests 1` or `0`), and `facade.py` no longer tests the phase word (the second check prints `phase tests in the facade: 0`).
- No module of the package other than `facade.py` reaches 400 lines.
- `REGISTRY` holds `merge` (the check below prints `merge True`).
- `bash tests/run.sh` passes, including `tests/py/test_lanes_drive.py`, `tests/py/test_lanes.py` and `test_golden.py`'s lane scenarios unchanged (the gate runs it).

```check
# The conductor runs this block before review.
$ python3 -m unittest discover -s tests/py -p "test_schedulers.py" -v
prints OK
$ python3 -c "import sys; from feature_flow.conductor.phases import REGISTRY; print('merge', 'merge' in REGISTRY); sys.exit(0 if 'merge' in REGISTRY else 1)"
prints merge True
$ python3 -c "import pathlib,sys; n=sum(p.read_text(encoding='utf-8').count('(\"lanes\") > 1') for p in pathlib.Path('feature_flow/conductor').rglob('*.py')); print('lane tests', n); sys.exit(1 if n > 1 else 0)"
prints lane tests
$ python3 -c "import re,pathlib,sys; t=pathlib.Path('feature_flow/conductor/facade.py').read_text(encoding='utf-8'); n=len(re.findall(r'phase\W{0,3}\s(?:==|!=|in)\s', t)); print('phase tests in the facade:', n); sys.exit(1 if n else 0)"
prints phase tests in the facade: 0
$ python3 -c "import pathlib,sys; big=[(str(p), n) for p in pathlib.Path('feature_flow/conductor').rglob('*.py') for n in [len(p.read_text(encoding='utf-8').splitlines())] if p.name != 'facade.py' and n >= 400]; print('over 400:', big); sys.exit(1 if big else 0)"
prints over 400: []
```

## Reference

- spec.md § Interfaces (`schedulers/`), § Edge cases (a level 3 lane ticket behind the feature head; `pick_ticket` and `dispatch` at the end)
- the facade: the lanes section (`lane_word` to `drop_lanes`), `next`, `prompt`, `verdict`, `pending_phase`, `reset`
- `feature_flow/lanes.py`, `tests/py/test_lanes_drive.py`

## Answer

## Attempt note

Attempt from commit 5097b00eefaa7c166a6089744b64dcc7dbc40f73, stopped before any code changed, because the ticket cannot be done inside its `Touches:`.

- **What fails**: Done when needs `merge` in `REGISTRY`, and `bash tests/run.sh` must pass. But `tests/py/test_phases.py` (ticket 08's test, not in this ticket's `Touches:`) pins the registry to five words: `WORDS = ("build", "review", "ask", "test", "final")` (line 25), and `Registry.test_every_registry_word_has_a_class_and_a_row_in_the_table` asserts `sorted(REGISTRY) == sorted(WORDS)` (line 51). I proved this by adding a `Merge(Phase)` with `name = "merge"` to `REGISTRY` in process and running `test_phases.Registry`. It failed with `AssertionError: Lists differ: ['ask', 'build', 'final', 'merge', 'review', 'test'] != ['ask', 'build', 'final', 'review', 'test']` (`Ran 5 tests`, `FAILED (failures=1)`). So the two Done when bullets "REGISTRY holds merge" and "`bash tests/run.sh` passes" cannot both hold unless `tests/py/test_phases.py` changes, and the footprint check sends back a change to it.
- **A second, smaller trap in the same file**: `Session.call` wraps the `hand_out` of every `REGISTRY` class, and `Walks.test_a_lane_ticket_waits_for_its_merge` ends with `s.check(["build", "review"])`. If the merge phase is ever handed out through `Merge.hand_out`, that test would also see `merge` in its hand-out set. A Merge class that `on_passed` queues by setting the phase word, without calling `hand_out`, avoids this one. Only line 25/51 really blocks.
- **What is needed**, one of:
  1. Widen this ticket's `Touches:` with `tests/py/test_phases.py`, and allow one change there: add `"merge"` to `WORDS` at line 25. Then line 60 (`only test and final are run-wide`) still holds, because Merge is `lane_scoped`. This is the smallest change, and it matches spec.md § Interfaces (`phases/`: "... and merge (ticket 10)").
  2. Add a small ticket before this one, blocked on nothing and touching only `tests/py/test_phases.py`, that adds `"merge"` to `WORDS`. Block 10 on it. (On its own it would fail until 10 lands, so option 1 is cleaner.)
  3. Drop "`REGISTRY` holds `merge`" from Done when, and keep the merge step in `LaneScheduler` only. This goes against spec.md § Interfaces and the acceptance intent.
- Nothing else was changed. The rest of the plan reads as doable inside `Touches:`. The leads for the next attempt: `("lanes") > 1` appears 5 times in facade.py (lines 557, 593, 699, 736, 798). The phase-word regex matches facade.py lines 828, 871, 877 and 885, all in the lane section that moves. Ticket 09's `FacadeLanes` is to be replaced outright.
