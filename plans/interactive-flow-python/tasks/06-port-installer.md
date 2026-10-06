# Port the installer to Python

Type: convert
Status: open
Blocked by: 01
Test first: yes

Start only after `plans/interactive-flow` ticket 10 is resolved: it removes the headless parts `install.sh` still installs.

Port `install.sh` to `feature_flow/install.py`, run as `python3 install.py` from the repo root. Same options (`--agent claude|codex|all`, `--user`, `--force`, `--dry-run`), same `CLAUDE_HOME` and `AGENTS_HOME`, same report lines, same rule that nothing is deleted and differing files are kept unless `--force`. Then make `install.sh` a wrapper of a few lines that runs `exec python3 "$(dirname "$0")/install.py" "$@"`, so `bash install.sh` keeps working. Do not fix bugs you find; note them under Shortcuts taken.

Before replacing `install.sh`, add a parity test: for each existing installer check in `tests/run.sh`, run the bash installer and `python3 install.py` into two temp targets and require the same report output and the same file tree (`find` listing and file contents).

## Not in this ticket

- Changing what gets installed.

## Done when

- `python3 install.py "$(mktemp -d)" --dry-run` prints the same report as the bash installer did on the same target, shown by the parity test.
- `wc -l < install.sh` is at most 5, and `bash install.sh "$(mktemp -d)"` installs the same tree as before.
- All existing installer checks in `bash tests/run.sh` pass unchanged, `bash tests/run.sh` exits 0, and `git status --porcelain` is empty afterwards.

## Reference

- install.sh (read only until the wrapper step)
- tests/run.sh (the `install.sh` sections)

## Answer
