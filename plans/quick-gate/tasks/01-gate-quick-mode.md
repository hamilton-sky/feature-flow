# Add a quick mode to the gate that runs Quick in place of Test

Type: task
Floor: allow flow-edit
Status: open
Blocked by: —
Test first: yes

In `feature_flow/gate.py`, give `run` a `quick=False` argument. In quick mode, when `commands.md` has a usable `Quick:` value (non empty, not starting with `<`), the gate runs Build, then Quick in the place of Test, then Lint, and prints `gate: Quick: <cmd>` for it. Without a usable `Quick:` value quick mode runs `Test` exactly as the full mode does. Full mode (the default) is unchanged and never reads `Quick:`. `main` and the command line stay as they are (the standalone `gate.py <feature>` is always the full gate). In `feature_flow/checks.py`, give `gate(scripts, feature, timeout=None, quick=False)` the same argument and pass it on.

Tests in a new `tests/py/test_quick_gate_mode.py`, with a throwaway plan folder whose Build, Test, Quick and Lint commands each append their name to a log file: full mode runs Build, Test, Lint; quick mode runs Build, Quick, Lint; quick mode with no `Quick:` line, or with `Quick: <placeholder>`, runs Build, Test, Lint and a failing Quick fails the gate with the Quick output tail.

## Not in this ticket

- The conductor deciding when to use quick mode: ticket 02.
- `commands.md` template and planner guide: ticket 03.

## Done when

- `python3 -m unittest discover -s tests/py -p "test_quick_gate_mode.py" -v` prints `OK` and lists a test with `placeholder` in its name.
- The whole suite passes: the conductor's gate runs it after the build, so it is not repeated in the check block.

```check
# The conductor runs this block before review.
$ python3 -m unittest discover -s tests/py -p "test_quick_gate_mode.py" -v
prints placeholder
prints OK
```

## Reference

- spec.md § Interfaces, § Edge cases
- `feature_flow/gate.py` (`run`, `main`, `command`), `feature_flow/checks.py` (`gate`), `tests/py/test_gate.py`

## Answer
