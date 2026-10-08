# Teach both skills to use the repo's conductor, else the home one

Type: task
Status: resolved
Blocked by: —
Test first: yes

Edit `skills/feature-flow/SKILL.md` (Claude) and `adapters/codex/feature-flow/SKILL.md` (Codex). In the paragraph that introduces "The conductor is `python3 scripts/flow.py <feature> <command>`", add a short rule: if `scripts/flow.py` exists in the repo, use it (the repo's own install wins); otherwise use `python3 "${FEATURE_FLOW_HOME:-$HOME/.feature-flow}/scripts/flow.py"`. Say that wherever the skill or a message names `scripts/flow.py`, `scripts/flow-status.py` or `scripts/flow-view.py`, it means the same folder, and that the guides are then in that folder's sibling `guides/` (`~/.feature-flow/guides/`, else `.feature-flow/guides/` in the repo). Run the conductor with the working directory in the repo: state and plans stay there. Keep the rest of each skill unchanged; the long example commands may keep `scripts/flow.py` as the repo form.

Adjust the install checks: the Claude skill's "say to run `uvx feature-flow-cli install .`" line also offers `uvx feature-flow-cli install --user` (once for every repo). The Codex skill's role check accepts `.agents/flow-roles/` in the repo or `~/.feature-flow/agents/`, and its "say to run" line also offers `install --user --agent codex`. The `git status` bullet about `.feature-flow/installed.txt` stays (it only applies to a repo install).

Then refresh this repo's own tracked copies so `tests/py/test_own_install.py` stays green: `python3 install.py . --agent all --force` (it rewrites `.claude/skills/feature-flow/SKILL.md` and `.agents/skills/feature-flow/SKILL.md`); commit nothing outside the ticket's change. Add a test (in `tests/py/test_units.py` or a new `tests/py/test_skills.py`) that both source skill files contain the home path rule (`.feature-flow/scripts/flow.py`) and still mention `scripts/flow.py`.

## Not in this ticket

- The conductor and installer code: tickets 01 and 03.
- README: ticket 06.

## Done when

- Both SKILL.md files contain the rule naming `.feature-flow/scripts/flow.py` and `FEATURE_FLOW_HOME`.
- `python3 -m unittest discover -s tests/py -p "test_own_install.py"` prints `OK`.
- The new skill-text test passes: `python3 -m unittest discover -s tests/py -p "test_skills.py"` prints `OK`.

```check
$ python3 -m unittest discover -s tests/py -p "test_own_install.py"
prints OK
$ python3 -m unittest discover -s tests/py -p "test_skills.py"
prints OK
```

## Reference

- `skills/feature-flow/SKILL.md`, `adapters/codex/feature-flow/SKILL.md`
- `tests/py/test_own_install.py`

## Answer

**Built**: `skills/feature-flow/SKILL.md` and `adapters/codex/feature-flow/SKILL.md` (conductor rule after the "The conductor is" sentence; install checks offer `install --user`; Codex role check accepts `.agents/flow-roles/` or `~/.feature-flow/agents/`); refreshed `.claude/skills/feature-flow/SKILL.md` and `.agents/skills/feature-flow/SKILL.md` with `python3 install.py . --agent all --force`; new `tests/py/test_skills.py` (committed first as `5d2756c`, failed on the missing `.feature-flow/scripts/flow.py`).

**Proof**: `python3 -m unittest discover -s tests/py -p test_skills.py` printed OK (1 test); `-p test_own_install.py` printed OK (2 tests); full `python3 -m unittest discover -s tests/py` printed OK (263 tests). Both SKILL.md files contain `FEATURE_FLOW_HOME` and `.feature-flow/scripts/flow.py` (asserted by the test). `bash tests/run.sh` not run by me.

**Decisions**: the literal `~/.feature-flow/scripts/flow.py` is spelled out beside the `${FEATURE_FLOW_HOME:-...}` form so the plain-text check finds it.

**Shortcuts taken**: none.

**For later tickets**: `install.py . --agent all --force` also creates an untracked `.feature-flow/` in this repo (installed.txt etc.); I deleted it afterwards and committed none of it.
