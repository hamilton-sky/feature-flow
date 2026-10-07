# Remove the mawk compatibility code from the floor guard and the gate

Type: task
Status: open
Blocked by: 02, 03, 04
Test first: no
Floor: allow config, skip, suppress

The bash scripts are gone, so simplify `feature_flow/floorguard.py` and `feature_flow/gate.py` to plain Python: drop `_awk_assign`, the byte-oriented lower-casing, `_ascii_lower` and the "parity"/"bash version" wording; handle the diff and `commands.md` as `str` (UTF-8, `errors="surrogateescape"` is fine); the 100 byte cut becomes 100 characters. `floorguard.allow_line` now takes and returns `str`: update its caller added to `feature_flow/conductor.py` in ticket 01. Keep the exit codes (0, 1, 2), the category names, the finding line `category: path: text` and the printed texts, because the conductor and the guides read them. `floorguard.run` runs the `git diff` once and reuses it for the findings and both assertion counts. Update the tests that pin mawk behaviour (`test_escapes_follow_mawk`, `test_text_is_cut_at_100_bytes`, `test_the_value_is_read_like_awk`, and the like) to the plain behaviour; do not delete coverage of exit codes or categories. In `.github/workflows/tests.yml` drop the mawk and gawk matrix entries and the "Select the awk under test" step; keep `jq` (tests/run.sh uses it), one Ubuntu and one macOS job, and the Windows and package jobs unchanged. Keep `tests/run.sh`: it also tests the viewer data, `--json`, the installer and the demo. Add a comment in `tests/run.sh` where it mentions mawk only if the line is now wrong.

## Not in this ticket

- The mawk-era code in `tickets.py`, `status.py`, `view.py`, `install.py`: left alone.
- Timeouts in the gate: ticket 06.
- Porting `tests/run.sh`.

## Done when

- `python3 -m unittest discover -s tests/py && bash tests/run.sh` passes.
- `grep -n "_awk_assign\|_ascii_lower\|parity\|mawk" feature_flow/floorguard.py feature_flow/gate.py` prints nothing.
- `grep -n "mawk\|gawk" .github/workflows/tests.yml` prints nothing, and the file still has the `windows` and `package` jobs.
- `grep -c 'unified=0' feature_flow/floorguard.py` prints `2`: once for the whole diff in `run` and once for the per-file `map.md` and `learnings.md` check (count it before you start and keep the whole-diff call to one; assertion counts reuse it).

## Reference

- spec.md § Design (Goal 3)
- feature_flow/floorguard.py, feature_flow/gate.py, tests/py/test_floorguard.py, tests/py/test_gate.py, .github/workflows/tests.yml, tests/run.sh

## Answer

