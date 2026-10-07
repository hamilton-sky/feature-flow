# Add the feature-planner and plan-reviewer roles

Type: task
Status: resolved
Blocked by: —
Test first: yes

Add two role files beside `agents/ticket-builder.md` and `agents/ticket-reviewer.md`, in the same style: front matter with `name`, `description`, `tools` and `model: inherit`, then a short body that points at the guide in the prompt and lists the rules that never bend.

`agents/feature-planner.md` is the planner's thinking strategy (spec.md § Decisions): the brief is the whole ask; read the repo before planning; research outside only where the code cannot answer, and cite it; two options at every real fork, a `settle` ticket when the choice is the user's; the lazy pass; prove the draft with `flow-status --check`; write only in the draft folder, never commit, never talk to the user. Tools: Read, Glob, Grep, Bash, Write, WebSearch, WebFetch. No Edit.

`agents/plan-reviewer.md` is read only (Read, Glob, Grep, Bash). It never saw the planner's reasoning, checks the draft against the brief, and ends with exactly `PLAN-REVIEW: PASS` or `PLAN-REVIEW: FAIL`.

## Not in this ticket

- The guides the roles point at: ticket 02.
- Installer changes: none are needed, `feature_flow/install.py` already copies every `agents/*.md` to `.claude/agents/`, `.feature-flow/agents/` and `.agents/flow-roles/`.

## Done when

- `bash tests/run.sh` prints `ok` lines checking that `agents/feature-planner.md` lists `WebSearch` and no `Edit`, and that `agents/plan-reviewer.md` lists neither `Edit` nor `Write`.
- `bash tests/run.sh` prints an `ok` line that the Claude install puts `feature-planner.md` and `plan-reviewer.md` into `.claude/agents/`, and the Codex install into `.agents/flow-roles/`.
- All existing tests still pass.

## Reference

- spec.md § Decisions
- agents/ticket-builder.md, agents/ticket-reviewer.md (the style to match)

## Answer

**Built**

- Added `agents/feature-planner.md` with the planner's repository-first strategy, outside-research citations, fork and `settle` handling, lazy pass, draft-only write boundary and `flow-status --check` proof rule.
- Added `agents/plan-reviewer.md` as a fresh read-only reviewer that checks the draft against the approved brief and emits the required verdict.
- Added focused role-permission and Claude/Codex installation checks to `tests/run.sh`.
- Made the conductor fixture use its running Python interpreter so the full suite does not depend on a separate `python` executable being installed.

**Proof**

- `bash tests/run.sh` printed `ok` for `the feature planner lists WebSearch`, `the feature planner has no Edit tool`, `the plan reviewer has no Edit tool`, and `the plan reviewer has no Write tool`.
- The same fresh run printed `ok` for `Claude installs both planning roles` and `Codex installs both planning roles`.
- The same exact run completed with `418 passed, 0 failed`; no PATH shim or command substitution was used. The repository smoke command also exited 0.

**Decisions**

- Kept the role bodies short and protocol-focused, matching the existing builder and reviewer roles while spelling out every invariant named by the spec.
- Tested only the front-matter tool lists, so prose cannot accidentally satisfy or fail a permission check.

**Shortcuts taken**

- none

**Review fixes**

- The gate reported that the exact `bash tests/run.sh` command failed because the fixture embedded `python -c` while this host provides only `python3`. Updated `tests/py/test_fixture_drive.py` to build its fixture commands from the quoted `sys.executable`; the focused regression passes and the exact full command now reports `418 passed, 0 failed`.

**For later tickets**

- Ticket 02 can refer to the installed roles as `feature-planner.md` and `plan-reviewer.md`; the generic installer already delivers both to Claude and Codex destinations.

## Review findings (round 1, gate)

gate: Test: bash tests/run.sh
gate: Test failed. the last lines of its output:
  ok    it is under 90 lines
  ok    the Codex skill is named feature-flow
  ok    with a quoted description
  ok    and no Claude-only header
  ok    and no argument hint
  ok    its openai.yaml makes it explicit only
  ok    it hands off with $feature-flow
  ok    it never says /feature-flow or $ARGUMENTS
  ok    its mode matches ticket 02 (subagents)
  ok    the Claude skill writes nothing under .git
  ok    the Claude skill saves the review reply in .feature-flow/state/
  ok    the Codex skill writes nothing under .git
  ok    the Codex skill saves the review reply in .feature-flow/state/
smoke-real.sh, prepare only
  ok    --prepare builds the project without any model installed
  ok    it says no model was called
  ok    and tells a codex user what to type
  ok    the project is installed for codex only
  ok    the plan passes the ticket check
  ok    and the first ticket is the one that is ready
  ok    it is one clean commit
  ok    a folder that is not empty is refused
  ok    --prepare defaults to claude
  ok    and tells a claude user what to type
  ok    the project is installed for claude only
  ok    without RUN_REAL or --prepare nothing runs
  ok    RUN_REAL=1 without --interactive runs nothing either
  ok    an unknown FLOW_AGENT is refused
  ok    and the script itself says what is allowed
  ok    and it creates nothing
  ok    --prepare without a folder is refused
  ok    --interactive without RUN_REAL is refused
  ok    an unknown option is refused
  ok    --interactive: a session that ends without HANDOFF, DONE or STOP exits 1
  ok    and says so
  ok    and prints the recovery command
  ok    and starts no second session
  ok    the session is started as a user would type it

414 passed, 4 failed
