# Make the build checks an ordered pipeline that batches reuse

Type: task
Status: resolved
Blocked by: 06
Test first: yes
Level: 3
Floor: allow flow-edit
Touches: feature_flow/conductor/, tests/py/test_buildchecks.py, tests/py/test_trust_drive.py, tests/py/test_trust_runner.py

Step 5 of the design. Add `feature_flow/conductor/buildchecks.py` (new): check classes `Gate`, `FloorGuard`, `Footprint`, `DoneWhen` and `TestFirst`, each running what `build_checks`, `footprint_report`, `run_done_when` and `run_test_first` run now, with the same log events (`GATE-QUICK`/`GATE-FULL`, `GATE-PASS`/`GATE-FAIL`, `GUARD-PASS`/`GUARD-FAIL`, `FOOTPRINT-PASS`/`FOOTPRINT-FAIL`, `DONEWHEN-*`, `TESTFIRST-*`), the same failure sources (`gate (quick)`, `gate (full)`, `floor guard`, `footprint check`, `done when`, `test first`), the same reports and notes, and the same side effects (`checks_ran`, `due_checks`, the `restore` key saved during test first). A pipeline runs them in that order and stops at the first failure, returning `(source, report, notes)` as `build_checks` does; `DoneWhen` and `TestFirst` run only with the gate on, as now. `judge_build` runs the whole pipeline; `judge_batch` runs it without `Gate` (its gate runs once at HEAD, as now).

Add `tests/py/test_buildchecks.py` (new): with stub checks, the order, stop at the first failure, the notes collected from passing checks, and the batch pipeline without the gate; plus one test per real check class against a throwaway repo where that is quick.

Four existing tests read a source string from the file that holds it (spec.md § Decisions, Tests that name `conductor.py`): `"BUILD %s %s %s%s"` (`tests/py/test_trust_drive.py`'s `PlantedBytecode`), `return "OK %s" % token` in `start` (`tests/py/test_trust_runner.py`'s `PlantedBytecode.plant`, with `PlantedBytecodeCrlf.prepare` always on the same file), and `check_code`'s docstring (`tests/py/test_trust_drive.py`'s `Holes.test_a_builder_commit_that_makes_check_code_return_early` and `tests/py/test_trust_runner.py`'s `test_hole_a_a_committed_return_in_check_code`). `start`'s line and `check_code` (a `Conductor` method, same docstring, same indent) stay in `facade.py`. If this ticket moves any of these strings anyway, point every test that reads it at the new file in the same commit, and change nothing else in those tests (brief, Decided).

## Not in this ticket

- The level and review decisions that follow green checks: ticket 06 made them.
- Moving `judge_batch` itself into a scheduler: ticket 09.

## Done when

- `python3 -m unittest discover -s tests/py -p "test_buildchecks.py" -v` prints `OK`.
- The five check classes exist (the check below prints their names).
- No module of the package other than `facade.py` reaches 400 lines.
- `bash tests/run.sh` passes, including `tests/py/test_proof.py`, `tests/py/test_batch_drive.py` and `test_golden.py` unchanged (the gate runs it).

```check
# The conductor runs this block before review.
$ python3 -m unittest discover -s tests/py -p "test_buildchecks.py" -v
prints OK
$ python3 -c "from feature_flow.conductor import buildchecks as b; print([c.__name__ for c in (b.Gate, b.FloorGuard, b.Footprint, b.DoneWhen, b.TestFirst)])"
prints 'TestFirst'
$ python3 -c "import pathlib,sys; big=[(str(p), n) for p in pathlib.Path('feature_flow/conductor').rglob('*.py') for n in [len(p.read_text(encoding='utf-8').splitlines())] if p.name != 'facade.py' and n >= 400]; print('over 400:', big); sys.exit(1 if big else 0)"
prints over 400: []
```

## Reference

- spec.md § Interfaces (`buildchecks.py`), § Edge cases (a batch)
- the facade: `build_checks`, `footprint_report`, `run_done_when`, `run_test_first`, `judge_build`, `judge_batch`
- `feature_flow/checks.py`, `feature_flow/proof.py`

## Answer

