# Commands and settings

[← README](../README.md) · [Docs index](README.md)

Every script command and every `FLOW_` setting. The skill runs these for you; you need them only to run a step by hand or change a default.

## Commands

```bash
python3 scripts/flow.py <feature> start|reset [NN]          the conductor (the skill runs it; also plan-prompt, plan-review-prompt, plan-accept)
FLOW_TRUST=<digest|new> FLOW_SESSION=<token> python3 -I scripts/flow-trust.py <feature> next|prompt|verdict <file>|fast on|off   loop commands by hand, through the runner: prints TRUST <digest> first (no hash check, see below)
python3 scripts/flow-status.py <feature>                  table of tickets and which are READY
python3 scripts/flow-status.py <feature> --next           path of the next ready ticket (exit 10 = done, 11 = stuck)
python3 scripts/flow-status.py <feature> --ready          every ready ticket, one per line (the same exit codes)
python3 scripts/flow-status.py <feature> --counts         one line of counts
python3 scripts/flow-status.py <feature> --check          cycles, missing blockers, missing Done when, unordered mentions
python3 scripts/flow-status.py <feature> --lint           --check plus: a check block (or `Check: none <why>`) on every ticket, a Test command
feature-flow report <feature>                             what a run did, from its log: builds, reviews, failed checks, stops
feature-flow import <spec-kit or openspec folder> <feature>   start plans/<feature>/ from their task list
feature-flow eval <feature> [--later]                     record the run in plans/<feature>/eval.json, with your verdict (also: flow-status.py <feature> --eval)
python3 scripts/flow-status.py <feature> --width          how many tickets can build at once, and why each waiting ticket waits
python3 scripts/flow-status.py <feature> --page           the flow's one page (Setup, Options, Plan, Build); --picks DIR writes the live page's picks
python3 scripts/flow-status.py <feature> --clean [--yes]  list (or delete) the brainstorm's spent files once the plan is accepted
python3 scripts/flow-status.py <feature> --mermaid        the ticket graph, coloured by status (add "plain" for none)
python3 scripts/flow-status.py <feature> --json           every ticket with status, blockers and readiness
python3 scripts/flow-view.py <feature> [--watch]          the animated graph page, opened in your browser
feature-flow brainstorm-page <feature> [--style NAME] [--fragment]   the brainstorm as the flow's one page (Forkboard); --live DIR, --asks, --answer, --apply, --picks for the live page
python3 scripts/gate.py <feature>                         run Build, Test and Lint from commands.md
python3 scripts/floor-guard.py <feature> <NN> [base]      check a ticket's diff, run from the repo root
```

`next`, `prompt` and `verdict` run directly stop with `STOP run the conductor through scripts/flow-trust.py, as the skill says`. Pass `FLOW_TRUST=new` on a first call, then the digest from the last `TRUST` line. Run by hand like this, nothing checks `flow-trust.py` itself, so it is for trying things out, not a protected run. The skills never run it this way: they start it through a loader line that first checks the file against the sha256 the skill pins, and stops with `flow-trust.py does not match this skill` if it differs (see `## Calling the conductor` in the skill). For a `--user` install the scripts are in `~/.feature-flow/scripts/` (or `$FEATURE_FLOW_HOME/scripts/`).

The commands in `commands.md` run through `bash -c` on Linux and macOS and through the system shell (`cmd.exe`) on Windows, so write them for the platform your team uses, or call `python` as in the examples.

`flow-status.py` also understands the `.scratch/<feature>/issues/` layout and the statuses `done`, `ready-for-agent`, `ready-for-human` and `closed`: `FLOW_DIR=.scratch FLOW_TICKETS=issues`.

| Variable | Default | Meaning |
|---|---|---|
| `FLOW_PROFILE` | unset | `careful`, `standard`, `normal` or `fast`: fills the settings in this table that are not set; a `Profile:` line in `commands.md` does the same |
| `FLOW_TICKETS_PER_SESSION` | `4` | tickets per session before `HANDOFF`; `0` never hands off |
| `FLOW_RELAY` | `0` | `1` hands off after every build and every review |
| `FLOW_DRIVER` | `person` | read by `start`: `agent` when another agent drives the run: no handoffs (unless `FLOW_TICKETS_PER_SESSION` is set), and the eval says so |
| `FLOW_LANES` | the plan's `Lanes:` line, else `1` | read by `start`: `2` to `4` builds tickets with disjoint `Touches:` side by side in worktrees (not with `FLOW_RELAY`); overrides `Lanes:` |
| `FLOW_FAST` | unset | read by `start`: `1` defers the reviews of tickets below level 3 to one feature review at the end, `0` turns it off; unset keeps the run's setting |
| `FLOW_BUDGET` | unset | read by `start`: minutes of active work before fast mode turns on, then a re-plan offer; `off` drops it |
| `FLOW_BATCH` | `5` | fast mode: most small tickets one builder takes at once; `1` turns batches off |
| `FLOW_SCOUTS` | `on` | `off` lists no scouts before any phase, whatever the brainstorm's `Scouts:` line says |
| `FLOW_CODEINTEL` | `auto` | `off` keeps codeintel out of the scout's and reviewer's prompts; `auto` adds it when `codeintel doctor` reports an engine ready |
| `FLOW_TAKEOVER` | unset | `1` lets `start` take a feature over from a session that is gone |
| `FLOW_MAX_RETRIES` | `2` | builds or reviews per step before the run stops |
| `FLOW_MAX_REVIEW_ROUNDS` | `3` | times a ticket may be sent back before the run stops (a level 1 ticket: once) |
| `FLOW_GATE` | `on` | `off` skips Build, Test and Lint after each ticket, and also the Done when and test-first checks; from the plan, only `Gate: off unsafe` in `commands.md` does the same |
| `FLOW_REVIEWERS` | `1` | `2` runs a quality and a ticket reviewer side by side where one review would run (not in lanes) |
| `FLOW_ROUND_REVIEW` | `off` | `on` reviews the whole round once at the end, after every ticket's own review |
| `FLOW_BASE_GATE` | `off` | `on` runs the whole gate once at the base, before the first ticket, and stops if it is red (`<feature>.base-gate.log`) |
| `FLOW_GATE_FULL` | unset | `1` runs the full Build, Test and Lint after every ticket, even when `commands.md` has a `Quick:` line |
| `FLOW_SMALL_FILES` | `3` | most files a ticket may change and still get the single review (no level), or stay level 1 |
| `FLOW_SMALL_LINES` | `60` | most changed lines for the single review; `0` turns the single review off |
| `FLOW_GATE_TIMEOUT` | `30` | minutes each gate command and the smoke test may run; `0` means no limit. A failed smoke test writes `.feature-flow/state/<feature>.smoke.log` |
| `FLOW_SMOKE` | the `Smoke:` line of `commands.md` | command run before every ticket; the run stops if it fails |
| `FLOW_DIR`, `FLOW_TICKETS` | `plans`, `tasks` | where the plans and the ticket folder live |
| `FLOW_NO_OPEN` | unset | `1` makes `flow-view.py` never open a browser |
| `FLOW_WATCH_SECONDS` | `3` | how often `flow-view.py --watch` rewrites the page |
| `FLOW_STYLE` | `route` | the brainstorm page's look when the brainstorm has no `Style:` line: `route`, `blueprint`, `sketch`, `paper`, `terminal` or `bright` (Forkboard's themes) |

The run also stops on its own after a number of phases (`BUILD` and `REVIEW` hand-outs, the spec review and the quality review each counting as one, a single review counting as one) that grows with the ticket count, recomputed at every pick, so a loop of failures cannot go on forever.
