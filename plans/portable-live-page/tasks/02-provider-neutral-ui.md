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

### Delayed-save draft repair (2026-11-12)

**Built**: Started clean at `73988b1e608fe48b30638646d597a2a6adb85e32`. Changed `assets/live.js` so Talk, local diagram asks, native diagram proposals, option asks and ticket asks capture the exact submitted draft and clear only when the current field still equals it. Added eight Chromium regressions spanning all four fields on local and native providers.

**Proof**:

- Test-only commit `d1f02a0` preceded the production fix. Fresh focused command `node --test --test-name-pattern='delayed' packages/forkboard/tests/browser/page.test.js` with supplied PATH/TAP environment failed all eight cases before the fix: actual field `''`, expected `second unsent request`. After the fix the same eight passed. Tests explicitly gate request/proposal completion, rather than relying on sleeps.
- Done when 1/check: fresh `python3 -m unittest discover -s packages/forkboard/tests -v` passed 62 tests, `OK`, exit 0, 4.239s, with supplied venv on PATH.
- Done when 2/check: fresh `npm --prefix packages/forkboard/tests/browser test` with supplied PATH and `NODE_OPTIONS=--test-reporter=tap` passed 20 tests, `# pass 20`, `# fail 0`, no cancelled/skipped/todo, exit 0, 20584.503417ms. Each new case preserves a newer draft after success, verifies only the first request was saved (where applicable), and verifies an unchanged draft with surrounding whitespace still clears after success.
- Done when 3: the same browser run passed existing dirty diagram/polling/reply/explicit proposal tests, disconnection/regeneration retention, conflict/retry/reload and stale-source protection, plus delayed-response draft retention for both providers.
- Frozen Python 3.9 syntax Lint and `git diff --check`: exit 0. Full frozen Test is left to the conductor's gate; fast OFF does not mean gate OFF. No self-review performed.

**Decisions**: Compare against the raw draft captured before trimming; the persisted request remains trimmed, while unmodified whitespace-bearing fields still clear normally. Successful callbacks continue to re-enable controls and show acknowledgement even when a newer draft remains.

**Shortcuts taken**: none.

**Review fixes**: Round-3 blocker: reproduced the data loss for all four field types on both hosts before changing logic. Guarded every asynchronous request-field clear, including native sampling, against the exact submitted value; deterministic delayed-response regressions pass. Prior footprint and TAP environment requirements remain documented above.

**For later tickets**: Preserve these conditional clears when changing shared request UI. No provider/backend contracts changed.

## Review findings (round 1, footprint check)

the build changed paths outside the ticket's `Touches:` line (packages/forkboard/forkboard/assets/providers.js (new) packages/forkboard/forkboard/assets/live.js packages/forkboard/forkboard/assets/live.css packages/forkboard/forkboard/page.py packages/forkboard/forkboard/cli.py packages/forkboard/tests/test_page.py packages/forkboard/tests/test_cli.py packages/forkboard/tests/browser/page.test.js packages/forkboard/forkboard/storage.py packages/forkboard/forkboard/live.py packages/forkboard/tests/test_storage.py packages/forkboard/tests/test_live.py): packages/forkboard/tests/test_server.py. tickets run side by side because their Touches do not overlap, so change only what Touches names. if the ticket cannot be done inside it, say so in the Answer and stop: the plan has to change, not the footprint. one file the ticket truly needs (a test that pins the old behaviour, a generator) may be named in the Answer as `Extra file: <path> - <why>`, when it is the only one


## Attempt note (footprint send-back)

The clean continuation started at `5c25a7f`. No production or test changes were necessary or made. Reproduced the finding with the real `feature_flow.conductor.buildchecks.Footprint.run`, the prescribed base `5d3f28e6d9c6d2095c393e2bd0d3bacf5963d9e3`, current ticket and lane 0: fast mode emitted `FOOTPRINT-FAIL` and the exact reported outside path, `packages/forkboard/tests/test_server.py`. The same check with fast mode disabled emitted `FOOTPRINT-EXTRA` and returned no failure. `EXTRA.findall` already recognizes the existing `Extra file:` line and its complete reason. The checker permits a single declared exception only when both lane and fast mode are disabled.

The fixture change is necessary: the preexisting concurrency test picks `profile=standard`; trusted document validation now requires that choice to be declared. Its assertions remain intact. Reverting that declaration or weakening validation would break the required behavior. The ticket remains open because this run mode rejects its documented exception. The trusted conductor must rerun in standard, single-ticket mode to evaluate the existing exception and run the remaining checks; no ticket footprint, plan, checker, test or configuration was changed. No self-review performed.


### Standard-mode continuation (2026-11-12)

**Built**: Started clean at `c93bc00d6c309b6e380f97e114ebf076b5158caf`. Retained the existing provider/UI/backend implementation and test fixture; no production or test changes were needed. This continuation changes only this ticket's Status/Answer and an appended map decision.