- **Built**:
  - New `feature_flow/conductor/buildchecks.py` (133 lines): classes `Gate`, `FloorGuard`, `Footprint`, `DoneWhen`, `TestFirst`. Each has `run(c)`, which takes the conductor and returns `(source or None, report, notes)`. `pipeline(c, gate=True)` builds the ordered list: `Gate` only when `gate and c.gate_on`, then `FloorGuard` and `Footprint`, then `DoneWhen` and `TestFirst` only when `c.gate_on`. `run(c, checks)` stops at the first failure with `(source, report, [])`, or returns `(None, "", notes)`. The bodies are the old `build_checks`, `footprint_report`, `run_done_when` and `run_test_first`, with the same log events, sources, report and note texts, and Stop messages. The side effects are also the same: `c.checks_ran`, `c.st["due_checks"]`, and `c.st["restore"]` with `c.save()` through `remember`.
  - `feature_flow/conductor/facade.py` (2058 to 1961 lines): the four methods are removed. `judge_build` calls `buildchecks.run(self, buildchecks.pipeline(self))`. `judge_batch` calls `buildchecks.run(self, buildchecks.pipeline(self, gate=False))`, and its own gate at HEAD is unchanged. `NOTE_SEP` is now imported from `store`.
  - `feature_flow/conductor/store.py`: `NOTE_SEP` moved here (the state-file format) so that `buildchecks` does not import the facade.
  - New `tests/py/test_buildchecks.py` (17 tests). Five pipeline tests use stub checks: the order with notes collected, the stop at the first failure, the full pipeline, the batch pipeline without `Gate`, and gate-off. Twelve tests run the real classes against a throwaway `helpers.Repo` through a small `Handle` fake of the conductor: `Gate` full fail and quick pass; `FloorGuard` pass, and fail on an edit to another ticket; `Footprint` pass, fail, and no Touches line; `DoneWhen` pass, fail, skip, deferred (`due_checks`), and the dirty-tree Stop; `TestFirst` pass (restore saved, then cleared), off, skip, and fail; and the pipeline stopping at the footprint before Done when.
  - Test-only commit 9d75274: the discover command failed with `ImportError: cannot import name 'buildchecks' from 'feature_flow.conductor'`. After that commit I changed one helper in the test file: `base()` commits only when the tree has changes. Without that fix, three tests crashed on an empty `git commit`. No assertion changed.
- **Proof**:
  - `python3 -m unittest discover -s tests/py -p "test_buildchecks.py" -v`: `Ran 17 tests`, `OK`, exit 0.
  - The class check printed `['Gate', 'FloorGuard', 'Footprint', 'DoneWhen', 'TestFirst']`, exit 0.
  - The 400-line check printed `over 400: []`, exit 0. buildchecks.py has 133 lines and store.py has 91.
  - `bash tests/run.sh`: `466 passed, 0 failed`, exit 0. I also ran these alone, and each printed OK: test_golden, test_proof, test_batch_drive, test_lanes_drive, test_policy, test_trust_drive, test_trust_runner, test_conductor_package. None of those test files changed.
- **Decisions**:
  - The checks take the conductor as a plain handle (`c`) and use only these attributes: `scripts`, `feature`, `plan`, `commands`, `gate_timeout`, `gate_on`, `checks_ran`, `st`, `get`, `log`, `save`, `ticket_name`, `ticket_at_base`, `gate_quick`. That is why a small fake works in the tests.
  - Each check returns a list of notes. `FloorGuard` returns its first `warning:` line, `DoneWhen` always returns its one note, and `TestFirst` returns its note only when it is non-empty. This is exactly the old `notes.append` / `if note` behaviour.
  - `pipeline` and `run` are module functions, not a Pipeline class. The batch passes `gate=False`, and ticket 09's `BatchScheduler` can call it the same way.
  - None of the four source strings moved (`"BUILD %s %s %s%s"`, `return "OK %s" % token`, and the `check_code` docstring are still in facade.py), so `test_trust_drive.py` and `test_trust_runner.py` are unchanged.
- **Shortcuts taken**: none.
- **For later tickets**: ticket 08/09: `judge_build` and `judge_batch` now call `buildchecks.run(self, buildchecks.pipeline(self[, gate=False]))`, and `build_checks`, `footprint_report`, `run_done_when` and `run_test_first` no longer exist on `Conductor`. Import `NOTE_SEP` from `feature_flow.conductor.store`. The facade still re-exports it by import.
