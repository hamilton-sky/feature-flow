# Follow-ups: conductor-rebuild

What the run left for later: minor findings of passing reviews, the findings a level 2 ticket passed with after 2 review rounds, and Done when checks this host could not pass. Each is a candidate for a cleanup ticket.

## 01-golden-runs (left for later)

- 1. minor tests/py/test_golden.py: the fixture guide uses the literal placeholder `<sha>`, which is also the text the SHA cleaner writes in place of real shas, so a prompt that stopped filling `<sha>` would not change the recordings. Have the cleaner write a marker no guide uses (e.g. `<SHA>`), then re-record, before ticket 03 moves code. (single review)

## 03-make-the-conductor-a-package (left for later)

- deferred check, needs the build module (pip install build) and the network: `python3 tests/package_smoke.py` (here: exit 1)
- 1. minor feature_flow/conductor/planning.py: Planner copies the conductor's attributes once when built; safe because it is built fresh on every call. A later ticket that caches a Planner would read stale scouts_on and paths. (single review)

## 04-settings-and-mode-rules (left for later)

- 1. minor feature_flow/conductor/facade.py: Conductor.__init__ overwrites self.per_session with session_limit(driver), so self.settings.per_session (4) and self.per_session (0) disagree for an agent driver; a later ticket reading self.settings.per_session gets the wrong value. Document settings.per_session as the raw value, or have callers use session_limit. (single review)
- 2. minor feature_flow/conductor/settings.py: mode_ok rebuilds the name->rule dict on every call; build it once at module level. (single review)

## 05-typed-state-views (left for later)

- 1. minor feature_flow/conductor/store.py: TicketState for lane 0 has prefix "", so clear() deletes every key including RUN_KEYS and other lanes' keys. It matches the old dict.clear() and clear() is only called inside in_lane today, but once ticket 12 hands views to phases this is a data-loss trap. Make lane-0 clear() drop only non-RUN_KEYS, non-L<k>. keys, or refuse it. (single review)
- 2. minor feature_flow/conductor/facade.py: Conductor.num now calls self.st.num(key), so with a plain dict in self.st (as test_proof sets it) num() raises AttributeError where it used to work. Use store.number(self.st.get(key, "0"), key, self.state_file) so any mapping works. (single review)

## 06-pure-level-and-review-policies (left for later)

- 1. minor feature_flow/conductor/facade.py (judge_build): small_note() and proof.review_mode(ticket_at_base()) are now evaluated before the defer decision, so a level 0 ticket in fast mode or with the gate off pays for extra git work that is thrown away. Compute small_note only when it can be used, or pass a thunk. (single review)
- 2. minor feature_flow/conductor/policy/review.py: after_checks takes nine positional arguments and the facade passes them by position; swapped flags would go unnoticed. Pass them as keyword arguments at the call site. (single review)
