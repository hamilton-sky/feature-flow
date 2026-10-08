# Say exactly what is protected in the README and the build guide, and bump to 0.5.0

Type: task
Floor: allow flow-edit
Status: resolved
Blocked by: —
Test first: no

In `README.md`, rewrite the paragraph in the cautions that describes the code check (it says "The conductor also checks that the code it runs ... That check is a tripwire, not a sandbox."). Say:

- Protected: edits by the builder, reviewer or planner subagents during a session, to feature-flow's own files (its package, its files in `scripts/`, the guides, the roles, the skill folders) and to the run state, including edits made by code the conductor runs during a step (tests, checks, git hooks); and between sessions when the `HANDOFF` line carries its digest. The session checks this with `scripts/flow-trust.py`, whose hash the skill pins, so a subagent cannot change the check.
- Not protected: a subagent that changes `python3` on PATH or the system Python, the agent itself, or anything outside the repo and the install folders; the session's very first step (whatever is on disk then is trusted); a background process left running by a step's own commands (it can swap a flow file in the instant between the runner's check and the conductor loading it, then put it back); a session that stops passing its digest. The conductor's own code check stays as a second line that catches accidental edits.
- Remove any wording that says the conductor's in-process check alone stops tampering. Keep the existing `Floor: allow flow-edit` sentence and mention that the session tells you which flow files changed.

Update the README's direct command-line examples (the `python3 scripts/flow.py <feature> start|next|prompt|verdict` usage line and any other direct `next`, `prompt` or `verdict` example): `next`, `prompt` and `verdict` now run as `FLOW_TRUST=<digest or new> python3 -I scripts/flow-trust.py <feature> <command>`, which prints a `TRUST` line first; `start`, `reset` and the planning commands still work directly.

In `guides/build.md`, the "Do not edit the flow's own code" bullet: name feature-flow's own files in `scripts/` (`flow.py`, `flow-status.py`, `gate.py`, `floor-guard.py`, `flow-view.py`, `flow-trust.py`) rather than the whole `scripts/` folder, add the run state in `.feature-flow/state/`, and say the session stops the run if they change. Refresh this repo's installed copy of the guide if `tests/py/test_own_install.py` needs it.

Set `__version__ = "0.5.0"` in `feature_flow/__init__.py` (global-install, which this builds on, is 0.4.0).

## Not in this ticket

- The skill text: ticket 06.
- Release notes or tags: the user tags releases.

## Done when

- `python3 -c "import feature_flow; print(feature_flow.__version__)"` prints `0.5.0`.
- `README.md` contains `flow-trust.py` and the words `Not protected`; it no longer contains `That check is a tripwire, not a sandbox.`
- `guides/build.md` names `flow-trust.py` and `.feature-flow/state/`.
- `python3 -m unittest discover -s tests/py` prints `OK`.

```check
$ python3 -c "import feature_flow; print(feature_flow.__version__)"
prints 0.5.0
$ python3 -c "import pathlib,sys; t=pathlib.Path('README.md').read_text(encoding='utf-8'); sys.exit(0 if 'flow-trust.py' in t and 'Not protected' in t and 'That check is a tripwire, not a sandbox.' not in t else 1)"
exit 0
$ python3 -c "import pathlib,sys; t=pathlib.Path('guides/build.md').read_text(encoding='utf-8'); sys.exit(0 if 'flow-trust.py' in t and '.feature-flow/state/' in t else 1)"
exit 0
$ python3 -m unittest discover -s tests/py
prints OK
```

## Reference

- spec.md § Scope, § Risks
- `README.md` (the cautions section), `guides/build.md`, `feature_flow/__init__.py`

## Answer

Work started at 27b0269a906473abcbb119996a03ab670a420549. Test first: no.

**Built**

- `README.md`, Caution: the old code-check sentence and "That check is a tripwire, not a sandbox." are replaced. The new text says every conductor call runs through `scripts/flow-trust.py` (beside the conductor: `scripts/` in the repo, `~/.feature-flow/scripts/` for a `--user` install), whose sha256 the skill pins and whose loader runs those same bytes. It says the runner prints `TRUST <code>.<state>` and the session passes it on as `FLOW_TRUST`. Then a **Protected:** paragraph (subagent edits to the package, the six named `scripts/` files, guides, roles, skill folders, in repo and install folders, and to `.feature-flow/state/`, including edits by tests, `check` commands and git hooks during a step; a STOP that names the files instead of TRUST; between sessions via the HANDOFF digest; the kept `Floor: allow flow-edit` sentence plus `FLOW-EDIT <files>`, which tells you which flow files changed) and a **Not protected:** paragraph (PATH `python3` or system Python, the agent, anything outside the repo and install folders; the very first call; a background process swapping a file between check and load; a session that stops passing its digest or resumes without one). The paragraph also says the conductor's own check stays as a second line for accidental edits and cannot stop deliberate tampering on its own. The floor guard and auto-stop sentences are unchanged.
- `README.md`, Commands: the `flow.py <feature> start|next|prompt|verdict` line is split. `flow.py` keeps `start|reset [NN]` and the planning commands. A new line gives `FLOW_TRUST=<digest|new> python3 -I scripts/flow-trust.py <feature> next|prompt|verdict <file>` and notes that it prints TRUST first. Below the block, a sentence quotes the conductor's refusal (`STOP run the conductor through scripts/flow-trust.py, as the skill says`) and says where the scripts live for a `--user` install. The handoff example now shows the digest word (`HANDOFF /feature-flow csv-export <16 hex>.<16 hex>`).
- `guides/build.md`: the "Do not edit the flow's own code" bullet now names `feature_flow/`, the six `scripts/` files, the guides and the roles, and adds the run state in `.feature-flow/state/`. It says `Floor: allow flow-edit` allows only the code edits and never the run state, and that the session stops the run if they change. No installed copy needed a refresh: guides are installed only under `.feature-flow/guides/`, which `test_own_install` forbids tracking, and that test passes.
- `feature_flow/__init__.py`: `__version__ = "0.5.0"`.
- `tests/run.sh`: the `--version prints the version` expectation changed from `feature-flow 0.4.0` to `feature-flow 0.5.0`. The 0.4.0 bump (496f635) changed the same line. `feature_flow/released.py` only lists 0.1.x hashes and never grows, so it is unchanged.

**Proof**

- `python3 -c "import feature_flow; print(feature_flow.__version__)"` printed `0.5.0` (rc 0).
- README check command: exit 0.
- guides/build.md check command: exit 0.
- `python3 -m unittest discover -s tests/py`: `Ran 350 tests in 171.796s` / `OK`.
- `bash tests/run.sh`: `465 passed, 0 failed`, exit 0 (includes `ok --version prints the version`). Smoke command: exit 0.

**Decisions**

- The README's direct runner form is the short `python3 -I scripts/flow-trust.py` form from ticket 03's Answer, not the skill's pinned loader line. The loader belongs in the skill, and its pinned sha would go out of date in the README with every runner change.
- The handoff example shows a made-up `<16 hex>.<16 hex>` digest, because that is what the runner appends (ticket 05).
- The scripts named in the guide and README are the six that the runner hashes (spec "What is hashed"). The user's own files in `scripts/` are not flow code.

**Shortcuts taken**

- none

**For later tickets**

- 08: the docs now promise exactly what the acceptance drive proves (holes a, b, c, new package file, edited guide/role/skill/state each STOP). If 08 finds a gap, the Protected paragraph in README's Caution must change with it.
