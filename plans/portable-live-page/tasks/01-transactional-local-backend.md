# Add transactional local storage and the loopback backend

Type: task
Status: open
Blocked by: —
Test first: yes
Level: 3
Floor: allow flow-edit
Touches: packages/forkboard/forkboard/storage.py (new), packages/forkboard/forkboard/server.py (new), packages/forkboard/forkboard/live.py, packages/forkboard/forkboard/cli.py, packages/forkboard/tests/test_storage.py (new), packages/forkboard/tests/test_server.py (new), packages/forkboard/tests/test_live.py, packages/forkboard/tests/test_cli.py, tests/run.sh

Implement the persisted operation/queue and HTTP contracts in spec.md Interfaces. Add JSON atomic replacement and bounded cross-process locking in storage.py; route standalone live regeneration and answer/answer-graph writes through lock/reload/mutate/replace. Preserve additive old-state compatibility and ask ordinals while adding stable IDs and idempotent operations. Keep corrupted state intact and fail actionably. Graph proposals carry request source context, validate graph shape and limits, and never rewrite source or silently replace user versions.

Use a narrow custom handler in server.py, loopback-only serve DIR with port 0/default and explicit port, strict allowlisted resources, conditional operation writes and current state reads. Enforce exact Host and write Origin, reject cross-origin/null origins, unsupported methods, encoded traversal and symlink escape, unbounded lengths, non-JSON/malformed/unknown operations, unsafe graph/text sizes and browser-authored answer/source/round changes. No arbitrary filesystem mapping, subprocess, shell or approval route. Read-only state/page metadata cannot mutate approved plans. Provide a trusted Python callback seam for current page regeneration, used later by FeatureFlow; request data never names callback targets.

Add actual HTTP and subprocess concurrency tests: two stale browsers, answer racing a browser save, regeneration racing a save, interrupted replacement, duplicate request retry, lock contention and restart recovery. Update tests/run.sh's explicit standard-library import allowlist only for genuinely introduced standard-library modules; retain its rejection of third-party imports and every existing check. This is extending the tested stdlib membership list, not removing or suppressing the check.

## Not in this ticket

- FeatureFlow phase selection and browser adapter behavior are implemented in dependent tickets; this slice supplies their stable transport/storage contracts.

## Done when

- `python3 -m unittest discover -s packages/forkboard/tests -v` prints `OK`, including conditional-write, hostile-input, legacy-state, queue and cross-process transaction tests.
- Loopback serve prints its actual URL and state location, preserves committed state across restart, and never exposes source files outside its narrow resources.
- Stale requests return 412 without mutation; successful operations preserve concurrent agent answers and regenerated source context.

```check
$ python3 -m unittest discover -s packages/forkboard/tests -v
exit 0
prints OK
```

## Reference

- spec.md (read-only)
- packages/forkboard/forkboard/live.py (read-only)
- packages/forkboard/forkboard/cli.py (read-only)
- tests/run.sh (read-only)

## Answer


**Built**

- Added `storage.py`: shared lock/reload/mutate/atomic-replace transactions, strict bounded state loading, persistent local identity, strong revisions, validated version/ask/pick operations, persistent operation IDs and request snapshots. Corrupt state is kept intact; ambiguous locks fail closed with recovery guidance.
- Added `server.py`: loopback-only `serve DIR [--port N]`, narrow page/state/metadata resources, exact Host and write Origin, bounded JSON requests, conditional writes and a trusted no-argument refresh callback.
- Updated standalone live regeneration and answers to use transactions; added `answer-graph`. State regeneration preserves additive metadata and request context; graph replies remain proposals. Saved versions retain their original source fingerprint.
- Added storage, real HTTP, subprocess race/restart/interruption and CLI regression coverage. Extended only the explicit stdlib membership list in `tests/run.sh` for `math` and `http`.

**Proof**

