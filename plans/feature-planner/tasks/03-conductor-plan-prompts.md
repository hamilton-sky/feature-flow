# Serve the planner and plan-reviewer prompts from the conductor

Type: task
Status: resolved
Blocked by: 01, 02
Test first: yes

Add two commands to `feature_flow/cli.py` and `feature_flow/conductor.py`, built in `feature_flow/prompts.py` the way `prompts.build` builds the builder's prompt (role body, guide, a task line):

- `flow.py <feature> plan-prompt <brief> [findings]`: STOP if `plans/<feature>/` exists or the brief cannot be read. Copies the brief to `.feature-flow/state/brief-<feature>.md`, clears `.feature-flow/state/draft/<feature>/` (only that folder) on a first round (no findings), and prints the feature-planner role, `guides/plan.md`, the brief, any findings, and a task line naming the draft folder.
- `flow.py <feature> plan-review-prompt`: STOP if there is no saved brief or no draft. Prints the plan-reviewer role, `guides/plan-review.md`, the brief and the draft folder.

Neither takes `FLOW_SESSION` and neither keeps state beyond the brief and the draft (spec.md § Decisions).

## Not in this ticket

- `plan-accept`: ticket 04.
- `start` still prints `PLAN` when there is no plan; the skill decides what follows.

## Done when

- `python3 -m unittest discover -s tests/py` runs new tests: `plan-prompt` prints the planner role and the brief and exits 0; it STOPs with exit 1 when the plan folder exists; a second round with findings keeps the draft; `plan-review-prompt` STOPs without a draft and prints the reviewer role with one.
- `python3 scripts/flow.py` with no arguments prints a usage line that names `plan-prompt` and `plan-review-prompt`.
- All existing tests still pass.

## Reference

- feature_flow/prompts.py, feature_flow/cli.py, feature_flow/conductor.py (`prompt`), feature_flow/state.py
- spec.md § Design

## Answer

Built: `plan-prompt <brief> [findings]` and `plan-review-prompt` in feature_flow/cli.py and conductor.py; `prompts.plan` builds both from the role file, the guide (with <feature> and <draft> filled in), a task line and the brief. The brief is saved to .feature-flow/state/brief-<feature>.md; a first round clears .feature-flow/state/draft/<feature>/ and only that.

Proof: `python3 -m unittest discover -s tests/py` runs tests/py/test_plan.py (planner prompt, STOP on an existing plan and a missing brief, findings round keeps the draft, reviewer prompt needs a brief and carries no planner text, usage names the commands). 107 tests OK; `bash tests/run.sh` 429 passed.

Decisions: built together with ticket 04 in one commit, since both change the same three files.

Shortcuts taken: none.
