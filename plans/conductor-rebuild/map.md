# Map: conductor-rebuild

## Destination

`feature_flow/conductor.py` is gone. In its place the package `feature_flow/conductor/` holds a facade under 300 lines for the 17 CLI commands and small modules under 400 lines each: errors, planning (the stateless plan and brainstorm commands), settings (with one table of which modes may run together), store (typed views over the state file), policy (levels, review), buildchecks (the check pipeline), phases (a registry and a transitions table), schedulers (serial, batch, lanes, one end of run), guards and budget, and workspace (in place of `in_lane` and `os.chdir`). Nothing a user, a caller or a test can observe has changed, and a golden test recorded on the old code proves it.

**The bar.** `bash tests/run.sh` prints `N passed, 0 failed` and exits 0, with every existing test unchanged except for the file paths they name (the brief's Decided line), and the golden test matching the recordings ticket 01 made before ticket 03; `python3 -c "import feature_flow.conductor as c; print(c.Conductor, c.Stop, c.NoPhase)"` exits 0; `feature_flow/conductor.py` does not exist; the ratchet test (facade under 300 lines, every package module under 400) passes. Ticket 14 runs it, and the acceptance tests (spec.md § Acceptance tests) prove that a run paused at a `HANDOFF` on the old code resumes on the new.

## How to work this

- See what is ready: `python3 scripts/flow-status.py conductor-rebuild`. Take the lowest numbered READY ticket.
- Claim: set `Status: claimed` in the ticket and save before starting.
- Resolve: write the result under `## Answer`, set `Status: resolved`, then add one line to
  Decisions so far below.
- See the graph: `python3 scripts/flow-status.py conductor-rebuild --mermaid` (coloured by status, drawn on demand).
- Commands live in `commands.md` (frozen). Lessons live in `learnings.md` (append only).
- Status lives only in the ticket files. This map never repeats it.
- The gate runs `bash tests/run.sh` after each ticket (about 10 minutes): while you work, run your own test file and `python3 -m unittest discover -s tests/py -p "test_golden.py"`.
- Never change `tests/py/golden/` after ticket 01: no later ticket lists it under `Touches:`, so the footprint check sends such a build back. A golden mismatch means the move changed behaviour; fix the code, not the recording.
- Every ticket that edits `feature_flow/` carries `Floor: allow flow-edit` (the build guide forbids editing the flow's own code without it), which also makes it level 3.

## Decisions so far

- (plan) The brief carries the design artifact's content under Design (layers, phase and scheduler protocols, the facade's own commands); spec.md copies it, and this plan is the authority for builders. Spec § Decisions has the forks.
- (plan) `pyproject.toml` lists packages by name, so ticket 03 adds `feature_flow.conductor`, `feature_flow.conductor.policy`, `feature_flow.conductor.phases`, `feature_flow.conductor.schedulers` (read from `pyproject.toml` and `tests/package_smoke.py`).
- (plan) `tests/run.sh`'s `flowrepo` copies only `feature_flow/*.py`, and its Python 3.9 parse check reads only `feature_flow/*.py`: the first breaks once the package exists (ticket 03 makes it copy the package folder); the second is covered by ticket 03's new package test.
- (plan) Existing tests that name `feature_flow/conductor.py`: `tests/py/test_trust_drive.py`, `tests/py/test_trust_runner.py` (not its `LinkedFolders` fake file system), `tests/py/test_install.py`, `tests/py/test_state_report.py`. They change only the path they name (brief, Decided, 2026-10-28, option A); spec.md § Decisions, Tests that name `conductor.py`, says which file each points at. Four tests read a source string and follow the module that holds it: the two `PlantedBytecode` tests (`"BUILD %s %s %s%s"`: facade, then `phases/build.py` from ticket 08; `return "OK %s" % token`: facade, `start`, with `PlantedBytecodeCrlf.prepare` always on the same file as `plant`) and the two `check_code` hole tests (`test_trust_drive.py`'s `Holes`, `test_trust_runner.py`'s `test_hole_a_a_committed_return_in_check_code`: the docstring of `check_code`, which stays a facade method).
- (plan) A frozen dataclass raises `dataclasses.FrozenInstanceError`, a subclass of `AttributeError`, on assignment; ticket 04's check proves frozenness that way (its `test_settings_are_frozen`), not through the undocumented `__dataclass_params__`. docs: https://docs.python.org/3.9/library/dataclasses.html
- (plan) `match`/`case` arrived in Python 3.10 (PEP 634), so it is not available on the 3.9 floor. docs: https://docs.python.org/3.10/whatsnew/3.10.html
- (plan) `from __future__ import annotations` works from Python 3.7. docs: https://peps.python.org/pep-0563/

- (brief, corrected) Resume on the new code is required only for a run paused between tickets (at a `HANDOFF`): acceptance A3. A run paused mid-ticket keeps today's behaviour, `Conductor.check_code` stopping it with `flow code changed while building ...` unless the ticket has `Floor: allow flow-edit`; nothing is built for it, and A4 only checks that this STOP is what it meets (read from `feature_flow/conductor.py`, `check_code`, `snapshot_code`).
- (plan) `gate.py`, `floorguard.py` and `status.py` run in process and read the plan folder relative to the working folder, and `floorguard.py` runs git without `cwd`; ticket 13 (after ticket 12, in the brief's order) gives them a `cwd=` keyword before ticket 15 drops `os.chdir`. `tests/py/test_proof.py` patches `proof.test_first` with a five-argument lambda, so `test_first` keeps its signature and takes the folder through `plan_dir` (spec.md § Decisions).
- (plan) Smoke is `tests/run.sh`'s own Python 3.9 parse check; the CI and CONTRIBUTING.md list no faster target.
- (plan) `MODE_RULES` has 6 rows: the `FLOW_LANES` range, lanes with relay (used by `start` and `lane_next`), lanes need the repo top, `FLOW_DRIVER` values, `FLOW_FAST` values, the batch preconditions (read from `start`, `lane_next`, `batch_for`). The `lane(s) ... still hold tickets` STOP in `start` is not a mode rule and stays in `start`.
- (plan) `policy/limits.py` holds `round_cap`, the "limits" policy in the brief's Design layer list (step 4 names only levels and review).

## Open questions

- None.
