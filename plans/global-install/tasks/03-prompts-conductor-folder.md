# Point subagent prompts at the conductor that is running

Type: task
Status: resolved
Blocked by: —
Test first: yes

`prompts.build()` and `prompts.plan()` paste guide text that says `python3 scripts/flow-status.py ...`. A builder or reviewer subagent gets only that text, so when the conductor runs from `~/.feature-flow/scripts` and the repo has no `scripts/`, the command fails. In `feature_flow/prompts.py`, after the guide body is read (next to the `<feature>` replacement), rewrite `python3 scripts/` to `python3 <folder>/` where `<folder>` is the absolute, forward-slash path of the `scripts` argument, but only when that folder is not `Path.cwd() / "scripts"` (the repo install keeps its text byte for byte). Put the path in double quotes if it contains a space. Do it once in a small helper used by both functions, and apply it to the role body too (the planner role names `python3 scripts/flow-status.py`).

## Not in this ticket

- The orchestrating session's own commands: the SKILL rule, ticket 05.
- Editing the guides: they keep saying `scripts/`.

## Done when

- `prompts.build("build", <scripts dir elsewhere>, ...)` contains `python3 <that dir>/flow-status.py` and no `python3 scripts/`.
- With `scripts` equal to `Path.cwd() / "scripts"` the output is identical to today's (an equality test against the unrewritten text).
- `python3 -m unittest discover -s tests/py -p "test_units.py"` prints `OK` (add the tests to `tests/py/test_units.py` or a new `tests/py/test_prompts.py`; use whichever pattern matches).
- `python3 -m unittest discover -s tests/py` passes.

```check
$ python3 -m unittest discover -s tests/py
prints OK
```

## Reference

- `feature_flow/prompts.py`: `build`, `plan`, `find_file`
- `tests/py/test_units.py`

## Answer


**Built**: `feature_flow/prompts.py` (new `_runner` helper, applied to role and guide in `build` and `plan`); `tests/py/test_prompts.py` (4 tests, committed first as `262c46f`, 3 failed before the change).

**Proof**:
- `python3 -m unittest discover -s tests/py -p "test_prompts.py"`: Ran 4 tests, OK (covers rewrite in build, rewrite in plan role, quoted path with a space, repo install text kept and no absolute path added).
- `python3 -m unittest discover -s tests/py -p "test_units.py"`: Ran 7 tests, OK.
- `python3 -m unittest discover -s tests/py`: Ran 258 tests, OK.

**Decisions**: the test uses a new file `test_prompts.py` since test_units covers other modules. A path with a space is quoted as `python3 "/a b/scripts"/flow-status.py`, which the shell reads as one word. Only the exact text `python3 scripts/` is rewritten; the task text built by the conductor is untouched.

**Shortcuts taken**: none.

**For later tickets**: the `plan` prompt leaves `<feature>` in the role body unreplaced (as before); the rewrite does not change that.
