# Move each phase into a class found through one registry

Type: task
Status: open
Blocked by: 07
Test first: yes
Level: 3
Floor: allow flow-edit
Touches: feature_flow/conductor/, tests/py/test_phases.py, tests/py/test_trust_drive.py, tests/py/test_trust_runner.py

Step 6 of the design. In `feature_flow/conductor/phases/` (made in ticket 03), one class per phase, each owning its hand-out, its judging, its prompt, its verdict handling and its scout questions:

- `Build`, in `feature_flow/conductor/phases/build.py` (new): `hand_out_build` (with its `"BUILD %s %s %s%s"` line), `judge_build`, the build prompt (with the batch note). Point `tests/py/test_trust_drive.py`'s `PlantedBytecode` at `feature_flow/conductor/phases/build.py`.
- `Review`: `hand_out_review`, `judge_review`, `take_verdict`, `record_verdict`, the review prompts.
- `Ask`: `hand_out_ask`, `judge_ask`, `ask_prompt`, `record_answer`, `emit_ask`, `ask_user`, `open_ask`, `ask_file`, `disputes_tests`.
- `Test`: `hand_out_test`, `judge_test`, `test_prompt`.
- `Final`: `hand_out_final`, `judge_final`, `final_prompt`, `final_note`, `feature_base`, `fix_ticket`.

Each class follows the phase protocol of spec.md § Interfaces (`name`, `lane_scoped`, `hand_out(ws)`, `judge(ws) -> Outcome`, `prompt(ws)`, `record(ws, reply)` with a default that raises `NoPhase`, `scout_questions(ws)`, `key(ws)`), with `Outcome(line, passed)`. There is no Workspace yet: until ticket 12, the facade passes itself as `ws`.

`REGISTRY` maps the phase word (`build`, `review`, `ask`, `test`, `final`) to its class. `TRANSITIONS` is a table of which phase may follow which (with `""` for between tickets and `merge` for a lane ticket waiting for its merge). `next`, `prompt`, `verdict`, `scouts`, `scout_prompt`, `pending_phase` and `phase_key` look the pending phase up in the registry instead of testing the phase word; the run-wide phases (`test`, `final`) say so through `lane_scoped = False`, so the "has no lane" STOPs come from one place with today's texts. Phases call back into the Conductor for `check_code` (so `tests/py/test_proof.py`'s patch still works), `count_run`, `save`, `log` and `emit`.

Add `tests/py/test_phases.py` (new): every registry word has a class and is in `TRANSITIONS`; a walk of `TRANSITIONS` reaches every phase from `""` and gets back to `""` from each; each phase's hand-out sets a phase the table allows after the one before (driven on a throwaway repo, or checked against the golden logs).

Four existing tests read a source string from the file that holds it (spec.md § Decisions, Tests that name `conductor.py`): `"BUILD %s %s %s%s"` (`tests/py/test_trust_drive.py`'s `PlantedBytecode`), `return "OK %s" % token` in `start` (`tests/py/test_trust_runner.py`'s `PlantedBytecode.plant`, with `PlantedBytecodeCrlf.prepare` always on the same file), and `check_code`'s docstring (`tests/py/test_trust_drive.py`'s `Holes.test_a_builder_commit_that_makes_check_code_return_early` and `tests/py/test_trust_runner.py`'s `test_hole_a_a_committed_return_in_check_code`). `start`'s line and `check_code` (a `Conductor` method, same docstring, same indent) stay in `facade.py`. If this ticket moves any of these strings anyway, point every test that reads it at the new file in the same commit, and change nothing else in those tests (brief, Decided).

## Not in this ticket

- `dispatch() if lanes else pick_ticket()` and the end of a run: ticket 09. Lanes, `lane_next` and the merge phase: ticket 10. Those may still test the phase word here.

## Done when

- `python3 -m unittest discover -s tests/py -p "test_phases.py" -v` prints `OK`.
- The registry holds the five phases (the check below prints them).
- `feature_flow/conductor/phases/build.py` (new) holds the build hand-out line that `PlantedBytecode` reads (the check below prints `BUILD line True`).
- No module of the package other than `facade.py` reaches 400 lines.
- `bash tests/run.sh` passes, including `tests/py/test_ask_drive.py`, `tests/py/test_tester_drive.py`, `tests/py/test_scouts_drive.py` and `test_golden.py` unchanged (the gate runs it).

```check
# The conductor runs this block before review.
$ python3 -m unittest discover -s tests/py -p "test_phases.py" -v
prints OK
$ python3 -c "from feature_flow.conductor.phases import REGISTRY, TRANSITIONS; print(sorted(REGISTRY))"
prints ['ask', 'build', 'final', 'review', 'test']
$ python3 -c "import pathlib; print('BUILD line', b'\"BUILD %s %s %s%s\"' in pathlib.Path('feature_flow/conductor/phases/build.py').read_bytes())"
prints BUILD line True
$ python3 -c "import pathlib,sys; big=[(str(p), n) for p in pathlib.Path('feature_flow/conductor').rglob('*.py') for n in [len(p.read_text(encoding='utf-8').splitlines())] if p.name != 'facade.py' and n >= 400]; print('over 400:', big); sys.exit(1 if big else 0)"
prints over 400: []
```

## Reference

- spec.md § Interfaces (`phases/`, the compatibility seam), § Stories (a maintainer adds a mode)
- the facade: `next`, `prompt`, `prompt_text`, `verdict`, `record_verdict`, `scouts`, `scout_prompt`, `scout_questions`, `pending_phase`, `phase_key`, and the methods listed above

## Answer
