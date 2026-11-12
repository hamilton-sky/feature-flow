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
