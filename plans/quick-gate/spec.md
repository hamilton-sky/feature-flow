# Quick gate — Spec

## Problem

After every ticket the conductor's gate runs the plan's whole `Build`, `Test` and `Lint` (`gate.run` in `feature_flow/gate.py`, called from `Conductor.judge_build`). In this repo that is about 4 minutes of unit tests plus the `tests/run.sh` harness, per ticket, and a 7-ticket plan spends most of its wall clock on it. The suite is the safety net, so it must still run, but it does not have to run in full after every ticket: a ticket in the middle of a plan can be checked by the fast part of the suite, and the whole suite run at the points that matter.

## Goal and the bar

A plan's `commands.md` may carry an optional `Quick:` line, the fast subset of `Test`. The gate runs Build, Quick (in place of Test) and Lint after a ticket, and the full Build, Test and Lint when the ticket is the last unfinished one, when the run is about to hand off to a new session, or when `FLOW_GATE_FULL=1`. Without a `Quick:` line nothing changes. The planner picks `Quick:` and the plan reviewer checks it. Every other conductor check is untouched.

**The bar.** `python3 -m unittest discover -s tests/py -p "test_quick_gate.py"` prints `OK`: in a fixture repo driven through the conductor, with `Quick` and `Test` commands that log which one ran, the first ticket of three runs only Quick, the last ticket runs Test, the ticket before a handoff runs Test, `FLOW_GATE_FULL=1` runs Test every time, a plan without `Quick:` runs Test every time, and the log has `GATE-QUICK` and `GATE-FULL` events to match. And `python3 -m unittest discover -s tests/py` and `bash tests/run.sh` pass. Ticket 05 runs it.

## Scope

In: `Quick` in `gate.py` (a quick mode); the conductor choosing quick or full per ticket; `FLOW_GATE_FULL`; the `commands.md` template, the planner guide and the plan-review guide; README; version 0.7.0.
Not in scope: the test-first proof (it keeps running the full `Test` command, see Decisions); choosing tests from the diff; skipping the gate for any ticket; Smoke (still runs before every ticket); the reviewers' own runs.

## Happy path

1. `commands.md` has `Test: <full suite>` and `Quick: <fast subset>`.
2. A builder resolves ticket 01 of 03 → the conductor runs the gate in quick mode: Build, Quick, Lint → log `GATE-QUICK`, then the floor guard, Done when, review.
3. Ticket 03, the last unfinished one, → the gate runs in full mode: Build, Test, Lint → log `GATE-FULL`.
4. A ticket that is the last one before the run hands off (`session_done + 1` reaches `FLOW_TICKETS_PER_SESSION`) also gets the full gate.
5. A failing quick or full gate sends the ticket back as today (`send_back("gate", ...)`).

## Edge cases

| Trigger | Expected behaviour | Handled in ticket |
|---|---|---|
| No `Quick:` line, or a placeholder in angle brackets | full gate every ticket, exactly as today | 01, 02 |
| `FLOW_GATE_FULL=1` | full gate every ticket | 02 |
| `FLOW_GATE=off` | no gate at all, as today | 02 |
| Only one ticket in the plan | it is the last: full gate | 02 |
| The last ticket is sent back and rebuilt | its gate is full again (it is still the last unfinished ticket) | 02 |
| A ticket is rebuilt after an earlier ticket's full gate failed | decided per ticket at its own build | 02 |
| `gate.py <feature>` run by hand | always the full gate, as today (quick mode is for the conductor only) | 01 |
| Quick command exits non zero or times out | the gate fails like any gate command | 01 |

## Design

    judge_build ─► gate_mode()
                      │ full if: no Quick | FLOW_GATE_FULL=1 | last unfinished ticket
                      │          | this ticket fills the session (handoff next)
                      │ else quick
                      ▼
              gate.run(feature, ..., quick=True|False)
                 quick: Build, Quick, Lint     full: Build, Test, Lint
                      │ fail ─► send_back("gate", output)
                      ▼ pass ─► floor guard, Done when, test first, review (unchanged)

### Decisions

- **Last ticket and handoff run the full suite** — options: full only on the last ticket; or also before a handoff; or on every Nth ticket. Chosen: last and before a handoff. Why: a handoff is where one session stops vouching for the work, so the whole suite should have passed on the commit it leaves; the last ticket closes the plan. The cost: a full-suite failure at those points is charged to that ticket's builder even if an earlier ticket broke it. CI on the PR is the same net.
- **Test first keeps the full Test command** — options: use Quick at the red commit too; keep Test. Chosen: keep Test. Why: Quick may not include the new test, and then the red run would pass for the wrong reason and send a correct ticket back. Open question for the user: whether to let a plan opt in.
- **Who writes `Quick:`** — the planner, checked by the plan reviewer, never the builder (the floor guard already fails any change to `commands.md`).
- **Switch** — `FLOW_GATE_FULL=1` forces the full gate; `FLOW_GATE=off` still turns the gate off.
- **No size rule** — "per ticket size" was considered; a small diff can still break a distant test, so the choice follows position in the plan, not diff size.

## Interfaces

- `feature_flow/gate.py`: `KEYS` stays `Build, Test, Lint`; `run(feature, out, err, timeout=None, quick=False)`; with `quick` and a usable `Quick:` value, Quick runs in the place of Test and the output says `gate: Quick: <cmd>`. The command line `gate.py <feature>` is unchanged and always full.
- `feature_flow/checks.py` `gate(scripts, feature, timeout=None, quick=False)`.
- `feature_flow/conductor.py`: `gate_quick()` decides; log events `GATE-QUICK` and `GATE-FULL` next to `GATE-PASS` and `GATE-FAIL`.
- Env: `FLOW_GATE_FULL` (default off).
- `commands.md`: optional `Quick:` line.

## Migration and compatibility

Plans without `Quick:` behave exactly as before. Run state needs no new keys.

## Risks

- A bad `Quick:` (too narrow) lets a break through until the last ticket — the plan reviewer must run it and check it covers the areas the tickets touch; the full gate and CI stay.
- A full-suite failure at the end is charged to the last builder — noted above; a send-back message names that the full gate ran.

## How this plan is built (read before running it)

Tickets 01 and 02 edit the conductor's own code, so each carries `Floor: allow flow-edit`; build with a conductor from a pinned checkout of the 0.6.0 release, as small-tickets was built on 0.5.0.