**Proof**:

- Done when 1/check: fresh `python3 -m unittest discover -s packages/forkboard/tests -v` completed with `Ran 62 tests in 3.924s`, `OK`, exit 0. Static/native rendering, provider/label CLI compatibility, approval/reopen validation and the actual concurrent HTTP fixture all passed.
- Done when 2/check: fresh `NODE_OPTIONS=--test-reporter=tap npm --prefix packages/forkboard/tests/browser test` completed with 12 tests, `# pass 12`, `# fail 0`, zero cancelled/skipped/todo, exit 0 (18754.722958ms). NODE_OPTIONS selects the reporter only, as already documented in learnings; the executed test command and configuration remain unchanged.
- Done when 3: that fresh browser run passed local queue/reply/proposal, repeated conflict/reload/idempotency, disconnect/regeneration/dirty form and staged-choice retention, and stale figure-source cases. The tests assert no automatic proposal save, preserved editor/text through polling and disconnection, stable retry IDs, and zero saved versions after stale-source replay rejection. Native capability denial and native deliberate proposal save also passed.
- Frozen Python 3.9 syntax Lint: exit 0. Full frozen Test remains left to the conductor's gate. No self-review performed.

**Decisions**: Retain the single necessary declared fixture extension. Fast mode is now off per the trusted conductor; a fresh direct execution of `feature_flow.conductor.buildchecks.Footprint.run` with the prescribed base `5d3f28e6d9c6d2095c393e2bd0d3bacf5963d9e3`, lane 0 and fast false emitted `FOOTPRINT-EXTRA` and returned `(None, '', [exception note])`. No checker, plan, conductor state or test configuration was changed.

**Shortcuts taken**: none in this continuation; the implementation's deliberate separate update preview remains documented above.

**Review fixes**: Round-1 footprint finding: reproduced and verified the existing `Extra file:` declaration under standard single-ticket mode. `test_server.py` changes only its trusted fixture to declare the `profile=standard` choice already used by the concurrency scenario; its stale-write/retry assertions remain intact. The fresh 62-test run passed that scenario. The historical fast-mode Attempt note is superseded by this standard-mode proof; independent review still judges the necessity of the exception.

**For later tickets**: No new contract changes. Ticket 03 should use the existing trusted document/frozen metadata and shared transaction seam described above.

## Review findings (round 2, done when)

$ npm --prefix packages/forkboard/tests/browser test
  wanted: exit 0 and output containing '# fail 0'
  got: exit 0
  the last lines of its output:

> test
> node --test page.test.js

✔ the editor adds, connects, renames, deletes, undoes and resets (461.632792ms)
✔ Arrange lays the boxes out four ways, without overlaps, and undo puts them back (417.787917ms)
✔ every theme draws the page, and a theme shapes the boxes (920.810875ms)
✔ at phone width nothing scrolls sideways (63.816125ms)
✔ the live page saves a version, and a clash reloads and saves the change again (293.617792ms)
✔ a live page with steps shows them as tabs, saves picks only on Approve, and Change takes an approval back (450.486625ms)
✔ local queue, reply and explicit proposal preserve dirty edits and typed text during polling (5129.259834ms)
✔ local staged list choices approve atomically and survive polling (2680.415125ms)
✔ native capability denial becomes accessible read only and native generation remains a deliberate save (267.840083ms)
✔ local repeated conflict retains an idempotent queue through reload and serializes retry (356.20175ms)
✔ local dirty edits, forms and staged picks survive disconnect and unsafe regeneration (6773.249375ms)
✔ local figure source change blocks blind conflict replay without discarding the editor (345.404292ms)
ℹ tests 12
ℹ suites 0
ℹ pass 12
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 18484.033


### Reporter-output send-back (2026-11-12)

**Built**: Started clean at `bdc7ffce83bbfee1b553de63e5f8183bea0564c7`. No production, test or configuration changes were required. Updated only this ticket bookkeeping and appended a map decision.

**Proof**:

- Done when 1/check: fresh `python3 -m unittest discover -s packages/forkboard/tests -v` with the supplied venv on PATH passed all 62 tests, `Ran 62 tests in 3.965s`, `OK`, exit 0.
- Done when 2/check: fresh `NODE_OPTIONS=--test-reporter=tap npm --prefix packages/forkboard/tests/browser test` passed all 12 tests, `# pass 12`, literal `# fail 0`, zero cancelled/skipped/todo, exit 0, 18640.403292ms.
- Done when 3: that browser run passed the local queue/reply/explicit proposal case, repeated conflict/reload/idempotency case, dirty edits/forms/staged picks through disconnection/regeneration case, and changed-source replay rejection case. Native denial and deliberate native proposal save passed too.
- Frozen Python 3.9 syntax Lint: exit 0. Full frozen Test is left to the conductor's gate; fast OFF does not mean gate OFF. No self-review performed.

