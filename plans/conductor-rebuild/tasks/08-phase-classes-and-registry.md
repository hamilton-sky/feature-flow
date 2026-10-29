# Move each phase into a class found through one registry

Type: task
Status: resolved
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

- **Built**:
  - New `feature_flow/conductor/phases/base.py` (82 lines). It holds `Outcome(line, passed)`, a frozen dataclass, and `Phase`, the protocol with its defaults. The defaults are: `name`, `lane_scoped = True`, `who` (what the "has no lane" STOPs call a run-wide phase), `takes_verdict`, `prompt` (raises NoPhase `no BUILD or REVIEW is pending`), `record` (raises NoPhase `no review is pending`), `scout_questions` (returns `[]`) and `key` (the generic scout key). It also holds the shared helpers `read_reply`, `ticket_prompt` and `review_notes`.
  - New `phases/build.py` (87 lines): `Build`, with `hand_out` (it holds the `"BUILD %s %s %s%s"` line), `judge`, `prompt`, `batch_note` and `scout_questions`.
  - New `phases/review.py` (144 lines): `Review`, plus the module functions `take_verdict(ws, what)` and `record_verdict(ws, reply, final=False)`, which the feature review shares. `LEVEL_LINE` moved here.
  - New `phases/ask.py` (211 lines): `Ask`, with `ask_file`, `open_ask`, `hand_out(ws, source, role, question)`, `disputes_tests`, `emit_ask`, `ask_user`, `record`, `record_answer`, `judge`, `prompt` and `scout_questions`. `ASK_HEADING`, `MAX_ASKS` and `RULING` moved here.
  - New `phases/test.py` (90 lines): `Test` (`lane_scoped = False`, `who = "tester"`, `takes_verdict = False`). `record` raises the old "the tester has no verdict" NoPhase. `scout_questions` raises the old "no BUILD or REVIEW is pending" NoPhase, so the tester still gets no scouts.
  - New `phases/final.py` (128 lines): `Final` (`lane_scoped = False`, `who = "feature review"`), with `feature_base`, `hand_out(ws, retry=False)`, `judge`, `fix_ticket`, `prompt`, `final_note`, `record`, `scout_questions` and `key`.
  - `phases/__init__.py`: `REGISTRY` (word to class) and `TRANSITIONS`. The table has the rows `""`, build, review, ask, test, final and merge, and each phase may follow itself where a retry hands it out again.
  - New `feature_flow/conductor/replies.py` (25 lines): `VERDICT`, `ANSWER`, `section_after` and `demote`. They moved here because both the facade's exports and the phases need them, and the phases must not import the facade. The facade imports `demote` and `section_after` back, so `feature_flow.conductor` exports the same objects.
  - `facade.py` went from 1961 to 1408 lines. The moved methods are gone. New `pending()` returns the registry class for this view's phase, or `Phase` when there is none. New `run_wide(command, lane)` returns the run-wide phase and raises the "has no lane" STOP from one place, with today's texts. `next`, `prompt`/`prompt_text`, `verdict`, `scouts`, `scout_prompt`/`scout_questions`, `pending_phase` and `phase_key` now route through these. The internal callers (`send_back`, `pick_ticket`, `check_acceptance`, `dispatch`, `lease`, `refresh`, `rebuild`, `finish`) call `Build`/`Review`/`Test`/`Final.hand_out(self)`. `lane_next` keeps its phase-word test (ticket 10) but judges through `REGISTRY[phase]`.
  - `tests/py/test_trust_drive.py`: only `PlantedBytecode.plant`'s path changed, to `feature_flow/conductor/phases/build.py`. `start`'s `return "OK %s" % token` and `check_code` (same docstring, same indent) are still in facade.py, so `test_trust_runner.py` is unchanged.
  - New `tests/py/test_phases.py` (8 tests). Five static tests: the registry words, each with a `Phase` subclass, a matching `name` and a row in the table; only test and final are run-wide; the table names only its own rows; a walk reaches every phase from `""` and gets back to `""` from each; and the default `record` raises NoPhase, plus `Outcome`'s fields. Three in-process drives on throwaway repos: serial with a builder's ask, a send-back, a reviewer's ask and two tickets; fast mode with the tester and the feature review; and a lane ticket through its merge. The drives patch `RunState.save` to record every saved phase change, per slot (`phase` and `L1..L4.phase`), and wrap each registry class's `hand_out`. They assert that every change, and every hand-out, sets a phase the table allows after the one before, and that the hand-out sets its own word.
  - Test-only commit 07f701b: the discover command failed with `ImportError: cannot import name 'REGISTRY' from 'feature_flow.conductor.phases'`. After that commit I corrected two expectations in my own new test. They were wrong about today's review policy: a level 2 ticket gets one single review unless it has `Review: full`. The serial tickets now carry `Review: full`, and the lane drive expects one review. No assertion was dropped.
