# Pass the assertion warning to the reviewer

Type: task
Status: resolved
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


**Built**: `feature_flow/floorguard.py` (`count_assertions` replaces `count_matching`, `ASSERT_REMOVED`/`ASSERT_ADDED` replaced by `ASSERT_LINE`; counts only lines under a `---`/`+++` path matching `DELETED_TEST`), `feature_flow/conductor.py` (`judge_build` stores the guard's first `warning:` line as `guard_warning` when the guard passes; `pick_ticket` clears it; `prompt` passes it for the review phase), `feature_flow/prompts.py` (`build` takes `warning` and appends `The floor guard warns: ...` to the reviewer's task), tests in `tests/py/test_floorguard.py` and `tests/py/test_conductor.py`.

**Proof**:
- `python3 -m unittest discover -s tests/py -k floorguard`: Ran 40 tests, OK (includes removed assert in `test_x.py` warns, same text in `README.md` does not).
- `python3 -m unittest discover -s tests/py -k GuardWarning`: Ran 3 tests, OK (review prompt has `The floor guard warns` with a removed assertion, none without, state cleared when ticket 02 is picked). The conductor test failed first for the right reason (text missing from the prompt).
- `python3 -m unittest discover -s tests/py`: Ran 160 tests, OK. `bash tests/run.sh`: 441 passed, 0 failed, exit 0.

**Decisions**: the warning is read from the guard's output text (first line starting `warning:`), so the guard's output and exit code are unchanged. Only the review prompt gets it, not the build prompt. A deleted test file counts through its `---` path, an added one through `+++`.

**Shortcuts taken**: none.

**For later tickets**: ticket 05 (one-diff refactor) must keep `count_assertions(diff)` returning `(removed, added)` over the same diff, and `guard_warning` in the run state. `prompts.build` has a new optional `warning` argument.