**Decisions**: The conductor must inherit `NODE_OPTIONS=--test-reporter=tap` when evaluating the unchanged browser command/check on this installed Node. The default spec reporter reports `ℹ fail 0`, while the frozen check explicitly requires `# fail 0`; successful tests alone do not satisfy that literal-output check. Environment-only TAP selection preserves every test and assertion.

**Shortcuts taken**: none.

**Review fixes**: Round-2 done-when finding: read the recorded default-reporter failure (exit 0, all 12 passing, wrong output marker), then reran the exact npm command under the supplied TAP environment and observed the required marker. This is an execution-environment requirement, not a claim that the default reporter now passes the check. The conductor must retain this environment for its own check and gate. Round-1 standard-mode fixture exception remains documented above.

**For later tickets**: Retain the documented TAP reporter environment for literal-output browser checks. No implementation contracts changed.

## Review findings (round 3, pair review)

QUALITY
1. blocker packages/forkboard/forkboard/assets/live.js:369: Successful saves erase newer unsent text. Chromium reproduction: delay publish, submit “first request”, type “second unsent request”, then complete publish; only the first request persists and the textarea becomes empty. The diagram and option-question callbacks have the same pattern. Clear fields only when their contents still match the submitted draft.

Both Done when suites passed: 62 Python tests and 12 browser tests. Boundary checks covered operation fields, identity, revisions, source fingerprints, choices, compound approvals, frozen controls, graph validation, routes, Host/Origin and escaped labels. The test_server.py fixture adjustment supports trusted-choice validation without weakening concurrency assertions.

REVIEW: FAIL

SPEC
- Python suite: MET (conductor) - python3 -m unittest discover -s packages/forkboard/tests -v passed and printed OK; not rerun.
- Chromium suite: MET (conductor) - npm --prefix packages/forkboard/tests/browser test passed with supplied TAP environment and printed # fail 0; not rerun.
- Dirty diagrams, typed requests, conflicts/disconnection and deliberate proposal preview/save: MET (conductor) - inspected the passing browser cases and their assertions for these behaviors.
- scope: OK - test_server.py necessarily declares the choice exercised by its existing concurrency test after trusted-document validation; map/learnings changes are ticket bookkeeping.
- test first: OK - new browser/storage tests require the production changes; conductor observed the Test command fail before implementation.

Reviewed through 5bd7ad914cd8d29805f7dc58babc0f719ed74f45, currently HEAD. Acceptance failures include future FeatureFlow work and obsolete fixture assumptions; the stale duplicate-operation expectation also contradicts the ticket's idempotent retry requirement.

Author-written reporter proof embedded under Review findings was encountered; no verdict had formed before that exposure. No files changed.

REVIEW: PASS

## Review findings (round 4, pair review)

QUALITY
1. major packages/forkboard/forkboard/assets/live.js:76: A stale-source operation permanently blocks the save queue. Retry and reload retain the same impossible head operation, preventing subsequent questions, choices and valid diagram saves. An in-memory probe using the actual flush functions left both operations pending with zero provider calls after retry. Add explicit cancellation/recovery that preserves the old edit while allowing unrelated operations through.

Probed source fingerprints, queued envelopes, retry/reload persistence, identity/time, compound approval/reopen fields, choice values, frozen controls, provider configuration and escaped labels. Both Done commands passed: 62 Python tests and 20 Chromium tests. Working tree remains clean; no retained artifacts observed. The concurrency fixture adjustment supports the stricter trusted-choice validation.

REVIEW: FAIL

SPEC
- Python suite: MET (conductor) — python3 -m unittest discover -s packages/forkboard/tests -v passed.
- Browser suite: MET (conductor) — npm --prefix packages/forkboard/tests/browser test passed.
- Dirty diagrams, typed requests and explicit proposals: MET — targeted Chromium runs covering polling/proposal, repeated conflict, disconnection/regeneration and stale source printed # pass 3, # pass 1, and # fail 0.
- scope: OK — test_server.py fixture adjustment is necessary because trusted document validation now rejects undeclared choices. Remaining changes implement the ticket or update its tracking files.
- test first: OK — added browser/storage tests require production changes; conductor observed the test command fail before implementation.
- range: base through d7c1948, which equals HEAD. Working tree remains clean; targeted tests cleaned their temporary files.
- acceptance failures: reported stale retransmission behavior already exists at the base; other inspected acceptance expectations use obsolete Setup/immediate-pick controls rather than this ticket’s five tabs and staged approval.
- disclosure: a filtering mistake exposed one author Answer bullet about trusted document metadata. No verdict had been formed before exposure.

REVIEW: PASS
