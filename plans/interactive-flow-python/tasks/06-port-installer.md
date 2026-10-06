# Port the installer to Python

Type: convert
Status: resolved
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

`feature_flow/install.py` is the port (stdlib only, 3.9 syntax, imports within the allowlist in `tests/run.sh`), and `install.py` at the repo root is a shim shaped like `scripts/flow.py` (`sys.dont_write_bytecode = True`). Same options read in the same order (`--agent X`, `--agent=X`, `--user`, `--force`, `--dry-run`, `-h`/`--help`), same `CLAUDE_HOME` / `AGENTS_HOME` (an empty value falls back to `$HOME/...`), same report lines in the same order, same exit codes (2 for usage errors and a missing target, 0 for `--help`). Files are compared and written as bytes; copies keep mode and times like `cp -p`; the two generated files (a Codex skill header, a role body) are written with mode 644 like the bash `chmod 644` on its temp file; nothing is deleted, a differing file is kept unless `--force`. `codex_header` and `role_body` follow the two awk programs line for line (bytes, a last line without a newline gets one, a carriage return is kept). The target is printed as bash's `cd && pwd` prints it: `$PWD` is used when it names the current directory, so a symlinked temp folder (macOS) prints the same path. What gets installed is unchanged; `feature_flow/install.py` itself now rides along in the package copy to `.feature-flow/feature_flow/`.

`install.sh` is now a 4-line wrapper: shebang, two comment lines, `exec python3 "$(dirname "$0")/install.py" "$@"`. The old bash installer is committed as `tests/install-bash-reference.sh`, used only by the parity test; it is deleted with the parity section in ticket 07.

Parity: the new section `install.sh and install.py parity` in `tests/run.sh` (right after the two installer sections) copies the sources to a temp folder, adds files the listing must skip or order (`.DS_Store`, `*.pyc`, `__pycache__`, a symlink, mixed-case names, an exec bit) and headers the transforms must rewrite (tabs, quotes, a backslash, CRLF, no final newline, a role without frontmatter), then runs every scenario of the existing installer checks plus edge cases (`--help`, `-h`, a missing target, `--agent=`, `--agent --force`, `-`, `--help --nonsense`, a git repo, `--dry-run --force`, an exec bit removed in the target, relative targets `.`, `..`, `""`, `./../b/`, `--user` with `HOME` only and with an empty `CLAUDE_HOME`). Each scenario runs once with the bash reference and once with `python3 install.py` in the same folder (so the printed paths are the same), under `LC_ALL=C`; the transcript (stdout and stderr together, with the exit code of every run) and the tree (sorted `find` listing, `cksum` and exec bit of every file, plus `diff -r`) must match. Result: `compared install.sh and install.py on 17 scenarios`, no difference. Checked that it catches a changed report line and a changed file mode. `bash tests/run.sh`: 365 passed, 0 failed. `python3 -m unittest discover -s tests/py`: 66 tests OK, 8 of them new in `tests/py/test_install.py`.

One existing check had to change: "a description with quotes and a backslash is escaped" pulled the `codex_header` awk function out of `install.sh` with `sed`, which the wrapper no longer holds. It now calls `feature_flow.install.codex_header` on the same input with the same two expectations. Every other installer check runs unchanged through the wrapper.

Shortcuts taken:
- Bugs kept from the bash version: the Codex loop over `skills/<name>` skips only `.DS_Store`, so a `*.pyc` or `__pycache__` there is installed (the parity fixture has one); a file whose contents match but whose mode differs counts as already current, even with `--force`, so a lost exec bit is never restored; `--dry-run --force` reports `update` lines while the summary still says `would add`; with `--agent all` a leftover skill present in both `.claude/skills` and `.agents/skills` is named twice; a target whose name starts with `-` cannot be given. Each wants its own ticket.
- The help text still says `usage: bash install.sh ...` (lines 2 to 14 of the old script, for parity); ticket 07 can switch it.
- Not reproduced: bash's `find | sort` and glob order follow the locale collation, the port sorts by bytes (as `LC_ALL=C`, which the parity test pins); `cd` honours `CDPATH` for a relative target; when `mkdir` or `cp` fails the port prints `install.py: <error>` and exits 1 where bash printed the tool's own message (also exit 1); an unreadable folder or file under the sources is skipped silently where `find`/`grep` printed an error; `cp -p` also tries to keep the owner; `--force` of a generated file onto a directory fails instead of copying into it; paths with a newline (which `$(...)` and `read` mangle).
- `bash install.sh` now needs `python3` on `PATH` (the wrapper fails with 127 without it), so the `note: install python3` line can only appear when the port is run by another interpreter name.
