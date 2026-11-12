# Route the shared live UI through Claude and local adapters

Type: task
Status: open
Blocked by: 01
Test first: yes
Level: 3
Floor: allow flow-edit
Touches: packages/forkboard/forkboard/assets/providers.js (new), packages/forkboard/forkboard/assets/live.js, packages/forkboard/forkboard/assets/live.css, packages/forkboard/forkboard/page.py, packages/forkboard/forkboard/cli.py, packages/forkboard/tests/test_page.py, packages/forkboard/tests/test_cli.py, packages/forkboard/tests/browser/page.test.js, packages/forkboard/forkboard/storage.py, packages/forkboard/forkboard/live.py, packages/forkboard/tests/test_storage.py, packages/forkboard/tests/test_live.py

Implement the provider contract from spec.md around the existing live.js behavior, using the stable backend from 01. Extract only provider capability access into providers.js; preserve the Claude use/artifact.publish SHA/user/sample APIs and denied/read-only behavior. Keep render's old live Boolean and CLI live default native behavior; add explicit provider and escaped agent-label configuration. Replace user-facing agent strings and provenance labels with configured labels, preserving old via=claude state.

Local diagram requests join the persistent asks queue with graph/source context rather than calling a model. Show queued/answered states and explicit proposal preview; saving the proposal remains deliberate. Keep native sample-based diagram editing. Serialize saves, retain pending operations across reload/error, handle a single conditional conflict replay against latest state, and show safe retry on a repeated conflict. Reject stale figure-source replay. Idempotent request IDs prevent duplicate asks.

Poll state/page metadata at a bounded two-second cadence, reconnect with backoff, update answers without destructive redraw, and preserve editor state, form text and pending saves. Use a visible update-available state for unsafe page replacements. Expose connection/read-only status accessibly, with keyboard controls and live announcements. Extend the existing Chromium test entry rather than adding an unexecuted JS suite: cover both actual localhost transport and mocked native transport, save/conflict/queue/reply/pick behavior, denied capabilities, escaped labels and dirty-edit refresh.

Preserve v0.35 five-tab behavior: stage per-tab choices until Approve sends the existing compound picks/approve/ask change atomically; Change sends unapprove plus reopen ask. Extend storage validation/transactions to these exact upstream payloads against the latest document, with all-or-nothing failure, idempotent retry and server-owned identity/time. Keep approved state across regeneration. Preserve ask.about for option/ticket context and labels for either agent. Plan Approve is user intent, never server execution. Accepted-plan controls stay frozen even for crafted local API requests. Cover native/local approve, reopen, list-valued picks and pending choices across refresh/conflict.

## Not in this ticket

- FeatureFlow source discovery and trusted automatic phase regeneration belong to 03; tests here use Forkboard documents and the backend.

## Done when

- `python3 -m unittest discover -s packages/forkboard/tests -v` prints `OK`, preserving static/native rendering and provider CLI compatibility.
- `npm --prefix packages/forkboard/tests/browser test` prints `# fail 0`, exercising native adapter parity and a real localhost backend without external network/model calls.
- Dirty diagrams and typed requests survive polling, conflict and disconnection; local queued proposals require explicit preview/save.

```check
$ python3 -m unittest discover -s packages/forkboard/tests -v
exit 0
prints OK
$ npm --prefix packages/forkboard/tests/browser test
exit 0
prints # fail 0
```

## Reference

- spec.md (read-only)
- packages/forkboard/forkboard/assets/live.js (read-only)
- packages/forkboard/tests/browser/page.test.js (read-only)

## Answer


**Built**

- Added `assets/providers.js` with Claude capability and local HTTP adapters; embedded it before the shared live layer. Renderer and CLI accept explicit provider/escaped agent labels, retaining the native Boolean/default/fragment behavior.
- Updated `assets/live.js`/`live.css`: serialized persistent operation queue, one conditional conflict replay, retained retry controls, two-second polling with capped reconnect backoff, non-destructive reply updates, preserved form/editor/staged choices, accessible status and update preview, local diagram requests and deliberate proposal preview/save. Native sampling, SHA publication, profiles, denied/read-only behavior and legacy claude provenance remain supported.
- Updated `live.py` and `storage.py`: regeneration records trusted available steps/choices/frozen metadata; compound approval and reopen validate against that latest metadata under the transaction lock. List choices, ask.about, server-owned identity/time, operation deduplication and all-or-nothing rejection are covered.
- Extended renderer/CLI/storage tests and the executed Chromium entry with actual loopback Python transport, plus native denial/sampling tests.

Extra file: packages/forkboard/tests/test_server.py - its existing concurrency test picked an undeclared profile choice. The fixture now declares that actual available choice, preserving the existing stale-write/retry assertions while enabling rejection of unknown keys against trusted documents.

