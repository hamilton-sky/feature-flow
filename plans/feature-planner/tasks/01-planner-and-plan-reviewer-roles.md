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

**Proof**

- `bash tests/run.sh` (with a temporary PATH-only `python` alias to this host's `python3`, because the existing fixture invokes `python`) printed `ok` for `the feature planner lists WebSearch`, `the feature planner has no Edit tool`, `the plan reviewer has no Edit tool`, and `the plan reviewer has no Write tool`.
- The same fresh run printed `ok` for `Claude installs both planning roles` and `Codex installs both planning roles`.
- The same run completed with `418 passed, 0 failed`. The repository smoke command also exited 0.

**Decisions**

- Kept the role bodies short and protocol-focused, matching the existing builder and reviewer roles while spelling out every invariant named by the spec.
- Tested only the front-matter tool lists, so prose cannot accidentally satisfy or fail a permission check.

**Shortcuts taken**

- none

**For later tickets**

- Ticket 02 can refer to the installed roles as `feature-planner.md` and `plan-reviewer.md`; the generic installer already delivers both to Claude and Codex destinations.
