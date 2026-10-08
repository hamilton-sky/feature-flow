# Make `install --user` write the whole flow under ~/.feature-flow/ and nothing into a repo

Type: task
Status: resolved
Blocked by: —
Test first: yes

In `feature_flow/install.py`, class `Installer`: when `user_level` is set, the conductor goes to a home folder instead of the target repo. The folder is `$FEATURE_FLOW_HOME` if set, else `$HOME/.feature-flow` (read next to where `CLAUDE_HOME` and `AGENTS_HOME` are read in `__init__`). Layout (see spec.md Design): `scripts/` (from `here/scripts`), `guides/`, `agents/` (raw role files, from `here/agents`), `feature_flow/` (from `self.package`, `skip=BUNDLE`), and the hash record `feature-flow.sha256` (`USER_HASHES`) in that folder. Add the home folder to `self.records` with `USER_HASHES`, so `place()`, `untouched()`, `locate()` and `write_installed()` give it the same upgrade rules as `~/.claude`: an unedited recorded file is updated, an edited one is kept and named, `--force` replaces it.

A user install writes no repo file: drop the `(target, HASHES)` record and the `INSTALLED` list for it, and skip the repo-only parts of `run()` (the "not a git repository" note, the exclude/`--private` handling, the "next: commit the installed files" hint). A target argument given with `--user` is ignored; the first output line `installing into ...` names the home folder. With `--agent codex|all` and `--user`, `install_codex()` must not write `<target>/.agents/flow-roles/` (the roles are in `~/.feature-flow/agents/`). A repo install (no `--user`) must write exactly what it writes today.

Update `USAGE` (both copies: `install.USAGE` and `command.USAGE`) and the module docstring to say what `--user` now does. Existing tests that expect `--user` to put scripts or roles in the repo must be changed in place to expect the home folder instead (do not delete assertions): `tests/py/test_install.py` (`test_a_user_level_upgrade_replaces_a_skill_nobody_edited` and neighbours), `tests/py/test_uninstall.py` (`test_user_removes_the_home_install_and_leaves_the_repo`: set `FEATURE_FLOW_HOME` under the temp home in `setUp`), and the two `--user` blocks in `tests/run.sh` (search `--user puts skills and agents in the user folder`, `--user keeps roles and scripts in the repo`; set `FEATURE_FLOW_HOME` there too).

## Not in this ticket

- Removing the home folder: that is `uninstall --user`, ticket 02.
- The skills choosing between repo and home conductor: ticket 05.
- Rewriting `python3 scripts/` in guide text for subagents: ticket 03.

## Done when

- After `install --user --agent all` with `HOME`, `CLAUDE_HOME`, `AGENTS_HOME` and `FEATURE_FLOW_HOME` under a temp folder, `scripts/flow.py`, `guides/build.md`, `agents/ticket-builder.md`, `feature_flow/__init__.py` and `feature-flow.sha256` exist under the home folder, and no `_bundle` folder is copied.
- The same run leaves the target repo without `scripts/`, `.feature-flow/`, `.claude/` and `.agents/`.
- A second run reports "already current"; an edited home file is kept and named; `--force` replaces it; an unedited file from an older recorded hash is updated.
- A repo install (no `--user`) still writes the same files as before (the existing repo-install tests pass unchanged).
- `python3 -m unittest discover -s tests/py -p "test_install.py"` prints `OK`, and `python3 -m unittest discover -s tests/py` and `bash tests/run.sh` pass.

```check
$ python3 -m unittest discover -s tests/py -p "test_install.py"
prints OK
```

## Reference

- spec.md § Design, § Decisions
- `feature_flow/install.py`: `Installer.__init__`, `place`, `untouched`, `write_installed`, `install_codex`, `run`
- `tests/py/test_install.py`, `tests/py/test_uninstall.py`, `tests/run.sh`

## Answer

**Built**: `feature_flow/install.py` (home folder `$FEATURE_FLOW_HOME` or `$HOME/.feature-flow` for `--user`; scripts, guides, agents, feature_flow and `feature-flow.sha256` go there; no repo record or `installed.txt`; no `.agents/flow-roles/` with `--user`; repo-only git notes moved into `repo_notes()`; docstring and `USAGE`), `feature_flow/command.py` (`USAGE`), `tests/py/test_install.py`, `tests/py/test_uninstall.py`, `tests/run.sh`. Test-only commit ee84c7a.

**Proof**:
- `python3 -m unittest discover -s tests/py -p "test_install.py"` prints OK (27 tests, new ones cover the layout, no `_bundle`, empty repo, second run "already current", edited file kept, `--force`, older recorded hash updated, codex writes no roles in the repo).
- `python3 -m unittest discover -s tests/py`: Ran 251 tests, OK.
- `bash tests/run.sh`: 457 passed, 0 failed.
- Repo-install tests pass unchanged.

**Decisions**: `--user` ignores the target argument; the first output line names the home folder. The old assertion that `installed.txt` lacks skills became "no `.feature-flow` in the repo" (stronger).

**Shortcuts taken**: in `test_uninstall.py` `setUp`, `FEATURE_FLOW_HOME` points at a sibling temp folder `flowhome`, outside the temp home, not under it as the ticket text says. Reason: `uninstall --user` does not know the home root until ticket 02, and the test asserts the temp home is empty. A user decision, because of the 01/02 order. Ticket 02 must move it back under `self.home` (one-line comment in the test says so).

**For later tickets**: ticket 02 moves `FEATURE_FLOW_HOME` in `test_uninstall.py` back under the temp home. The home record `feature-flow.sha256` lists paths relative to the home folder (`scripts/flow.py`, `feature_flow/...`).