- Start: `4359c43e2b693589d3da5e1c7e5f939c2ee93055`. Test-only commit: `4380788`. Before implementation, `python3 -m unittest discover -s packages/forkboard/tests -v` failed because the new storage/server modules did not exist (38 tests, two import errors). Repeated against an isolated `git archive 4380788` snapshot: exit 1, the same missing-module failures. The early full Test run crossed working-tree changes and was stopped as inconclusive; it is not test-first evidence.
- Done when 1/check: fresh `python3 -m unittest discover -s packages/forkboard/tests -v` completed with 50 tests, `OK`, exit 0 (final full Test: 3.983s). Includes legacy metadata preservation, queue deduplication, corrupted-state preservation, bounded lock contention, interrupted replacement and actual process death before replacement.
- Done when 2: `test_cli_server_prints_url_restarts_and_rejects_busy_port` starts the actual command twice with port 0, asserts the actual loopback URL and state path, verifies retained committed state after both restarts, and verifies a busy explicit port fails actionably. Real HTTP tests prove the page works and secret files, traversal/encoded paths and symlinks are rejected. These tests all passed in the fresh 50-test check.
- Done when 3: `test_two_browsers_stale_answer_and_retry` proves 412 leaves bytes unchanged and retries preserve an agent answer; `test_http_save_waits_for_agent_then_rejects_stale_context` races HTTP saves against separate-process answer and regeneration transactions, proving both stale revisions and changed source fingerprints are rejected. Subprocess writer coverage also retains answers, picks and regenerated round/context. All passed.
- Frozen Test `bash tests/run.sh && python3 -m unittest discover -s packages/forkboard/tests -v && npm --prefix packages/forkboard/tests/browser test`: exit 0; 466 shell checks passed, zero failed; 50 Python tests `OK`; six Chromium tests passed, zero failed/cancelled/skipped/todo.
- Build `python3 -m build --outdir dist`: exit 0; wheel and sdist built successfully. The frozen Lint command parsed the listed files as Python 3.9 with exit 0. `git diff --check` passed.

**Decisions**

- `storage.transaction(path, mutate, create=False, timeout=2, page=None)` is the shared writer seam. The callback sees the freshly loaded state under a cross-process directory lock; `page=` atomically replaces sibling index.html under that same lock after the state commit. State replacement uses a flushed/fsynced same-directory temporary file and `os.replace`.
- `storage.change(path, {id, change}, expected_revision)` accepts exactly one existing UI-shaped version/ask/pick operation. Reusing an ID for identical work returns current state, including later agent replies; reusing it for different work fails. New stale operations raise `storage.Conflict`; HTTP maps this to 412. State/body/text limits are 8 MiB/1 MiB/20,000 characters; graphs allow 500 nodes and 1,000 edges with bounded labels and finite layout positions.
- State `identity` is `{id, label}`; local operations use that reviewer. `_operations` stores ID-to-operation hashes across regeneration/restart. New asks get stable IDs, kind and immutable graph/source/title snapshots without changing their existing ordinal positions. Graph answers use `ask.result` and preserve reviewer versions; `live.version` returns a saved version's source when present, retaining the legacy fallback.
- `server.create(folder, port=0, refresh=None)` supports embedded/testing callers; `server.serve` announces the actual URL and state path. The refresh callback receives no request arguments and runs only for the exact `/api/page` resource. Metadata revision hashes rendered HTML; metadata also includes round and phase (default `review`, overridable through trusted state).

**Shortcuts taken**: none.

**For later tickets**

- Local browser adapters should obtain `identity.id` from state, persist an envelope ID through retries, send the strong ETag verbatim as If-Match, and carry the figure `source` in version/request context to prevent replay onto changed source. The operation payload keeps existing `{version: {figure, by?, entry}}`, `{ask: {...}}`, and `{pick: {key, entry}}` shapes; backend timestamps and identity are authoritative.
- The dependent FeatureFlow integration must replace its own direct regeneration/answer writers with `storage.transaction`, set trusted phase metadata as needed, and supply the no-argument refresh callback. This ticket changes standalone writers only, inside its footprint. `live.load` retains its legacy convenience behavior; managed writes must use strict `storage.read`/transactions.
- After confirming a crashed writer is dead, an operator may remove the named `state.json.lock` directory to recover. No live/ambiguous lock is removed automatically. Process death before replacement can leave an unreferenced temporary file, while the previous committed state remains readable.


