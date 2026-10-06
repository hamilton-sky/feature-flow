# Remove the headless loop

Type: task
Status: open
Blocked by: 12, 13
Test first: no
Floor: allow test-delete

The Claude acceptance run and the successful Codex hand run have proved the replacement in both supported runtimes, so remove what only the headless loop used: `scripts/auto-flow.sh`, `skills/run-flow/`, the old flow skills now living in `guides/` (`skills/next-phase/`, `skills/review-ticket/`, `skills/plan-feature/`, `skills/show-flow/`), the cost log, and the tests that drive them, including the fake `claude` and fake `codex` code that only `auto-flow.sh` used. Keep `flow-status.sh`, `gate.sh`, `floor-guard.sh`, `flow-view.sh` and `flow.sh`. Update `tests/smoke-real.sh` so its non-interactive real-run branches (the ones that start `auto-flow.sh`) are gone and `--interactive` and `--prepare` remain.

Search the repo for every remaining mention (`grep -rn 'auto-flow\|run-flow\|next-phase\|review-ticket\|plan-feature\|show-flow' --exclude-dir=plans --exclude-dir=.git .`) and fix each one outside the README, which ticket 11 rewrites.

## Not in this ticket

- The README: ticket 11.
- `plans/in-session-mode` and `plans/portable-runtime-skills`: retired separately.

## Done when

- `test ! -e scripts/auto-flow.sh && test ! -d skills/run-flow && test ! -d skills/next-phase` succeeds.
- `grep -rln 'auto-flow\|run-flow\|next-phase\|review-ticket' --exclude-dir=plans --exclude-dir=.git --exclude=README.md .` prints nothing.
- `env RUN_REAL=0 bash tests/smoke-real.sh --interactive; echo $?` prints `2`, and `bash tests/run.sh` exits 0.
- Ticket 12's Answer has no `FAIL`, and ticket 13's Answer contains `Codex run finished: yes`; if either runtime did not finish successfully, this ticket stays blocked and the headless loop remains.

## Reference

- scripts/auto-flow.sh, tests/run.sh, tests/smoke-real.sh
- spec.md § Migration and compatibility

## Answer
