# Accept a reviewed draft into plans/

Type: task
Status: resolved
Blocked by: 03
Test first: yes

Add `flow.py <feature> plan-accept`: STOP if `plans/<feature>/` already exists (never overwrite), if there is no draft, or if `flow-status --check` fails on the draft (run with `FLOW_DIR` pointing at `.feature-flow/state/draft`). Otherwise copy the draft folder to `plans/<feature>/`, run `--check` there, and print `OK plans/<feature>`. Uses `FLOW_DIR` for the destination like the rest of the conductor. Never commits.

## Not in this ticket

- Merging a draft into an existing plan (spec.md § Scope).
- Committing the plan: the session suggests the commit, as today.

## Done when

- `python3 -m unittest discover -s tests/py` runs new tests: accept copies every draft file and prints `OK plans/f`; it STOPs and copies nothing when the plan folder exists; it STOPs and copies nothing when the draft fails `--check`; it STOPs with no draft.
- `python3 scripts/flow.py` with no arguments prints a usage line that names `plan-accept`.
- All existing tests still pass.

## Reference

- feature_flow/checks.py (`flow_status`), feature_flow/status.py (`FLOW_DIR`)

## Answer

Built: `plan-accept` checks the draft with `checks.flow_status(..., root=draft)` (FLOW_DIR for one call), copies it into FLOW_DIR/<feature> (default plans/), checks again and prints `OK <folder>`. STOPs on an existing plan, no draft, or a failing check, and then copies nothing. Never commits.

Proof: tests/py/test_plan.py: accept copies every file and prints OK plans/g; follows FLOW_DIR=docs/plans; STOPs on an existing plan, without a draft, and on a cyclic draft with plans/g left absent. 107 tests OK.

Shortcuts taken: none.
