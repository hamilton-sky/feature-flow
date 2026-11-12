# Expose all live phases and reuse agent commands safely

Type: task
Status: open
Blocked by: 01, 02
Test first: yes
Level: 3
Floor: allow flow-edit
Touches: feature_flow/brainstorm_page.py, feature_flow/flow_page.py, feature_flow/flow_plan.py, feature_flow/command.py, feature_flow/status.py, tests/py/test_brainstorm_page.py, tests/py/test_flow_page.py, tests/py/test_flow_plan.py, tests/py/test_portable_live_page.py (new), packages/forkboard/tests/browser/page.test.js

Wire FeatureFlow launch flags and existing status --page/--brainstorm-page aliases to the local adapter/backend from 01 and 02. Reuse folder selection, flow_page.document, flow_plan.sections/build_section and existing apply_picks validation. Generate a plan-derived base document when draft/accepted tasks exist without brainstorm Markdown; mark earlier steps not used and never create a synthetic brainstorm. Keep accepted-plan precedence and FLOW_DIR behavior. State-only questions/replies and draft plan picks must work without Markdown; diagram apply requires an actual brainstorm source and preserves fingerprint checks.

Route FeatureFlow answer/answer-graph and live regeneration through the same storage transaction used by HTTP, including concurrent source regeneration versus browser save. Add --serve DIR and --port with a trusted feature-bound render callback: on read-only refresh inspect relevant brainstorm/spec/map, commands and ticket contents and regenerate only changed content. Read ticket status dynamically so active and completed Build become visible within five seconds. Keep source/state/page revisions coherent and do not overwrite a newer reply or attach old versions to new figure sources.

Browser picks remain proposals; --picks applies only existing valid setup/draft settings and never approves, edits accepted commands/tickets or disables a gate. Approval/reopen requests retain upstream structured step/approve/about context. Page Plan Approve is the user's yes for agent processing, never an HTTP build/commit. Change cannot bypass an accepted plan's freeze. Refresh document composition from the latest approved state under the shared transaction, preserve list-valued picks (helpers/full_review), option picks and ask.about, and retain flow_plan's current read-only Plan vs reality output. Watch the run log plus decisions/followups alongside tickets so reality refresh is timely; do not write those inputs. No-brainstorm flows mark Style/Team/Options not used, support Plan Approve and ticket questions, and never fabricate a brainstorm. Add integration tests for brainstorm, draft, accepted/active and completed Build, with and without brainstorm, invalid picks, accepted setting protection and subprocess races. Extend the existing browser entry with actual FeatureFlow phase fixtures including dirty-editor-safe refresh.

## Not in this ticket

- Conductor approval rules and execution policy stay in the conductor; this ticket exposes existing behavior without adding an approval endpoint.

## Done when

- `python3 -m unittest discover -s tests/py -p "test_*page.py" -v` prints `OK`, proving launch/request operations and plan-only phase support.
- `python3 -m unittest discover -s tests/py -p "test_flow_plan.py" -v` prints `OK`, proving draft validation and immutable approved settings.
- `npm --prefix packages/forkboard/tests/browser test` prints `# fail 0`, including external ticket status refresh, answer delivery and draft-to-build phase changes.

```check
$ python3 -m unittest discover -s tests/py -p "test_*page.py" -v
exit 0
prints OK
$ python3 -m unittest discover -s tests/py -p "test_flow_plan.py" -v
exit 0
prints OK
$ npm --prefix packages/forkboard/tests/browser test
exit 0
prints # fail 0
```

## Reference

- spec.md (read-only)
- feature_flow/brainstorm_page.py (read-only)
- feature_flow/flow_page.py (read-only)
- feature_flow/flow_plan.py (read-only)

## Answer

**Built**: Updated `feature_flow/brainstorm_page.py` to expose local provider, agent label, server/port, graph answers and plan-only rendering, with shared-lock regeneration and transactional replies. Added phase, validation, accepted-freeze and subprocess concurrency tests in `tests/py/test_portable_live_page.py`, and an actual FeatureFlow browser refresh/answer/dirty-editor fixture in `packages/forkboard/tests/browser/page.test.js`. Existing aliases delegate to the same command.

**Proof**: Starting commit `4486878236f73145db6472786453eaf00e2dde4d`; test-only commit `9e0c39a` failed the new plan-only launch test on the missing provider flag. Fresh `python3 -m unittest discover -s tests/py -p "test_*page.py" -v`: 30 tests, OK, exit 0. Fresh `python3 -m unittest discover -s tests/py -p "test_flow_plan.py" -v`: 6 tests, OK, exit 0. Fresh `npm --prefix packages/forkboard/tests/browser test` with supplied TAP environment: 22 tests, # fail 0, exit 0; the FeatureFlow fixture observes an agent answer and draft-to-complete update while preserving dirty graph and text. The phase tests exercise draft, active and complete with and without brainstorm, invalid gate picks, accepted freeze, and parallel subprocess answers/regenerations. Python 3.9 syntax Lint passed. Full Test left to the conductor's gate.

**Decisions**: Compose the document inside the same cross-process storage lock used by HTTP, using the latest approved state and replacing state and HTML under that lock. The refresh callback compares rendered content before regeneration; it reads the existing phase composition on each poll, including ticket and reality inputs. Accepted plans freeze page choices, while valid draft picks retain the existing validators.

**Shortcuts taken**: Regeneration uses the storage module's lock, validation and atomic-replacement primitives directly because its transaction helper takes a precomputed page; a shared helper that accepts a page computed under the lock would remove that duplication if the storage API is extended.

**For later tickets**: The page uses the same existing status aliases; documentation should include `--serve`, `--port`, `--provider`, `--agent-label`, and `--answer-graph`. Preserve the shared lock and latest-state composition when adjusting regeneration.

## Review findings (round 1, pair review)

QUALITY
1. major feature_flow/brainstorm_page.py: A POST can arrive after plan acceptance but before the next /api/page refresh. It is then checked against the old, unfrozen document and can record picks or an approval after acceptance. Refresh and validate the accepted-plan state under the same lock as the mutation.
2. major feature_flow/brainstorm_page.py: Regeneration replaces state.json before index.html. If the second replacement fails or the process stops, the new state is paired with the old page. Use recoverable, coordinated publication of both files.

Probed inputs: feature and path arguments, provider and port, state and page files, source and plan files, answers and graph proposals, picks, approvals, and concurrent refresh and browser writes. All three specified checks passed.

REVIEW: FAIL

SPEC
- Page tests: MET (conductor) — the conductor reported the check passed.
- Flow plan tests: MET (conductor) — the conductor reported the check passed.
- Browser tests: MET (conductor) — the conductor reported the check passed.
- Scope: OK.
- Test first: OK — the diff adds tests, and the conductor observed the test command fail before the production change.

REVIEW: PASS
