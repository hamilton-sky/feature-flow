# Learnings: proven-checks

Things a fresh worker would otherwise waste time rediscovering: a command that works, a
trap, a quirk of the environment. Append one or two lines, newest last, tagged with your
ticket number. Never edit or delete another line. Keep it short; a human prunes it.

- (01) `tests/run.sh` allows only listed stdlib modules in `feature_flow/` imports (no `collections`: use `dataclasses`); the unittest suite alone does not catch it.
- (02) `tests/py` Repo tests that call `prompt` need `agents/` and `guides/` copied in and committed first, or `next` STOPs on a dirty tree. Running the full suite plus `tests/run.sh` takes about 2 minutes: run it in the background.
- (03) In-process `cli.main` tests must patch `Conductor.check_code` (the code hash covers the checkout's feature_flow, not the temp repo's copy); `FLOW_GATE_TIMEOUT` is whole minutes, so a 0.02 minute timeout needs a patched `proof.test_first`.
- (04) Tests that drive a ticket through REVIEW now need two PASS verdicts (spec, then quality) before the next BUILD; a test that sets state `limit=` needs 3 per round, not 2.
- (05) A test for a send-back build prompt can use a real failing gate: add a `Test:` command to `commands.md` and commit a `FAILING` file (see `tests/py/test_debug.py`).
