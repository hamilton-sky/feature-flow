# Write the brief, planner and plan-review guides

Type: task
Status: open
Blocked by: —
Test first: no

Three guides, runtime neutral like the others (no `/feature-flow`, `$feature-flow` or `$ARGUMENTS`):

- `guides/brief.md`, for the user's session: how to write the feature brief from the conversation (Feature, What, Why, In scope, Out, The bar, Unsure; every line from the conversation or marked as an assumption; no bar means ask for one), approval 1, saving the brief, running the planner and the plan-reviewer, one more planner round on `PLAN-REVIEW: FAIL`, `PLAN: QUESTIONS`, approval 2 and what it shows, and `plan-accept`. With no conversation to draw on, ask the Step 1 questions from `guides/plan.md` and write the brief from the answers.
- `guides/plan.md`, rewritten for the planner: Step 1 reads the brief instead of asking the user; Step 2 adds outside research with sources; Step 3 keeps the lazy pass but drops the user's yes (the session asks); Step 4 writes into the draft folder, with the brief carried into `spec.md`; Step 5 checks the draft with `FLOW_DIR`; Step 6 is a fixed reply ending `PLAN: READY` or `PLAN: QUESTIONS`. The ticket rules stay word for word.
- `guides/plan-review.md`, for the plan-reviewer: what to check against the brief and how to end.

## Not in this ticket

- The skills that send the session to `guides/brief.md`: tickets 05 and 06.
- The conductor commands the guides name: tickets 03 and 04.

## Done when

- `bash tests/run.sh` checks `brief`, `plan`, `plan-review` in its guides loop and prints `ok guides/brief.md exists`, `ok guides/plan-review.md exists`, and `names no runtime's skill invocation` for each.
- `grep -c 'PLAN: READY' guides/plan.md` prints a number of 1 or more, and `grep -c 'PLAN-REVIEW: PASS' guides/plan-review.md` prints 1 or more.
- All existing tests still pass.

## Reference

- spec.md § Design, § Decisions
- guides/plan.md (the ticket rules section is copied unchanged)

## Answer
