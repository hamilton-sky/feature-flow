# Map: quick-gate

## Destination

A plan can set `Quick:` in `commands.md`. After a ticket the gate runs Build, Quick and Lint; it runs the full Build, Test and Lint on the last unfinished ticket, before a handoff, and when `FLOW_GATE_FULL=1`. No `Quick:` line, no change. The planner chooses `Quick:`, the plan reviewer checks it. Version 0.7.0.

**The bar.** `python3 -m unittest discover -s tests/py -p "test_quick_gate.py"` prints `OK` (quick on a middle ticket; full on the last, before a handoff, under `FLOW_GATE_FULL=1`, and without `Quick:`), and `python3 -m unittest discover -s tests/py` and `bash tests/run.sh` pass. Ticket 05 runs it.

## How to work this

- See what is ready: `python3 scripts/flow-status.py quick-gate`. Take the lowest numbered READY ticket.
- Claim: set `Status: claimed` in the ticket and save before starting.
- Resolve: write the result under `## Answer`, set `Status: resolved`, then add one line to
  Decisions so far below.
- See the graph: `python3 scripts/flow-status.py quick-gate --mermaid` (coloured by status, drawn on demand).
- Commands live in `commands.md` (frozen). Lessons live in `learnings.md` (append only).
- Status lives only in the ticket files. This map never repeats it.
- The gate runs the whole suite after each ticket: run only your ticket's own test file yourself.

## Decisions so far

- (plan) Position in the plan, not diff size, decides quick or full; the last ticket and a handoff run the full suite. Why and the rejected options: spec.md § Decisions.
01 — gate.run and checks.gate take quick=False; quick mode runs Quick in Test's slot when Quick: is usable, else Test.

## Open questions

- Should the test-first proof be allowed to use `Quick:` when a plan opts in? Left on `Test` for now.
01 — gate.run/checks.gate take quick=False; quick mode runs Quick in Test's slot when usable, else Test; tests are portable (python logger script, no skips).
02 — conductor.gate_quick picks quick unless FLOW_GATE_FULL=1, no Quick:, last unfinished ticket, or session fills; gate send-back says (quick) or (full).
03 — planner writes Quick: only from a clearly faster subset of Test (strict subset, never invented); plan reviewer runs it in check 4.