- **Proof**:
  - `python3 -m unittest discover -s tests/py -p "test_phases.py" -v`: `Ran 8 tests`, `OK`.
  - The registry check printed `['ask', 'build', 'final', 'review', 'test']`.
  - The BUILD check printed `BUILD line True`. facade.py has 0 copies of the line and phases/build.py has 1.
  - The 400-line check printed `over 400: []` and exited 0. The largest module besides the facade is planning.py (215), then phases/ask.py (211).
  - `bash tests/run.sh`: `466 passed, 0 failed`, exit 0. The run includes `python3 -m unittest discover -s tests/py passes`, the import-list check and the 3.9 parse. I also ran these together: test_golden, test_ask_drive, test_tester_drive, test_scouts_drive, test_proof, test_trust_drive, test_trust_runner, test_conductor_package, test_lanes_drive, test_fast_drive, test_batch_drive, test_review_pass, test_levels_drive, test_conductor and test_phases. Result: `Ran 243 tests`, `OK`. Of those, only test_trust_drive.py changed, and only its one path.
  - Acceptance `test_rebuild_maintainer ... test_each_phase_is_a_class_in_phases_found_through_one_registry` now passes.
- **Decisions**:
  - Phase methods are classmethods, so `REGISTRY[word]` is the class itself, as the acceptance test wants (`inspect.isclass`). They are called as `Build.hand_out(ws)`, with no instances. Phases reach each other through module imports (`from feature_flow.conductor.phases import ask as ask_phase`). That is safe in a cycle on Python 3.7+ because the attribute is read at call time.
  - The hand-outs keep their extra arguments: `Ask.hand_out(ws, source, role, question)`, and `Test`/`Final.hand_out(ws, retry=False)`.
  - `Outcome.passed` is True only where the old code called `pass_ticket`, through `defer_review`, a review pass, or `pass_with_followups`. It is False for a batch (`judge_batch` counts its own tickets), the tester and the feature review, since those are no ticket. Nothing reads it yet. Ticket 09's schedulers may.
  - `verdict` on a run-wide phase does this: if `takes_verdict` (final), it checks the lane and clears `findings_for`. Then it calls `record`. So the tester's NoPhase still comes before any lane STOP, as before.
  - `scouts` keeps its NoPhase for phases outside the registry (`""`, merge). The tester's NoPhase comes from `Test.scout_questions`, which runs before anything is cleared or saved, so the order of effects is the same.
  - `edit_retry`, `undo_edit`, `scout_findings`, `pass_ticket`, `send_back`, `judge_batch` and the acceptance helpers stay on the facade. The ticket did not list them, and they are shared or belong to tickets 09 and 10.
- **Shortcuts taken**: until ticket 12, `ws` is the Conductor, so phases read `ws.st`, `ws.all` and `ws.lane` directly. Ticket 12 replaces that with the Workspace.
- **For later tickets**:
  - Ticket 09: `Test.judge` and `Final.judge` still end with `ws.dispatch() if ws.num("lanes") > 1 else ws.pick_ticket()`, in phases/test.py and phases/final.py, not in the facade.
  - Ticket 10: the merge phase class goes into `REGISTRY`, and `TRANSITIONS` already has its row. The `lane_next` phase-word test is the one place left.
  - Ticket 12: phases use `ws.st`, `ws.all`, `ws.lane`, `Path.cwd()` (the lane workdir in `ticket_prompt` and `Ask.prompt`), and these Conductor methods: `count_run`, `save`, `log`, `emit`, `check_code`, `undo_edit`, `edit_retry`, `scout_findings`, `pass_ticket`, `send_back`, `defer_review`, `judge_batch`, `measure_level`, `small_note`, `ticket_at_base`, `flow_edit_allowed`, `snapshot_code`, `deferred`, `write_due`, `add_due`, `acceptance_folder`, `acceptance_command`, `run_acceptance`, `dispatch` and `pick_ticket`.
  - The `"BUILD %s %s %s%s"` line now lives in phases/build.py.
