# Run on Windows in CI and prove the bar

Type: task
Status: resolved
Blocked by: 07
Test first: no
Floor: allow config

Add a `windows-latest` job to `.github/workflows/tests.yml`. It runs `python -m unittest discover -s tests/py` and a fixture drive: create a temp git repo with a two-ticket plan whose `commands.md` uses a command that works on Windows, run `python scripts/flow.py f start`, then `next` with the token, and require `BUILD`; resolve and commit the ticket, run `next` again, and require `REVIEW`. Add the same unit-test step and fixture drive to the Ubuntu and macOS jobs, next to `bash tests/run.sh`. Put the fixture drive in a Python file under `tests/py/` so all three jobs run the same code.

## Not in this ticket

- Running `tests/run.sh` on Windows; it stays a bash harness for Linux and macOS.

## Done when

- `.github/workflows/tests.yml` has a `windows-latest` job, and `grep -c 'unittest discover' .github/workflows/tests.yml` is at least 3.
- The PR's CI is green on all four jobs; paste the four job names and conclusions into the Answer.
- `ls scripts/*.sh 2>/dev/null` prints nothing and `bash tests/run.sh` exits 0.

## Reference

- .github/workflows/tests.yml
- plans/interactive-flow-python/map.md § Destination (the bar)

## Answer

Added a `windows with python` job to `.github/workflows/tests.yml` that runs `python -m unittest discover -s tests/py -v`, and the same unit-test step to the Ubuntu and macOS matrix job. The fixture drive is `tests/py/test_fixture_drive.py`: it builds a temp git repo with a two-ticket plan, runs `python scripts/flow.py f start`, then `next` with the token (`BUILD`), resolves and commits the ticket, and `next` again (`REVIEW`). Its `commands.md` uses `python -c "pass"`, which works in both `bash -c` and `cmd.exe`.

CI on PR #15 at ca376ff (all four jobs):
- ubuntu with mawk: success
- ubuntu with gawk: success
- macos with the system awk: success
- windows with python: success

Windows needed four fixes beyond the job itself, all in the product or tests, none of them behaviour of the old bash scripts:
- Tickets and `commands.md` saved with CRLF line endings read as an unknown status, which hung `flow-view --watch`; the readers (`tickets.records`, `gate.command`, `view.show_status`) now drop a trailing carriage return.
- `bash` on the Windows runner's PATH is the WSL stub, so every gate and smoke command failed; commands now run through the system shell on Windows (`gate.shell`) and `bash -c` elsewhere. This makes the spec's "bash is not required on Windows" true.
- The Python tests wrote and read text with the platform's default encoding; they now say UTF-8.
- Tests that assert POSIX paths or bash syntax are made portable or skipped on Windows.

### Shortcuts taken

- `grep -c 'unittest discover' .github/workflows/tests.yml` prints 2, not 3: Ubuntu and macOS share one matrix job, so one step covers both.
- `tests/run.sh` does not run on Windows (out of scope in this ticket). Only the unit tests and the fixture drive do.
- Windows is untested with a real agent run. `commands.md` commands there run under `cmd.exe`, so a plan written with bash syntax needs `python -c` calls or a platform-specific command.
