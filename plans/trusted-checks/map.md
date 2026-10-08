# Map: trusted-checks

## Destination

Every conductor call the skills make goes through `scripts/flow-trust.py`, whose sha256 both skills pin and whose one-line loader checks and runs the same bytes. It stops the run when the flow's files changed since the last step, when the flow's code changed during a call, or when the run state is not what the conductor saved; the digest it prints carries trust from step to step and, through `HANDOFF`, to the next session. Version 0.5.0, built after global-install (PR #38) merges.

**The bar.** `python3 -m unittest discover -s tests/py -p "test_trust_drive.py"` prints `OK` (holes a, b and c, a new package file, and edited guide, role, skill and state files each end in a STOP naming the path; an untampered drive reaches DONE), and `python3 -m unittest discover -s tests/py` and `bash tests/run.sh` pass. Ticket 08 runs it.

## How to work this

- See what is ready: `python3 scripts/flow-status.py trusted-checks`. Take the lowest numbered READY ticket.
- Claim: set `Status: claimed` in the ticket and save before starting.
- Resolve: write the result under `## Answer`, set `Status: resolved`, then add one line to Decisions so far below.
- See the graph: `python3 scripts/flow-status.py trusted-checks --mermaid`.
- Commands live in `commands.md` (frozen). Lessons live in `learnings.md` (append only).
- Status lives only in the ticket files. This map never repeats it.

## Decisions so far

- Plan — the trusted code is a shipped file pinned by a sha256 in both skills, not a typed snippet; see spec.md Decisions (the user was asked to confirm on a decision card).
- Plan — snapshot before and after every conductor call; code must not change during a call (hole c, reproduced; see learnings.md).
- Plan — only feature-flow's named files in `scripts/` are hashed; ticket 01 stops anything else in `scripts/` or the repo root from being imported.
- Plan — the digest is `<code>.<state>` so a flow-edit build can change code but never the state; the `.trust` file only names paths (plan review finding).
- Plan — the conductor runs with `-X pycache_prefix=<fresh temp>`: a planted .pyc would otherwise run edited code with unchanged sources (plan review finding).
- Plan — every ticket that edits feature-flow's own files carries `Floor: allow flow-edit`: build this plan from a pinned older conductor (`git worktree add ../ff-0.4.0 v0.4.0`), as guard-hardening and proven-checks were.
- Plan — the brief's "previous ticket passed review" check is dropped (forgeable by the same writer; the runner already covers it).
- Plan — this builds on global-install (0.4.0, PR #38): build only after it merges, on a fresh main; the runner hashes `$FEATURE_FLOW_HOME` and lives beside whichever `flow.py` the skill picks.
- Plan — sources outside the repo code:
  - Python `-I`: docs: https://docs.python.org/3/using/cmdline.html#cmdoption-I ("sys.path contains neither the script's directory nor the user's site-packages directory"; implies -E and -s, and -P from 3.11).
  - Python `-X pycache_prefix` (3.8+), which redirects .pyc reads and writes away from `__pycache__/`: docs: https://docs.python.org/3/using/cmdline.html#cmdoption-X and https://docs.python.org/3/library/sys.html#sys.pycache_prefix. The plan reviewer confirmed a planted .pyc is loaded without it and ignored with it.
  - `importlib.util.spec_from_file_location(name, location, submodule_search_locations=...)` plus `sys.modules[name] = module` before `spec.loader.exec_module(module)` to load a package by path: docs: https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
  - `py_compile.compile(..., invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)` writes a .pyc whose header holds the source's mtime and size (used to forge one in tests): docs: https://docs.python.org/3/library/py_compile.html
  - `git --no-replace-objects` ignores replacement refs made by `git replace`: docs: https://git-scm.com/docs/git#Documentation/git.txt---no-replace-objects and https://git-scm.com/docs/git-replace. `git cat-file blob` prints the raw blob with no textconv: https://git-scm.com/docs/git-cat-file
  - `cmd.exe`: `%` expands variables, `!` only with delayed expansion (off by default), `"` groups an argument; the loader uses only double quotes and none of `$ % !`: docs: https://learn.microsoft.com/windows-server/administration/windows-commands/cmd
- 01 — the five scripts drop their own folder from sys.path first thing and load feature_flow by path (spec_from_file_location), so nothing in scripts/ or the repo root can shadow a module; work under python3 -I.
- 02 — with FLOW_TRUSTED=1 the conductor's last stderr line is `flow-state <state sha|none> <findings sha|none>` from the bytes it wrote/read (state.SEEN); owner stored as sha256(token), old 16-hex raw owners accepted once; next/prompt/verdict STOP without FLOW_TRUSTED=1.
- 02 — (round 2) cli.peek reads both files before any early return, so usage errors report what is on disk; state.* records only with an explicit kind ("state"/"findings"); a non-UTF-8 state file is a STOP.

## Open questions

- Should `next`, `prompt` and `verdict` refuse to run without the runner (ticket 02, part 3)? Planned default: yes, as a guard against a session that forgets the runner; it changes the README's direct command line (ticket 07). If the user says no, drop part 3 of ticket 02 and the README change in ticket 07. Asked in the thread.
- Hash `.claude/agents/`, `guides/` and `agents/` beside the conductor by feature-flow's file names only, not every file (spec.md § Decisions, "Shared folders hashed by name")? Planned default: by name, so the user's own agents and folders never stop a run. If the user says every file, ticket 03 changes the hashed set.
