# Follow-ups: conductor-rebuild

What the run left for later: minor findings of passing reviews, the findings a level 2 ticket passed with after 2 review rounds, and Done when checks this host could not pass. Each is a candidate for a cleanup ticket.

## 01-golden-runs (left for later)

- 1. minor tests/py/test_golden.py: the fixture guide uses the literal placeholder `<sha>`, which is also the text the SHA cleaner writes in place of real shas, so a prompt that stopped filling `<sha>` would not change the recordings. Have the cleaner write a marker no guide uses (e.g. `<SHA>`), then re-record, before ticket 03 moves code. (single review)

## 03-make-the-conductor-a-package (left for later)

- deferred check, needs the build module (pip install build) and the network: `python3 tests/package_smoke.py` (here: exit 1)
- 1. minor feature_flow/conductor/planning.py: Planner copies the conductor's attributes once when built; safe because it is built fresh on every call. A later ticket that caches a Planner would read stale scouts_on and paths. (single review)
