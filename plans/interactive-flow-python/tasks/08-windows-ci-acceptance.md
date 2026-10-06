# Run on Windows in CI and prove the bar

Type: task
Status: open
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
