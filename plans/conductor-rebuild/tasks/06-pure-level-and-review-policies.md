# Pull the level rules and the review decisions into pure policy functions

Type: task
Status: open
Blocked by: 05
Test first: yes
Level: 3
Floor: allow flow-edit
Touches: feature_flow/conductor/, tests/py/test_policy.py, tests/py/test_trust_drive.py, tests/py/test_trust_runner.py

Step 4 of the design. Three modules in `feature_flow/conductor/policy/`, pure (no git, no state, no files, no `os`): they take values and return values, and the facade does the reading, logging and saving.

- `policy/levels.py` (new), with `declared`, `measured` and `describe` as spec.md § Interfaces gives them: one rule set behind today's `base_level`, `measure_level` and `footprint`'s level. The declared level from the ticket text, raised to 3 by `Review: full`, `Type: convert` or `Floor: allow flow-edit`; raised from the diff by a `Sensitive:` path (to 3) or a level 1 diff over the small limits (to 2); never lowered; each with the same reason text (`describe_level`, `LEVEL_NAMES`). The caller passes whether flow-edit is allowed, read as today: `base_level` from the committed ticket at base (`flow_edit_allowed`), `footprint` from the text at HEAD.
- `policy/review.py` (new), with `after_checks` and `on_fail` as spec.md § Interfaces gives them: the decision tree of `judge_build` after green checks (defer in fast mode below level 3 with the gate on; the small single pass at level 0; the single pass at level 1 to 3 unless `Review: full`; quality only when the spec pass passed earlier; the round note at level 2 past `FULL_ROUNDS`) and the FAIL branch of `judge_review` (pass with follow-ups at level 2 past `FULL_ROUNDS` outside the spec pass when `followups_only`, else send back). It returns the decision, the review pass and the notes; the facade logs `REVIEW-SMALL`, `REVIEW-SINGLE` and the rest as now.

- `policy/limits.py` (new), with `round_cap(level, max_rounds)`: today's `round_cap` (`min(1, max_rounds)` at level 1, else `max_rounds`), the "limits" policy of the brief's Design.

Add `tests/py/test_policy.py` (new) with table tests: one row per rule and per branch, each with the inputs and the expected level and reason, or decision, pass and notes.

Four existing tests read a source string from the file that holds it (spec.md § Decisions, Tests that name `conductor.py`): `"BUILD %s %s %s%s"` (`tests/py/test_trust_drive.py`'s `PlantedBytecode`), `return "OK %s" % token` in `start` (`tests/py/test_trust_runner.py`'s `PlantedBytecode.plant`, with `PlantedBytecodeCrlf.prepare` always on the same file), and `check_code`'s docstring (`tests/py/test_trust_drive.py`'s `Holes.test_a_builder_commit_that_makes_check_code_return_early` and `tests/py/test_trust_runner.py`'s `test_hole_a_a_committed_return_in_check_code`). `start`'s line and `check_code` (a `Conductor` method, same docstring, same indent) stay in `facade.py`. If this ticket moves any of these strings anyway, point every test that reads it at the new file in the same commit, and change nothing else in those tests (brief, Decided).

## Not in this ticket

- Running the checks (gate, floor guard, footprint, Done when, test first): ticket 07.
- `followups_only` keeps its name and module export for `tests/py/test_levels.py`; it may move into the new review policy module as long as `feature_flow.conductor.followups_only` still imports.

## Done when

- `python3 -m unittest discover -s tests/py -p "test_policy.py" -v` prints `OK`.
- The six functions exist under those names (the check below prints `policy ok`).
- The three policy modules hold no reference to `git`, `checks`, `state`, `codehash`, `os` or `subprocess` (the check below prints `impure []`).
- No module of the package other than `facade.py` reaches 400 lines.
- `bash tests/run.sh` passes, including `tests/py/test_levels.py`, `tests/py/test_levels_drive.py` and `test_golden.py` unchanged (the gate runs it).

```check
# The conductor runs this block before review.
$ python3 -m unittest discover -s tests/py -p "test_policy.py" -v
prints OK
$ python3 -c "from feature_flow.conductor.policy.levels import declared, measured, describe; from feature_flow.conductor.policy.review import after_checks, on_fail; from feature_flow.conductor.policy.limits import round_cap; print('policy ok')"
prints policy ok
$ python3 -c "import types,sys; import feature_flow.conductor.policy.levels as a, feature_flow.conductor.policy.review as b, feature_flow.conductor.policy.limits as l; bad=[k for m in (a, b, l) for k, v in vars(m).items() if isinstance(v, types.ModuleType) and v.__name__.split('.')[-1] in ('git', 'checks', 'state', 'codehash', 'os', 'subprocess')]; print('impure', bad); sys.exit(1 if bad else 0)"
prints impure []
$ python3 -c "import pathlib,sys; big=[(str(p), n) for p in pathlib.Path('feature_flow/conductor').rglob('*.py') for n in [len(p.read_text(encoding='utf-8').splitlines())] if p.name != 'facade.py' and n >= 400]; print('over 400:', big); sys.exit(1 if big else 0)"
prints over 400: []
```

## Reference

- spec.md § Interfaces (the three policy modules), § Edge cases (a ticket not yet committed at its base; level 2 past FULL_ROUNDS)
- the facade: `base_level`, `measure_level`, `describe_level`, `footprint`, `small_note`, `judge_build`, `judge_review`, `round_cap`, `followups_only`
- `feature_flow/proof.py` (`declared_level`, `review_mode`), `tests/py/test_levels.py`

## Answer
