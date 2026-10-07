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

Built: agents/feature-planner.md (thinking strategy + rules, tools Read, Glob, Grep, Bash, Write, WebSearch, WebFetch) and agents/plan-reviewer.md (read only, ends PLAN-REVIEW: PASS/FAIL).

Proof: `bash tests/run.sh` prints the new "planning roles" checks (planner has WebSearch and no Edit, reviewer has no Edit or Write), and installed checks for both roles in .claude/agents/ and .agents/flow-roles/. 422 passed, 0 failed.

Decisions: no installer change, it already copies every agents/*.md.

Shortcuts taken: none.

Review fixes: the Codex review on PR #20 found that a findings round asks the planner to fix its draft, which a no-Edit role with "never edit an existing file" could not do. The planner now has Edit and may write and edit only inside the draft folder; the test checks that rule instead of the missing Edit.
