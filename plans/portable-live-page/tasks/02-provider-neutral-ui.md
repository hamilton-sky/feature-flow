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
