# Switch every caller to Python and delete the bash scripts

Type: task
Status: open
Blocked by: 02, 03, 04, 05, 06
Test first: no
Floor: allow test-delete

Every port has passed its parity test. Switch the remaining callers to the Python commands and delete the bash versions: the guides under `guides/`, both `feature-flow` skills, `tests/smoke-real.sh`, `examples/demo.sh`, the README and the plan templates now call `python3 scripts/flow-status.py`, `python3 scripts/gate.py`, `python3 scripts/floor-guard.py` and `python3 scripts/flow-view.py`. Delete `scripts/flow-status.sh`, `scripts/gate.sh`, `scripts/floor-guard.sh` and `scripts/flow-view.sh`, and the parity tests that compared them. Point the remaining `tests/run.sh` checks at the Python commands. The installer installs the `.py` shims and stops installing the `.sh` scripts.

## Not in this ticket

- The Windows CI job: the next ticket.

## Done when

- `ls scripts/*.sh 2>/dev/null` prints nothing.
- `grep -rnE '(flow-status|gate|floor-guard|flow-view)\.sh' --exclude-dir=plans --exclude-dir=.git .` prints nothing.
- `bash install.sh "$(mktemp -d)"` installs `scripts/flow-status.py` and no `scripts/*.sh`.
- `bash tests/run.sh` exits 0 and `git status --porcelain` is empty afterwards.

## Reference

- guides/, skills/feature-flow/, adapters/codex/feature-flow/, README.md, tests/run.sh, tests/smoke-real.sh, examples/demo.sh

## Answer