**Proof**

- Start: `5d3f28e6d9c6d2095c393e2bd0d3bacf5963d9e3`. Test-only commit `dbc06bc` preceded production changes. Fresh `python3 -m unittest discover -s packages/forkboard/tests -v` failed with missing renderer provider argument, rejected CLI flags and rejected compound/about operations (61 tests, one failure, three errors). Test-only commit `7304431` adds actual local browser contracts; the browser command failed its two new local cases on the missing provider flags, while all six existing tests passed.
- Done when 1/check: final fresh `python3 -m unittest discover -s packages/forkboard/tests -v`: 62 tests, `OK`, exit 0, 4.067s. Covers static/native rendering, explicit provider/label CLI, list approvals/reopen, idempotent retry, frozen controls, unknown choices and malformed compounds without any committed mutation.
- Done when 2/check: final fresh `NODE_OPTIONS=--test-reporter=tap npm --prefix packages/forkboard/tests/browser test`: 12 tests, `# pass 12`, `# fail 0`, zero skipped/cancelled/todo, exit 0, 19.069s. NODE_OPTIONS selects TAP output only; no test configuration was changed. Both mocked Claude and actual subprocess Python localhost transport run without external network/model calls.
- Done when 3: the same final browser run verifies that diagram requests persist graph/source snapshots; polling a graph reply leaves the dirty editor and typed question unchanged; Preview changes only the editor and Save persists the version. Additional browser cases prove a repeated conflict retains one stable request ID across reload, disconnected editor/text/list picks survive reconnect and regeneration, local approve/reopen are atomic, and changed figure sources block replay with the dirty graph intact and zero saved versions.
- Frozen Python 3.9 syntax Lint: exit 0. `git diff --check`: exit 0. Full frozen Test: left to the conductor's gate. No self-review performed.

**Decisions**

- Local state identity and strong ETag come from the backend. The persistent queue stores the entire stable-ID envelope before sending; successful operations leave the queue only after acknowledgement. A conflict fetches latest state and retries once; a second conflict, unavailable backend or stale figure retains the operation for visible retry.
- `live.state` persists `_document = {steps, choices, frozen}` from the trusted renderer input. Browser operations cannot change this metadata. Approval requires every choice from the current step exactly once and an approval ask; reopen requires the completed step and its complete following suffix plus the matching reopen ask. Accepted settings reject choice/approval/reopen operations. Native operations retain their existing payload shape.
- Page HTML replacement is treated conservatively: display an update-available control and open the newly generated page in a separate sandboxed preview while leaving the current editor/forms/queue intact. State replies update in place; the page never silently loads a proposed graph or replaces dirty content.

**Shortcuts taken**

- Page regeneration is always reviewed in the separate preview, even when the current page happens to be clean. This avoids guessing whether a whole new document can be merged safely. A future safe document-swap mechanism would be worthwhile if users need to promote regenerated navigation into the editable view without reloading.

**For later tickets**

- Ticket 03 should supply `doc['frozen'] = True` on accepted-plan/build documents (or a recognized `doc['phase']`: accepted/build/complete/completed), and continue regenerating with `live.state` inside `storage.transaction` so the trusted available controls stay current. The shared UI and local API both respect `_document.frozen`; questions remain allowed. Accepted Plan Approve is intent only and executes no work.
- Renderer signature is additive: `render(..., fragment=False, live=False, provider='claude', agent_label=None)`. Old positional callers are unchanged. Local CLI renders a full HTML document; native keeps its fragment. New assets ship through existing asset globs.
- Local queued graph asks include the editor's original source context. Never replace it with a newly polled source when retrying. Graph proposals retain the ask's fingerprint and require explicit preview then Save as my version.

## Review findings (round 1, footprint check)

the build changed paths outside the ticket's `Touches:` line (packages/forkboard/forkboard/assets/providers.js (new) packages/forkboard/forkboard/assets/live.js packages/forkboard/forkboard/assets/live.css packages/forkboard/forkboard/page.py packages/forkboard/forkboard/cli.py packages/forkboard/tests/test_page.py packages/forkboard/tests/test_cli.py packages/forkboard/tests/browser/page.test.js packages/forkboard/forkboard/storage.py packages/forkboard/forkboard/live.py packages/forkboard/tests/test_storage.py packages/forkboard/tests/test_live.py): packages/forkboard/tests/test_server.py. tickets run side by side because their Touches do not overlap, so change only what Touches names. if the ticket cannot be done inside it, say so in the Answer and stop: the plan has to change, not the footprint. one file the ticket truly needs (a test that pins the old behaviour, a generator) may be named in the Answer as `Extra file: <path> - <why>`, when it is the only one