### Repair verification (2026-11-08)

**Built**: This continuation starts at `2a05b74b3509b6e84add5cf10f2e8510a10f5670`, which already commits the two restored fingerprint fixes and includes their regression tests. No production or test changes were necessary in this continuation; only this ticket and the appended map decision change. The earlier test-only fingerprint commit `df22edfe01f943547ca76a60b6cd678d561be80b` is an ancestor of this start (`git merge-base --is-ancestor` exit 0); no new failing-test claim is made.

**Proof**:

- Fresh ticket check `python3 -m unittest discover -s packages/forkboard/tests -v`: 55 tests, `OK`, exit 0, 4.070s. The actual HTTP startup/restart, hostile-resource and symlink tests prove the second Done when; stale-browser and subprocess answer/regeneration races prove the third Done when with 412 and unchanged bytes, preserved answers and source context.
- Fresh frozen Test `bash tests/run.sh && python3 -m unittest discover -s packages/forkboard/tests -v && npm --prefix packages/forkboard/tests/browser test`: exit 0; 466 offline checks passed, zero failed; 55 Forkboard tests `OK` (4.117s); six browser tests passed, zero failed/cancelled/skipped/todo. The existing optional PyYAML check reported unavailable; no test/config changes were made.
- Fresh Build `python3 -m build --outdir dist`: wheel and sdist successfully built, exit 0. Fresh frozen Lint: Python 3.9 parsing passed, exit 0.

**Review fixes**:

1. Version operations require a nonempty string source in the payload or entry, and every supplied source must match the current figure. `test_version_requires_explicit_matching_source_even_with_fresh_revision` passed: omitted/null/empty/numeric/stale fingerprints fail without changing committed bytes; all three valid source locations work; conflicting payload/entry fingerprints fail.
2. Regeneration pins untagged legacy versions to the previous figure fingerprint before replacing figure metadata, preserving already tagged versions. `test_regeneration_pins_legacy_versions_to_the_previous_source` passed, including repeated regeneration and original-version provenance.

**Decisions**: Retain the restored implementation and regression coverage; request independent review of the fingerprint fixes using these fresh checks. Compound approval/reopen support remains ticket 02 as specified by the repair continuation.

**Shortcuts taken**: none.

**For later tickets**: The transactional backend remains unchanged from the starting commit. Continue with ticket 02 after independent review; preserve explicit version source fingerprints in every browser save.

## Review findings (round 1, pair review)

QUALITY
1. major packages/forkboard/forkboard/storage.py:239: Version operations can omit both source fields. Confirmed that replaying an old graph with a fresh ETag succeeds and stamps it with the regenerated source fingerprint, bypassing stale-source protection. Require and validate the graph’s source fingerprint before saving.
2. major packages/forkboard/forkboard/live.py:33: Regeneration preserves legacy versions without recording their original source. version() then returns the new figure fingerprint for those old graphs, allowing subsequent apply checks to treat stale edits as current. Confirmed with an in-memory legacy-state probe. Add the previous figure fingerprint to legacy versions before replacing figure metadata.

Probed: HTTP paths, methods, Host, Origin, Content-Type, If-Match, Content-Length, Transfer-Encoding and JSON; operation IDs/types; ask identity, timestamps, text, figure, version, step, kind, source and graph; version graph, positions, provenance and source; pick identity, timestamp, key and value; persisted legacy state, paths/symlinks, locking, replacement, CLI arguments and trusted refresh callback. No files changed.

REVIEW: FAIL

SPEC
- Forkboard unit suite: MET (conductor) - `python3 -m unittest discover -s packages/forkboard/tests -v` passed its check and printed OK.
- Loopback startup, restart persistence and narrow resources: MET - focused `python3 -m unittest test_server -v` printed `Ran 6 tests` and `OK`; startup/restart, hostile paths and symlink tests passed.
- Stale requests and concurrent answers/regeneration: MET - the same focused run passed stale-browser and subprocess race tests, asserting 412 without mutation, preserved answers and request source context.
- scope: OK - reviewed 4359c43..8173e24 (current HEAD); source, tests, allowlist and plan bookkeeping match this ticket. Acceptance failures require provider/browser/FeatureFlow work assigned to dependent tickets.
- test first: OK - new tests require the new storage/server modules and would fail without production changes; conductor observed the failing test commit before implementation.

