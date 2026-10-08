# Make `install --user` write the whole flow under ~/.feature-flow/ and nothing into a repo

Type: task
Status: open
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

