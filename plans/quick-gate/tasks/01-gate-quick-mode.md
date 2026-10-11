# Add a quick mode to the gate that runs Quick in place of Test

Type: task
Floor: allow flow-edit
Status: resolved
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

**Built**: `feature_flow/gate.py` (`run(..., quick=False)`), `feature_flow/checks.py` (`gate(..., quick=False)` passes it on), new `tests/py/test_quick_gate_mode.py` (7 tests). Test-only commit came first.

**Proof**: `python3 -m unittest discover -s tests/py -p "test_quick_gate_mode.py" -v` ran 7 tests, listed `test_quick_mode_with_a_placeholder_runs_test`, printed OK. Before the code it failed with 7 errors (no `quick` argument). `test_gate.py` still passes (11 tests, OK). The full suite is left to the conductor's gate.

**Decisions**: in quick mode the Quick command replaces the Test slot inside the existing loop, so order stays Build, Quick, Lint. It also runs when Test is empty. Full mode never reads `Quick:`.

**Shortcuts taken**: none.

**For later tickets**: the failing Quick output uses the same format as the others: `gate: Quick failed. the last lines of its output:`.

## Review findings (round 1, floor guard)

floor guard: the diff weakens the bar instead of meeting it
skip: tests/py/test_quick_gate_mode.py: @unittest.skipUnless(shutil.which("bash") and os.name != "nt",
if a finding is intended, the ticket needs a line like: Floor: allow <category>

## Answer (round 2)

**Built**: `tests/py/test_quick_gate_mode.py` only. The `skipUnless` decorator and the `shutil` import are gone. The throwaway Build, Test, Quick and Lint commands now run a small `logger.py` written into the temp plan folder: `"<sys.executable>" logger.py <Name>`. It uses double quotes only and no shell operators, so it parses the same under bash and cmd.exe. A failing Quick passes a second argument, which makes the script write `quick broke` to stderr and exit 3. Same 7 tests, including `test_quick_mode_with_a_placeholder_runs_test`. No skip anywhere.

**Proof**: `python3 -m unittest discover -s tests/py -p "test_quick_gate_mode.py" -v` ran 7 tests, all ok, listed the placeholder test, printed OK, exit 0. `grep -n "skip\|shutil"` on the file finds nothing.

**Decisions**: a helper script rather than `python -c "..."` inline, because inline code needs nested quotes that differ between bash and cmd.exe. I could not run it on Windows here; it is written to parse under cmd.exe but only the Linux run is proven.

**Shortcuts taken**: none.

**Review fixes**: floor guard finding (skip in the test file): removed the skip and made the commands portable instead of bash only.

**For later tickets**: none new.