REVIEW: PASS

## Repair continuation

Keep this ticket unresolved until the two round-1 source-fingerprint findings are verified and reviewed again: require current source for version operations, and preserve original source on legacy versions before regeneration. Existing restored fixes are uncommitted; earlier proof does not resolve this review failure. Approval/reopen operation support is assigned to 02.

## Review findings (round 1, test first)

no commit between base and HEAD changes only test files. Commit the failing test alone first, then the code. A test commit does not count when earlier commits already changed production files. If the test and the code are in one commit (or the test commit sits on top of code that is already there), recover: revert that commit, commit the test files alone, then restore the production files in a later commit (git checkout <the old commit> -- <paths>). Do not rewrite history.

## Attempt note (test-first send-back)

The specified base `2a05b74b3509b6e84add5cf10f2e8510a10f5670` already contains both fingerprint fixes, while their failing-test commit `df22edfe01f943547ca76a60b6cd678d561be80b` is an ancestor of that base. `feature_flow.proof._candidates(base, 'plans/portable-live-page')` returned `[]`. Its candidate rule requires the entire tree at a test-only commit to differ from the specified base only in test and plan files. Reverting the fixes after that base would leave production files different from the base at the test commit, so the recovery prescribed in the finding cannot produce a qualifying candidate. A test-only commit against the unchanged base would run against already-fixed production code, and fabricating a failing test would weaken the bar. No code or tests were changed. The conductor needs a base preceding the existing test-only commit, or a plan/conductor correction that recognizes the already-recorded test-first history; then rerun the checks and independent review. The ticket remains open.

## Attempt note (supplied base 7719153)

The supplied start `771915391496fb48e2c75dd73fc6e8ab5868c1a2` already includes the fingerprint fixes and their test-only commit `df22edfe01f943547ca76a60b6cd678d561be80b` (verified ancestor, exit 0). `feature_flow.proof._candidates` returns `[]` for the supplied base. A test-only commit on that base would run against the already-fixed production code; reverting the production fixes before such a commit would make that commit differ from the base in production files and fail the candidate rule. No code or tests were changed. A base before the existing test-only commit or a correction to the test-first gate is needed; the ticket remains open.

## Attempt note (supplied base e3cb173)

The supplied start `e3cb17340c691668273dc218b7d998e3adfc62fd` already contains the fingerprint fixes and their test-only commit `df22edfe01f943547ca76a60b6cd678d561be80b` (verified ancestor, exit 0). `feature_flow.proof._candidates` returned `[]` for this start. A test-only commit on this base would run against already-fixed production code; reverting the fixes first would make the candidate differ from the base in production files. No code or tests were changed. A base preceding the existing test-only commit or a correction to the test-first gate is needed. The ticket remains open.


### Current-base verification (2026-11-12)

**Built**: The clean checkout began this continuation at `709d962a56da3a2ea780ee087dae388756b4130c`, with implementation already committed after the prescribed base `65951d4cf7029240439aedd9342f8fb66daced6a`. Production changes are in `709d962`; the preceding `8aa2f9aeff97195435bce839f1a3eab70a0420cd` changes only Forkboard tests and the allowed stdlib test membership list. This continuation changes only this ticket's Status/Answer and an appended map decision; no production or test changes were needed.

**Proof**:

