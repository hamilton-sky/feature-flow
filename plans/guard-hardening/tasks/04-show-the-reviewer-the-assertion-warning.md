# Pass the assertion warning to the reviewer

Type: task
Status: open
Blocked by: 01
Test first: yes
Floor: allow skip, suppress, threshold

Today `floorguard.run` prints `warning: N assertion line(s) removed, M added...` but `judge_build` drops the guard's output when the guard passes, so nobody sees it. Count only lines of test-looking paths (the `+++`/`---` file in the diff matches the `DELETED_TEST` path idea), so a README edit mentioning `assert` does not count. When the guard passes with a warning, `judge_build` stores the warning line in the run state (`guard_warning`, one line) and `prompts.build` appends it to the reviewer's task text as `The floor guard warns: ...`. It is cleared when the next ticket is picked. It never becomes a finding and the guard's exit code does not change.

## Not in this ticket

- Making fewer assertions a finding: rejected, parametrised tests and consolidation trip it (spec.md § Goal 2).
- The one-diff refactor: ticket 05.

## Done when

- `python3 -m unittest discover -s tests/py -k floorguard` covers: removed asserts in `test_x.py` with none added produces the warning; the same text in `README.md` does not.
- A conductor test (`tests/py/test_conductor.py`): a build whose diff removes an assertion line from a test file reaches `REVIEW`, and `prompt` for that review contains `The floor guard warns`; a build without it has no such text.
- All existing tests still pass.

## Reference

- spec.md § Design (Goal 2)
- feature_flow/floorguard.py (`count_matching`, the end of `run`), feature_flow/conductor.py (`judge_build`), feature_flow/prompts.py (`build`)

## Answer

