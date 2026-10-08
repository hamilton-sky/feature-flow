# trusted-checks — Spec

## Problem

The conductor is meant to catch a builder (or reviewer, or planner) subagent that edits feature-flow itself, but it checks itself with its own code. `codehash.py` hashes the conductor's files and `Conductor.check_code()` compares them with hashes saved in `.feature-flow/state/`. Every `scripts/flow.py` call starts a new process that loads whatever is on disk, so a subagent that edits `conductor.py` to skip `check_code()`, or rewrites the saved hashes, gets its own version run on the next call. The run state (`flow-<feature>.state`) is a plain file any subagent can write: writing `phase=` after resolving a ticket makes the next `next` hand out the following ticket with no gate, floor guard, Done when checks, test-first proof or review. Code the conductor itself runs during `next` (the gate's Test command, Done when checks, the test-first red run, the smoke command, git hooks) can edit the conductor too. And `scripts/flow.py` runs with `scripts/` on `sys.path`, so a new `scripts/secrets.py` replaces the standard library inside the conductor. All four were reproduced on main 69b993c (see learnings.md).

The principle of the fix (the user's): nothing a subagent can write may decide whether a subagent tampered. The trusted reference is the orchestrating session's own context, which subagents cannot change. The check runs code pinned by that context, not code trusted because it is on disk.

## Goal and the bar

Every conductor call the skill makes goes through `scripts/flow-trust.py`, a stdlib-only file whose sha256 both skills pin. A one-line loader in the skill reads the file, checks its bytes against the pinned hash and runs those same bytes. The runner refuses to call the conductor when the flow's files differ from the digest the session passed in, refuses to accept a call during which the flow's code changed or the run state ended up different from what the conductor saved, and prints the new digest for the session to pass next time.

**The bar.** `python3 -m unittest discover -s tests/py -p "test_trust_drive.py"` prints `OK`: in a fixture repo, driven the way the skill drives it (loader, then runner with the last `TRUST` digest), each of these ends in a `STOP` that names the changed path: (a) a builder commit that makes `check_code` return early, (b) a builder that resolves its ticket and writes `phase=` into the state file, (c) a `Test:` command whose script edits `feature_flow/conductor.py` during `next`, a new `.py` file in the package folder, and an edited guide, role, skill or state file; an untampered drive of the same plan reaches `DONE`. And `python3 -m unittest discover -s tests/py` and `bash tests/run.sh` pass. Ticket 08 runs it.

## Scope

In: the runner `scripts/flow-trust.py` (hashing, the before/during/after checks, `TRUST` line, flow-edit allowance, HANDOFF digest); the conductor reporting the sha of the state it saved and refusing direct `next`/`prompt`/`verdict`; owner stored as `sha256(token)`; `scripts/*.py` loading the package by path so nothing in `scripts/` or the repo root can shadow a module; both skills pinning the runner's hash and calling only through it; README and `guides/build.md` on what is and is not protected; version 0.5.0.
Not in scope: signing releases; protecting against a compromised system Python, `python3` on PATH, the agent itself, ptrace, or anything outside the repo and the install folders (named in the docs, ticket 07); a "previous ticket passed review" check inside the conductor (dropped, see Decisions); a real Codex or Windows agent run (no Codex from the cloud; Windows is covered by CI unit tests).

## Happy path

1. Session's first conductor call: `FLOW_TRUST=new <loader> <folder>/flow-trust.py <sha> <feature> start` → loader checks the file's hash, runs it → runner hashes the flow files, runs `python3 -I <folder>/flow.py <feature> start`, hashes again → prints `TRUST <digest>` then `OK <token>`.
2. Every later call passes the last digest: `FLOW_TRUST=<digest> FLOW_SESSION=<token> ... <loader> ... <feature> next` → runner compares, calls, re-hashes → `TRUST <new>` then `BUILD ...`.
3. After a BUILD, the session passes `--after-build <ticket> <sha>` on the next `next`; a code change is accepted only if the ticket at `<sha>` has `Floor: allow flow-edit`, and the runner prints `FLOW-EDIT <paths>` so a non-auto session tells the user.
4. At `HANDOFF` the runner prints `HANDOFF <invoke> <feature> <digest>`; the user types it into a new session, which passes the digest as `FLOW_TRUST` on its first call.

## Edge cases

| Trigger | Expected behaviour | Handled in ticket |
|---|---|---|
| Flow file edited, added or removed between calls | `STOP flow files changed since the last step: <paths>`; conductor not called | 03 |
| `FLOW_TRUST` missing | `STOP` asking for the last TRUST digest (forgetting is loud, not silent); `new` is the explicit first-call value | 03 |
| Flow code changed during a conductor call (gate, checks, hooks) | `STOP flow code changed during <command>: <paths>` | 04 |
| State file differs after the call from what the conductor reported saving | `STOP the run state was changed by something other than the conductor` | 04 |
| Code change after a BUILD whose ticket at base allows flow-edit | accepted, `FLOW-EDIT <paths>` line, new digest | 04 |
| `git replace` used to swap the ticket blob | ignored: runner reads with `git --no-replace-objects cat-file blob` | 04 |
| A planted `feature_flow/__pycache__/*.pyc` that matches the source's mtime and size | not loaded: the conductor runs with a fresh `pycache_prefix` | 03 |
| Flow-edit build that also edits the state file and rewrites `.trust` | STOP: the state part of the digest must match, `.trust` is never used to decide | 04 |
| Edits to `__pycache__/`, `*.pyc`, the review-reply file, the log, drafts, or the user's own files in `scripts/` | no STOP | 03 |
| Runner file differs from the pinned hash (tampered, or skill and runner from different versions) | loader exits 1 with `flow-trust.py does not match this skill`; skill says reinstall and stop | 06 |
| Windows checkout with CRLF in `flow-trust.py` | loader hashes LF-normalised bytes, so it still matches | 06 |
| Planted `hashlib.py` in the repo root | ignored (`-I`) | 06 |
| Conductor called directly, without the runner | `STOP` telling the session to call through `scripts/flow-trust.py` (`start`, `reset`, `plan-*` still allowed) | 02 |
| Old-style `HANDOFF <invoke> <feature>` typed into a new session | works with `FLOW_TRUST=new`; the skill warns it could not check the flow's files | 06 |
| State from 0.4.x with a plain owner token | still accepted once, re-saved hashed | 02 |
| New `scripts/<stdlib-name>.py` or repo-root `<stdlib-name>.py` | not imported by the conductor or its sibling scripts | 01 |

## Design

    session context: pinned sha, last TRUST digest
         │ loader line (python3 -I -c ...)
         ▼
    [flow-trust.py bytes, sha checked] ──hash flow files──► compare FLOW_TRUST
         │ same                                   │ differs
         ▼                                        ▼
    [python3 -I flow.py <cmd>]                STOP <paths>
         │ stdout line, stderr `flow-state <sha>`
         ▼
    hash again: code same? state == reported?
         │ yes                                    │ no
         ▼                                        ▼
    TRUST <digest> + conductor line          STOP <paths>

**What is hashed** (missing paths skipped, `__pycache__/` and `*.pyc` never): from the conductor's own folder (the folder `flow-trust.py` is in, call it `S`): `S/{flow.py, flow-status.py, gate.py, floor-guard.py, flow-view.py, flow-trust.py}`, `S/../feature_flow/` (every file; it exists there only in a feature-flow checkout or home install), and in `S/../guides/` and `S/../agents/` only the names `prompts.find_file` looks up (the `GUIDES` and `ROLES` values plus `debug.md`), present or absent, because in a repo install `S/..` is the user's repo root and its own `guides/` or `agents/` folders are the user's. In the repo: `.feature-flow/{feature_flow,guides,agents}/`, `.claude/skills/feature-flow/`, `.agents/skills/feature-flow/`, `.agents/flow-roles/`, and `.claude/agents/<the four feature-flow role names>`. In the home: `$CLAUDE_HOME` (default `~/.claude`) `skills/feature-flow/` and `agents/<four role names>`, `$AGENTS_HOME` (default `~/.agents`) `skills/feature-flow/`, and `$FEATURE_FLOW_HOME` (default `~/.feature-flow`) every file. State: `.feature-flow/state/flow-<feature>.state` and `.findings`. Code = everything but the two state files.

The digest has two parts, `<code>.<state>`, each the first 16 hex characters of sha256 over sorted `path\0sha256\0` pairs (in-repo paths relative and POSIX, others absolute POSIX): code is every hashed file but the two state files, state is those two. Keeping them apart lets the runner allow a flow-edit code change while still refusing any state change, without trusting anything on disk.

**Bytecode.** `__pycache__/` and `*.pyc` are not hashed, so the runner must make sure none is loaded: it runs the conductor with `-X pycache_prefix=<a fresh empty temp folder>`, so a planted `feature_flow/__pycache__/*.pyc` (which Python would otherwise load when its header matches the source's mtime and size) is ignored. The per-file list is written to `.feature-flow/state/flow-<feature>.trust` after every call; it is untrusted and used only to name paths once the digest has already decided to STOP.

### Decisions

- **Where the trusted code lives** — options: A) the brief's ≤15-line snippet typed into `python3 -I -c` for every check; B) a shipped file whose sha256 the skills pin, run by a one-line loader that checks and executes the same bytes. Chosen: B. Why: the trust still comes from the session's context (the pinned hash), the model copies one line instead of retyping 15 lines dozens of times (drift gives false STOPs), the file can be as long as the checks need, and a one-line `-c` avoids `cmd.exe` multi-line quoting. Rejected: A. This is the main departure from the brief; the user was asked on a decision card.
- **Who compares digests** — options: A) the session keeps per-file lines and compares by eye; B) the runner compares, given the last digest. Chosen: B. Why: a lost or mistyped digest becomes a STOP, never a silent pass, and the session's context stays small.
- **When to snapshot** — options: A) after every conductor call (brief); B) before and after every call, and require code to be unchanged across the call. Chosen: B. Why: A makes the conductor's own runs of builder-written code (gate, Done when, test-first, smoke, git hooks) a laundering path (hole c).
- **State changes during a call** — the honest conductor (its code was verified at the start of the call) reports the sha of the state and findings files as it left them on stderr when `FLOW_TRUSTED=1`; the runner requires both files to match. Why: closes a state write by code the conductor ran after its last save.
- **`scripts/` coverage** — options: A) hash every file in `scripts/` (brief); B) hash feature-flow's named files and stop anything else there from being imported. Chosen: B. Why: the installer writes into the user's own `scripts/` folder, so A would STOP whenever a ticket edits e.g. `scripts/deploy.sh`; B fixes the root cause (ticket 01). Same for the repo root in a feature-flow checkout.
- **Shared folders hashed by name** — options: A) every file in `.claude/agents/`, `S/../guides/` and `S/../agents/` (brief); B) only the names feature-flow uses there (the four role names; the `GUIDES` and `ROLES` values plus `debug.md`), present or absent. Chosen: B. Why: `~/.claude/agents/` and `.claude/agents/` hold the user's other agents, and in a repo install `S/..` is the user's repo root, so A would STOP on any edit to the user's own files; a new file there is never read by the conductor or the skill. Folders feature-flow owns (`feature_flow/`, `.feature-flow/*`, the skill folders, `.agents/flow-roles/`, `$FEATURE_FLOW_HOME`) are still hashed whole. An open question in map.md, asked in the thread.
- **Forgetting** — the conductor refuses `next`, `prompt` and `verdict` unless `FLOW_TRUSTED=1` (set only by the runner), and the runner refuses a missing `FLOW_TRUST`. Forgeable, but aimed at a forgetful session, not a builder. User-visible: the README's direct `python3 scripts/flow.py <feature> next|prompt|verdict` use changes to `FLOW_TRUST=new python3 -I scripts/flow-trust.py <feature> <command>` (ticket 07 updates it); an open question in map.md, asked in the thread; planned default yes.
- **Owner token** — stored as `sha256(token)` (brief goal 5). Low value: subagents can probably read the session's transcript on disk (inferred, not tried); kept because it is cheap.
- **"Previous ticket passed review" in `pick_ticket()`** (brief goal 5) — dropped. Why: the same writer that can write `phase=` can write that marker and the log line, and the runner already STOPs any state change between calls. Overrule in the plan review if wanted.
- **HANDOFF digest** — added by the runner, not the conductor, so the conductor's one-line output is unchanged. It guards the gap between sessions; edits to the skill files during a session are caught before the handoff because the skill folders are hashed.
- **Version** — 0.5.0: 0.4.0 is global-install (PR #38), which this builds on.

## Interfaces

- `scripts/flow-trust.py [--after-build <ticket> <sha>] <feature> <command> [args...]`, run via the loader. Env: `FLOW_TRUST` (`new` or the last `<code>.<state>` digest), plus the usual `FLOW_*`. Output: first line `TRUST <digest>` (or `STOP ...`), optional `FLOW-EDIT <paths>`, then the conductor's output unchanged except `HANDOFF` gains the digest. Exit code: the conductor's, or 1 on its own STOP.
- Loader (in both skills, byte for byte): `python3 -I -c "import hashlib,sys;b=open(sys.argv[1],'rb').read().replace(b'\r\n',b'\n');sys.exit(exec(compile(b,'flow-trust','exec')) if hashlib.sha256(b).hexdigest()==sys.argv[2] else 'flow-trust.py does not match this skill')" <S>/flow-trust.py <pinned sha> ...`
- Conductor: with `FLOW_TRUSTED=1`, the last stderr line is `flow-state <state sha256 or none> <findings sha256 or none>`, for the bytes it left in each file.

## Migration and compatibility

Direct `python3 scripts/flow.py <feature> next` now STOPs with a pointer to the runner; `start`, `reset` and the planning commands still work directly. A run started under 0.4.x keeps its plain owner token until the next save. An old `HANDOFF` line without a digest still resumes, with a warning. The skill and the runner must come from the same install; a mismatch STOPs with "reinstall".

## Risks

- Model friction: a longer command per call — the loader is one line copied from the skill, and the skill shows the full command once.
- Windows `cmd.exe` quoting of the loader — double quotes only, no `$`, `!` or `%`; tested by running the extracted loader line through the platform shell in ticket 06.
- Global-install not yet merged — build waits for #38; ticket 03 covers `$FEATURE_FLOW_HOME` either way.
