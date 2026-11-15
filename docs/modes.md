# Modes

[← README](../README.md) · [Docs index](README.md)

A mode says what kind of work a run is, and sets the reviews, the gate, the lanes and the scouts for you. There are five. `feature` is the default.

| Mode | Pick it when | Before the build | Reviews | Gate | Lanes | Scouts | Tickets per session |
|---|---|---|---|---|---|---|---|
| `fix` | one bug with one cause ([how](fix.md)) | reproduce, diagnose, your yes, a plan of one ticket | one reviewer | each ticket | 1 | on | 4 |
| `small` | a clear change, a few tickets, nothing risky | brief and plan, no brainstorm | one review of the whole feature at the end; level 3 keeps its own | at the end | batches of up to 5 | off | 6 |
| `feature` | most work | brief and plan; a brainstorm when the idea is fuzzy | two reviewers side by side, and one review of the round | every 3 tickets | auto, up to 4 | on | 4 |
| `careful` | auth, tokens, money, data loss, shared core code | brief, a brainstorm offered, acceptance tests with an `Acceptance:` line | the full gate and two reviewers on every ticket | each ticket | auto, up to 2 | on | 3 |
| `explore` | you are not sure what to build yet | a brainstorm that ends in Go or No-go | then built as `feature`, or `careful` if you pick it | as `feature` | as `feature` | on | 4 |

Three rules hold in every mode:

- Ticket levels and `Sensitive:` paths still raise a ticket's review. `small` never skips a level 3 ticket's own review.
- The session suggests a heavier mode when the work outgrows its own: a `fix` with two causes offers `feature`, as it always did.
- Mid-run, `mode small` makes the run faster (it is `fast on`), and `mode <the plan's own mode>` goes back. A heavier mode changes the plan's reviews, so it needs a re-plan, which needs your yes.

## Picking one

Name it in the command, `/feature-flow csv-export small`, and nothing is asked. Otherwise the session guesses from your words and says so in one line, with the reason:

> Mode: careful (it touches src/auth/, a Sensitive: path). ok, or say fix / small / feature / explore.

"ok" takes it. With `auto` or `agent` the guess is taken and said. On the guided page the plan-yes card shows the mode too, as its first choice.

The mode is written into the plan's `commands.md` as a `Mode:` line, approved and frozen with the plan. `FLOW_MODE=<mode>` on `start` overrides the line for one run.

## Older names

Each mode stands on one of the old profiles, so a plan made before modes runs exactly as before:

| Old | Now |
|---|---|
| `fast`, `Profile: fast`, `FLOW_PROFILE=fast` | `small` |
| `standard` | `feature` (and `explore`, once built) |
| `careful` | `careful` |
| `normal` | `fix` (and a plan with no `Mode:` or `Profile:` line) |
| `FLOW_PROFILE` | `FLOW_MODE` |

## Settings the mode now sets alone

Since 0.44.0 only the mode sets these, and a run ignores them when they are set by hand (0.43.0 warned):

`FLOW_FAST`, `FLOW_REVIEWERS`, `FLOW_ROUND_REVIEW`, `FLOW_BASE_GATE`, `FLOW_GATE_FULL`, `FLOW_BATCH`, `FLOW_MAX_RETRIES`, `FLOW_MAX_REVIEW_ROUNDS`.

`FLOW_GATE=off` is ignored too: only `Gate: off unsafe` in the approved `commands.md` turns the gate off, so it always shows in the plan. `start` prints one line for each setting it ignored, and `feature-flow config` lists them on its `Ignored:` line.

The settings that stay yours to override: `FLOW_MODE`, `FLOW_LANES`, `FLOW_SCOUTS`, `FLOW_BUDGET`, `FLOW_CODEINTEL`, `FLOW_GATE_TIMEOUT`, `FLOW_TICKETS_PER_SESSION`, `FLOW_DIR` and `FLOW_TICKETS` ([all settings](commands-and-settings.md)).

## See what a run will use

`feature-flow config <feature>` prints the plan's mode and where it came from, then every setting the run will use, its value and where that came from: the mode, `commands.md`, your shell, or built in. Without a feature it shows what a new plan gets from the template. `--all` adds the settings the mode keeps to itself. It is read-only, and it reads the settings the way the conductor does, so the two cannot disagree.

```
$ feature-flow config checkout-retry
Feature: checkout-retry
Mode: small        commands.md (Mode: small)

setting               value                                       from
reviews per ticket    one review of the whole feature at the end  mode small
round review          off                                         mode small
full gate and review  at the end                                  mode small
gate at the base      off                                         mode small
lanes                 1                                           built-in
scouts                off                                         mode small
...
Plan lines: Build, Test, Lint, Smoke
```

