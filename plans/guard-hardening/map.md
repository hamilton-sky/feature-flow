# Map: guard-hardening

## Destination

The conductor notices when a build changes the code it runs; the floor guard covers the listed gaps with a caught and a look-alike test each; `floorguard.py` and `gate.py` are plain Python; the gate and the smoke test time out; this repo's committed copies of the tool match the source. Version 0.2.0.

**The bar.** `python3 -m unittest discover -s tests/py && bash tests/run.sh` passes, the two tamper tests fail on 0.1.6 and pass now, and CI is green on every job. Ticket 10 runs it.

## How to work this

- See what is ready: `python3 scripts/flow-status.py guard-hardening`. Take the lowest numbered READY ticket.
- Claim: set `Status: claimed` in the ticket and save before starting.
- Resolve: write the result under `## Answer`, set `Status: resolved`, then add one line to
  Decisions so far below.
- See the graph: `python3 scripts/flow-status.py guard-hardening --mermaid` (coloured by status, drawn on demand).
- Commands live in `commands.md` (frozen). Lessons live in `learnings.md` (append only).
- Status lives only in the ticket files. This map never repeats it.
- Run it from a pinned 0.1.6 conductor, see `spec.md` § How this plan is built.
- Order that must hold: 01 first; 05 only after 02, 03 and 04 are resolved (reviewed); 08 to 10 only after PR #34 is merged.

## Decisions so far

01 — the conductor hashes its own package, scripts and build/review prompt files at pick time and stops on any change (`Floor: allow flow-edit` in the ticket at base allows it); see `feature_flow/codehash.py`.

## Open questions

- Version (decided 2026-10-07, user): release as 0.2.0. The old bash-era `v0.2.0` tag on origin is deleted by the user before they push the new one.
- Whether `FLOW_GATE_TIMEOUT` should also bound the planner's `Smoke` run in `commands.md`: assumed yes, it is the same smoke call.
02 — skip category gained skipTest, importorskip, expectedFailure, t.Skipf/SkipNow, #[ignore = ; focused .only( / fit( / fdescribe( are skips only on test-looking paths (DELETED_TEST) and not after a word char, '.' or 'def '.
03 — config guard: nine whole-file names added; pyproject.toml/setup.cfg judged by section of each changed line, package.json by key values, conftest.py by added words, Makefile only if commands.md uses make; all reported as 'config: <path>', allowed by Floor: allow config.
04 — a passing floor guard's assertion warning (test paths only) is saved as guard_warning and added to the reviewer's task as 'The floor guard warns: ...'; cleared on the next pick; never a finding.
