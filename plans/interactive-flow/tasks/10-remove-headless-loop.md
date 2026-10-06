# Remove the headless loop

Type: task
Status: open
Blocked by: 12
Test first: no
Floor: allow test-delete, ticket-edit

The Claude acceptance run and the successful Codex hand run have proved the replacement in both supported runtimes, so feature-flow becomes interactive only. Delete every part of the headless flow; nothing may remain, not even unused.

Delete:

- `scripts/auto-flow.sh`, and `skills/run-flow/`.
- The old flow skills now living in `guides/`: `skills/next-phase/`, `skills/review-ticket/`, `skills/plan-feature/`, `skills/show-flow/`.
- The cost log: `flow-cost-<feature>.log` handling in `scripts/flow-view.sh` (and its page template) and the fake cost log `examples/demo.sh` writes.
- The headless settings, everywhere they are read or documented: `FLOW_AGENT` (except `tests/smoke-real.sh --prepare`, which uses it to choose which agent's files to install), `FLOW_AGENTS`, `FLOW_ALLOWED_TOOLS`, `FLOW_CLAUDE_ARGS`, `FLOW_CODEX_ARGS`, `FLOW_COST`, `FLOW_MAX_TOTAL_USD`, `FLOW_MAX_TURNS`, `FLOW_MODEL`, `FLOW_REVIEW`, `FLOW_REVIEW_MODEL`, `FLOW_SLEEP`.
- In `tests/run.sh`: every check that drives `auto-flow.sh` or `run-flow`, and the fake `claude` and fake `codex` executables if nothing else uses them.
- In `tests/smoke-real.sh`: the real-run branches that start `auto-flow.sh`. Keep `--prepare` and `--interactive`, the acceptance harness of this plan, which is the only place allowed to start `claude -p`.
- `plans/in-session-mode/` and `plans/portable-runtime-skills/`, the two plans this one replaced, if they are still in the repo.

`adapters/codex/skill.awk` is already gone (installer ticket) and the README is rewritten in the next ticket, so leave `README.md` alone here.

## Not in this ticket

- The README: ticket 11.

## Done when

- `test ! -e scripts/auto-flow.sh && test ! -d skills/run-flow && test ! -d skills/next-phase && test ! -d skills/review-ticket && test ! -d skills/plan-feature && test ! -d skills/show-flow && test ! -d plans/in-session-mode && test ! -d plans/portable-runtime-skills` succeeds.
- `grep -rlnE 'auto-flow|run-flow|next-phase|review-ticket|codex exec|flow-cost|FLOW_(AGENTS|ALLOWED_TOOLS|CLAUDE_ARGS|CODEX_ARGS|COST|MAX_TOTAL_USD|MAX_TURNS|MODEL|REVIEW|REVIEW_MODEL|SLEEP)\b|claude -p' --exclude-dir=.git --exclude-dir=interactive-flow --exclude-dir=interactive-flow-python --exclude=README.md --exclude=smoke-real.sh .` prints nothing.
- `grep -cE 'auto-flow|run-flow' tests/smoke-real.sh` prints `0`, and `env RUN_REAL=0 bash tests/smoke-real.sh --interactive; echo $?` prints `2`.
- `bash examples/demo.sh` still builds the demo page, and `bash tests/run.sh` exits 0.
- Ticket 12's Answer has no `FAIL`; if the Claude run did not finish successfully, this ticket stays blocked and the headless loop remains. (The Codex hand run was skipped by the user and the Codex runtime stays unverified by hand.)

## Reference

- scripts/auto-flow.sh, tests/run.sh, tests/smoke-real.sh
- spec.md § Migration and compatibility

## Answer