- Done when 1/check: fresh `python3 -m unittest discover -s packages/forkboard/tests -v` printed `Ran 55 tests in 4.054s` and `OK`, exit 0. Includes legacy state, queue deduplication, bounded lock contention, interrupted replacement, process death, cross-process answer/regeneration transactions and source-fingerprint regressions.
- Done when 2: the same fresh command passed `test_cli_server_prints_url_restarts_and_rejects_busy_port`, which launches the real CLI twice on port 0, checks its actual loopback URL and state path, retains committed state through both restarts and rejects a busy explicit port. `test_host_origin_routes_methods_and_hostile_operations_do_not_mutate` and `test_symlink_and_corrupt_state_fail_closed` passed, proving narrow resources and unchanged state for rejected operations.
- Done when 3: the same fresh command passed `test_two_browsers_stale_answer_and_retry`, asserting 412 with unchanged bytes and preserved concurrent answers, and `test_http_save_waits_for_agent_then_rejects_stale_context`, racing actual HTTP saves with separate-process answer/regeneration writers and rejecting an old source even after fetching a fresh revision. Request snapshots retain their original source context.
- Re-ran the ticket test command against an isolated `git archive 8aa2f9a` inside the checkout: exit 1, `Ran 38 tests`, `FAILED (failures=1, errors=3)`. The legacy-source regression fails on the old fingerprint; imports fail because the storage/server modules do not yet exist. The archive was removed after the check. This verifies the existing failing-test history; no new test-first claim or fabricated failure is needed.
- Build `python3 -m build --outdir dist`: exit 0, successfully built the wheel and sdist. Frozen Lint (Python 3.9 syntax parsing): exit 0. `git diff --check`: exit 0. Full frozen Test: left to the conductor's gate.

**Decisions**: Retain the existing transaction and narrow HTTP implementation, including both restored source-fingerprint fixes. The fresh evidence above supersedes historical proof for this continuation. Compound approval/reopen and FeatureFlow integration remain with dependent tickets.

**Shortcuts taken**: none.

**Review fixes**:

- Round-1 quality finding 1: retained the explicit matching-source validation in `storage.change`; fresh `test_version_requires_explicit_matching_source_even_with_fresh_revision` passed for missing/null/empty/numeric/stale sources, valid source locations and mismatched dual sources.
- Round-1 quality finding 2: retained legacy version pinning before regeneration; fresh `test_regeneration_pins_legacy_versions_to_the_previous_source` passed, preserving both untagged and already tagged version provenance across repeated regeneration.
- Test-first finding: the prescribed base now precedes `8aa2f9a`, whose entire diff from that base is the test paths listed above; production follows in `709d962`. The isolated failing-test run proves that the test commit precedes working implementation. Independent review remains the conductor's responsibility.

**For later tickets**: Use `storage.transaction` for FeatureFlow-managed writers, and preserve explicit source fingerprints in browser version operations. This continuation introduces no new backend contract changes.

## Review findings (round 1, pair review)

QUALITY
1. major packages/forkboard/forkboard/storage.py:233-234: Diagram asks can relabel stale graphs with the current source. In-memory probes confirmed both a graph submitted without source and a saved version carrying an older source receive the regenerated figure’s fingerprint. Require matching source for submitted graph snapshots and preserve or reject stale saved-version context; add regression tests.

Probed HTTP paths/methods, Host/Origin, content headers, JSON, revision preconditions, operation IDs/types, identity/time, ask fields/context, version graph/source/provenance/positions, pick fields, persisted state, locking, replacement, CLI and refresh callback through the 55-test suite and focused in-memory probes. Suite passed. Tests may leave Python bytecode caches; no files were manually changed.

The required base ticket already contained Answer text, exposing it before any verdict was formed. Reviewed 65951d4..e0750e5, current HEAD.

REVIEW: FAIL

SPEC
- Forkboard unit suite: MET (conductor) - required unittest check passed and printed OK; not rerun.
- Loopback startup, restart persistence and narrow resources: MET - focused python3 -m unittest test_server -v ran six tests and printed OK, including actual CLI startup/restart, hostile paths and symlinks.
- Stale requests and concurrent answers/regeneration: MET - same focused run verified 412 without mutation, preserved agent answers and retained request source context.
- scope: OK - reviewed 65951d4..e0750e5 (HEAD); implementation, tests, stdlib allowlist and plan bookkeeping match the ticket. Acceptance failures stop at provider functionality assigned to dependent tickets.
- test first: OK - 8aa2f9a changes only tests/checks; new tests import production modules absent at that commit. Conductor observed failure before implementation.

The mandated base ticket unexpectedly contained an existing Answer, which reached me before any verdict. This verdict uses the diff, conductor check and independently run HTTP checks. Working tree remains clean; no files left behind.

REVIEW: PASS
