# Learnings: portable-live-page


- (01) The installed codeintel doctor is probed by existing prompt fixtures in tests/py; on this machine the full shell suite took roughly 42 minutes while focused Forkboard tests took four seconds. Do not mistake its quiet captured output for a hung suite.
- (01) New backend APIs: storage.transaction(path, mutate, create=False, timeout=2, page=None), storage.change(path, envelope, revision), and server.create/serve(folder, port=0, refresh=None). The page argument keeps regeneration HTML within the state writer lock; refresh is a trusted no-argument callback.

- (02) Regeneration must provide trusted steps/choices via live.state; accepted documents should set doc.frozen (or phase accepted/build/complete/completed). Unknown choice keys are rejected when trusted document metadata exists.
- (02) NODE_OPTIONS=--test-reporter=tap makes the existing browser command print the literal # fail 0 on this Node version; it changes output formatting only. Regenerating identical HTML does not change /api/page revision, even when the state round increments.
