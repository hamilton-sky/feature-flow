# Map: portable-live-page

## Destination

One Forkboard live UI works with native Claude artifacts and a local Codex backend. Persistent diagram versions, revision conflicts, queued requests and replies, validated proposal picks and refresh cover brainstorm, draft Plan, active Build and completed Build, including features that skipped brainstorming.

**The bar.** `python3 -m unittest discover -s plans/portable-live-page/acceptance -v` prints `OK`; the frozen Test command passes existing offline, Python and Chromium suites. The final ticket repeats the offline/adapter/phase bar and records the manual Codex smoke instructions.

## How to work this

- See ready work: `python3 scripts/flow-status.py portable-live-page`; claim the lowest ready ticket by setting its Status.
- Resolve with an Answer and append one decision here. Status lives only in task files.
- Commands are frozen in commands.md; append discoveries to learnings.md.
- Plans live in plans/<feature>/; this unapproved v0.37 repair draft lives under .feature-flow/state/draft-v037/. Tool overrides are FLOW_DIR and FLOW_TICKETS.

## Decisions so far

- Repository discovery: graph search returned no flow_page nodes; read the source directly. Existing live.state, asks/answer/version/picks, flow_page.document and flow_plan sections/apply_picks are the compatibility baseline.
- Both CLI live renderers and answer writers currently directly overwrite state.json; all must share transactions, not just HTTP writes.
- Existing assets/* package data already includes new adapter assets in both distributions; no packaging configuration change is planned.
- Choose narrow conditional operation writes. Strong If-Match preconditions prevent lost updates and use 412 for false preconditions (docs: https://www.rfc-editor.org/rfc/rfc9110.html#section-13.1.1).
- Choose a custom standard-library HTTP handler rather than an unrestricted static file server. Python 3.9 provides ThreadingHTTPServer, but http.server offers only basic checks; explicitly implement the loopback origin, resource and body boundaries in spec.md (docs: https://docs.python.org/3.9/library/http.server.html).
- No external Claude API assumptions: preserve the repository's actual capability signatures and browser test contract. Playwright is pinned at 1.63.0; use existing tests and APIs, introducing no new library dependency.
- Lazy pass: drop SQLite/migrations, SSE/WebSockets, new model SDK, browser model keys, automatic agent wakeups, separate redesign, synthetic brainstorm files and a package-config ticket. Existing JSON, editor, state model, validation and asset globs cover them.

## Open questions

None. All three Unsure assumptions are kept: loopback first, explicit request processing, and page choices remain proposals under existing approvals. Tickets 01–04 authorize flow-edit because they change FeatureFlow/Forkboard files covered by integrity snapshots. Only 02 adds storage/live implementation and unit-test paths for upstream approval/reopen support; 04 adds docs/source-of-truth.md. All checks, levels and gates remain unchanged; ticket 05 needs no exception.

## Decisions so far (continued)

01 — Share bounded JSON transactions and persistent operation IDs across standalone agent writes and the narrow loopback API; keep diagram replies as request-context proposals.

## v0.37 repair review

Five tickets remain; no folds. 01 stays open pending fingerprint-fix review. 02 preserves five tabs and atomic approval/reopen; 03 preserves latest-document/approved/list-pick semantics, plan-only entry and read-only reality; 04 documents files as truth and intent versus execution; 05 retains the entire bar. commands.md is byte-for-byte unchanged. This draft excludes acceptance/eval artifacts and does not replace the approved plan.

Before restart, the independent tester must update acceptance against the newly approved spec: browser.cjs Setup selectors and immediate pick persistence become Style/Team tabs plus staged picks/Approve; Change targets the actual tab; test_portable.py proposal-only wording must distinguish valid compound Plan approval intent from forbidden executable/forged writes. Add atomic approve/reopen, about context, accepted freeze and read-only reality coverage. Preserve hostile-input, stale-source and concurrency checks. Do not have builders edit acceptance. Existing acceptance remains untouched until that tester handoff.

01 — Reverified the restored source-fingerprint fixes with 55 Forkboard regressions and the full frozen gate; versions require matching source and legacy versions retain their previous source through regeneration.

01 — Verified the restored backend against the corrected preimplementation base: 55 Forkboard tests pass and the isolated test-only commit fails before production; preserve explicit source fingerprints and the shared transaction seam.

01 — Diagram request graphs require matching source context; selecting a stale saved version fails without mutation instead of receiving the current source.

02 — Share Claude/local capability adapters and a persistent conditional save queue; validate compound approvals/reopen against trusted document controls and freeze accepted settings, preserving dirty edits through polling and explicit update previews.

02 — Standard single-ticket verification accepts the declared concurrency-fixture exception; 62 Python and 12 Chromium tests pass with provider, dirty-edit, queue, conflict and approval behavior retained.

02 — Reverified 62 Python and 12 Chromium tests; the frozen literal browser-output check requires the conductor to inherit NODE_OPTIONS=--test-reporter=tap on this Node installation.

02 — Successful request acknowledgements clear only the exact submitted draft; eight delayed-response browser regressions preserve newer Talk, diagram, option and ticket drafts on local/native hosts.

02 — Preserve stale-source edits separately on explicit recovery, then resume queued saves without rebasing the old graph.
