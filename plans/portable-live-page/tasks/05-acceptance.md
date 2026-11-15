# Verify the portable live page end to end

Type: task
Status: open
Blocked by: 01, 02, 03, 04
Test first: no
Level: 1

Perform the map's complete bar after all implementation slices. Re-run the frozen gate and examine the independently written acceptance results supplied by the conductor. Review the documented manual Codex smoke steps against actual CLI help; no model account is required for automated proof. Record exact proof and any environment limitation in this ticket's Answer and append learnings. This ticket changes no product or test code. If proof reveals a defect, return it to the owning implementation ticket rather than widening this footprint.

Exercise the existing suites against both transports and all phases; ensure acceptance covers no-brainstorm plans, concurrent answer/regeneration versus browser writes, restart persistence, hostile localhost requests, reply proposals and dirty-edit-safe refresh. Build package artifacts with the frozen Build command and use the existing smoke scripts for both distributions; package smoke may require build dependencies/network and is declared accordingly below.

## Not in this ticket

- The conductor runs Acceptance only after every ticket resolves; do not run or depend on that command as a ticket check. Product fixes belong to their implementation tickets.

## Done when

- `bash tests/run.sh` prints `0 failed`; existing offline behavior remains green.
- `python3 -m unittest discover -s packages/forkboard/tests -v` prints `OK`; backend and legacy state suites pass.
- `npm --prefix packages/forkboard/tests/browser test` prints `# fail 0`; native and local browser suites pass.
- `python3 packages/forkboard/tests/package_smoke.py` prints `all passed`, proving standalone distribution assets and local commands.
- `python3 tests/package_smoke.py dist` prints `all passed`, proving the bundled distribution after the frozen Build command.

```check
$ bash tests/run.sh
exit 0
prints 0 failed
$ python3 -m unittest discover -s packages/forkboard/tests -v
exit 0
prints OK
$ npm --prefix packages/forkboard/tests/browser test
exit 0
prints # fail 0
$ python3 packages/forkboard/tests/package_smoke.py
exit 0
prints all passed
needs installed build dependencies or network for isolated build environments
$ python3 tests/package_smoke.py dist
exit 0
prints all passed
```

## Reference

- spec.md (read-only)
- commands.md (read-only)
- map.md (read-only)

## Answer
