# Remove the mawk compatibility code from the floor guard and the gate

Type: task
Status: resolved
Blocked by: 02, 03, 04
Test first: no
Floor: allow config, skip, suppress, threshold

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

**Built**: `feature_flow/floorguard.py` and `feature_flow/gate.py` are plain str Python (no `_awk_assign`, `_ascii_lower`, byte regexes or parity wording). `git` output is decoded once in `_Guard.git` (utf-8, surrogateescape). `allow_line` takes and returns `str`; caller in `feature_flow/conductor.py` updated. `feature_flow/checks.py` `gate()` updated because `gate.run` now writes text. `run` runs the whole `git diff --unified=0` once and reuses it for findings and assertion counts. A small `_file_diff` helper holds the per-file diff (map.md, learnings.md, pyproject/setup.cfg, conftest.py). Tests updated in `tests/py/test_floorguard.py` and `tests/py/test_gate.py`. `.github/workflows/tests.yml`: matrix is now `ubuntu` and `macos`, awk step removed. `tests/run.sh`: the one comment that mentioned mawk reworded.

**Proof**:
- `python3 -m unittest discover -s tests/py && bash tests/run.sh`: 159 tests OK, then `441 passed, 0 failed`, exit 0.
- `grep -n "_awk_assign\|_ascii_lower\|parity\|mawk" feature_flow/floorguard.py feature_flow/gate.py`: no output.
- `grep -n "mawk\|gawk" .github/workflows/tests.yml`: no output; `grep -c "^  windows:\|^  package:"` prints 2.
- `grep -c 'unified=0' feature_flow/floorguard.py`: 2 (it was 5 before: run twice, plus toml, conftest and the map/learnings check).

**Decisions**: `gate.run`'s out and err callbacks now take `str`, not bytes, so `checks.gate` and `test_gate` changed with it. The `unified=0` count of 2 is the whole diff in `run` plus `_file_diff`, which all per-file diffs share. `test_escapes_follow_mawk` was deleted because `_awk_assign` no longer exists. The 100 byte test became a 100 character test, with an `é` on the cut edge.

**Shortcuts taken**: none.

**For later tickets**: `gate.run` and `gate.command` and `gate.tail` use `str` now (ticket 06, timeouts, builds on that). The installed copy under `.feature-flow/` is untouched (it is ticket 08's job to refresh it).
