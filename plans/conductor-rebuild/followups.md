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

## 07-build-check-pipeline (left for later)

- 1. minor tests/py/test_buildchecks.py: Handle is a hand-written fake of the Conductor surface; a renamed conductor attribute would not be noticed here. Add one test against a real Conductor, or check that Conductor has every attribute Handle provides. (single review)

## 08-phase-classes-and-registry (left for later)

- 1. minor feature_flow/conductor/phases/test.py: Test.scout_questions raises NoPhase where old code returned []; scout-prompt in a tester phase would give NoPhase instead of "no scout k: there are 0". Hard to reach. Fix: return []. (single review)
- 2. minor feature_flow/conductor/phases/base.py: Phase.lane_scoped defaults True, so prompt_text's not-lane_scoped guard is nearly dead. Fix: drop it or comment why. (single review)

## 09-serial-batch-schedulers-and-end-of-run (left for later)

- 1. minor feature_flow/conductor/schedulers/facade_lanes.py: temporary class reaches back into the facade and relies on inheriting SerialScheduler for start_ticket; ticket 10 should replace it outright. (single review)

## 10-lane-scheduler (left for later)

- 1. minor feature_flow/conductor/facade.py: in a run without lanes, a root state phase=merge makes next find Merge, whose judge returns Outcome(None), so next returns None instead of falling to scheduler().next. Only a damaged state file reaches it. Fix: skip merge in that lookup or Stop in Merge.judge without a lane. (single review)
- 2. minor feature_flow/conductor/schedulers/lane.py: LaneScheduler.finish only forwards to self.end.finish(); drop it. (single review)

## 11-guards-and-budget (left for later)

- 1. minor feature_flow/conductor/schedulers/lane.py: guards.before_ticket(c, busy, only=("replan","budget")) drops its return value; a later guard returning a line would be lost. Return it as the serial scheduler does. (single review)
- 2. minor feature_flow/conductor/guards.py: before_ticket's only= silently skips unknown names; check them against the known guards. (single review)

## 12-workspace-in-place-of-in-lane (left for later)

- 1. minor feature_flow/conductor/workspace.py Workspace.__getattr__: still forwards every missing name to the Conductor; an allow-list would enforce the lane view. (single review)
- 2. minor feature_flow/conductor/workspace.py _working_in: two call sites (entered, flow_code); ticket 15 should remove both. (single review)
- 3. minor tests/py/test_schedulers.py:304 stale "as in_lane gives it" comment. (single review)

## 13-cwd-keyword-in-the-helpers (left for later)

- 1. minor feature_flow/gate.py: a cwd with no plan makes the gate print "nothing to run" and exit 0; ticket 15 passes lane folders, so fail when cwd is given and is not a folder. (single review)
- 2. minor feature_flow/proc.py, feature_flow/checks.py: a missing cwd makes Popen raise FileNotFoundError out of checks.smoke/gate instead of a failing Result. (single review)
- 3. minor feature_flow/floorguard.py, feature_flow/status.py: _under defined twice with the same body. (single review)
