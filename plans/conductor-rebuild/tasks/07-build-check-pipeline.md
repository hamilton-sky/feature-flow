# Make the build checks an ordered pipeline that batches reuse

Type: task
Status: open
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
