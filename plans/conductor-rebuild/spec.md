# Conductor rebuild — Spec

## Problem

`feature_flow/conductor.py` is 2,304 lines and one `Conductor` class with about 134 methods. The maintainer (shammai): "The conductor is getting large. 2,298 lines in one file. Every new mode adds branches to it, and the combinations multiply." The phase word (`build`, `review`, `ask`, `test`, `final`, `merge`) is tested in about 32 places and `num("lanes") > 1` in 9, so each new phase or mode is threaded through 5 to 7 methods. `self.dispatch() if self.num("lanes") > 1 else self.pick_ticket()` is written out 4 times (in `judge_final` twice, `judge_test`, `check_acceptance`). Lane work swaps `self.st` and `self.lane` and calls `os.chdir` inside `in_lane`, and `prompts.REPO` is a module global the conductor flips.

The approved design is the artifact "Conductor Rebuild Plan"; the brief carries its content (the layers, the phase and scheduler protocols, which commands stay on the facade) and its ten steps, and this spec copies them. This plan is the authority for builders: no builder needs to open the artifact.

## Goal and the bar

`feature_flow/conductor.py` becomes the package `feature_flow/conductor/` of small layered modules, with no change in behaviour that any caller, test or user can see.

**The bar.** All of these hold:

1. `bash tests/run.sh` passes (it ends with `N passed, 0 failed` and exits 0). It runs every existing test (changed only in the file paths they name, as the brief's Decided line allows: see § Decisions, Tests that name `conductor.py`) and the new golden test, which matches the recordings made in ticket 01 on the code as it is before ticket 03.
2. `python3 -c "import feature_flow.conductor as c; print(c.Conductor, c.Stop, c.NoPhase)"` prints the three classes and exits 0.
3. `feature_flow/conductor.py` no longer exists.
4. The ratchet test passes: `feature_flow/conductor/facade.py` is under 300 lines and every other `.py` file of the package is under 400.

## Stories

### A maintainer adds a mode

**As** the maintainer, **I want** each phase, scheduler, guard and rule in its own small module, **so that** a new phase or mode is one new class plus one table row, not branches in 5 to 7 methods.

- [ ] Each phase (build, review, ask, test, final) is a class in `feature_flow/conductor/phases/` (new), found through one registry; `next`, `prompt`, `verdict`, `scouts`, `pending_phase` and `phase_key` route through it.
- [ ] Serial, batch and lane runs are scheduler classes in `feature_flow/conductor/schedulers/` (new), chosen once per call; the end of a run (acceptance tests due, the acceptance run, the feature review, `DONE`) is one shared step.
- [ ] Which modes may run together is one table in `feature_flow/conductor/settings.py` (new), with a test per row.
- [ ] The level rules are the pure functions `policy.levels.declared`, `policy.levels.measured` and `policy.levels.describe`, the review decision tree is `policy.review.after_checks` and `policy.review.on_fail`, and the round limit is `policy.limits.round_cap` (all under `feature_flow.conductor`, signatures in § Interfaces); each returns the same level, reason, decision and notes as today's methods for every row of a table test in `tests/py/test_policy.py`.
- [ ] The facade is under 300 lines and no package module reaches 400 (a ratchet test keeps it so).

### A user runs the flow

**As** a user of `/feature-flow`, **I want** nothing to change, **so that** a run behaves the same before and after, including a run paused between tickets on the old code and resumed on the new.

- [ ] The CLI and its 17 commands take the same arguments and print the same lines (BUILD, REVIEW, ASK, TEST, WAIT, HANDOFF, DONE, OK, RETRY, SCOUT, NONE, PLAN, STOP), byte for byte, with the same exit codes (0, 1 for STOP, 2 for NoPhase and usage).
- [ ] Every `STOP` message is the same text.
- [ ] The state file has the same keys and the same `key=value` format; the log has the same events; findings files, the ticket sections and `followups.md` text the conductor writes are the same.
- [ ] A run paused between tickets (at a `HANDOFF`) on the old code goes on with the new code: `start` then `next` print the same lines (shas, tokens and paths replaced) as a twin run that stayed on the old code (acceptance test A3). This is the only resume the feature must provide.
- [ ] A run paused mid-ticket keeps today's behaviour, with nothing built for it: `Conductor.check_code` stops `next` with `STOP flow code changed while building <ticket>: ...`, as it does for any change to the flow's files mid-ticket (unless the ticket has `Floor: allow flow-edit`). Acceptance test A4 checks that this STOP, and not an `is damaged` STOP, is what such a run meets.

## Scope

In: the ten steps of the design (ticket map below), a golden test recorded first, the package layout in `pyproject.toml` so the wheel carries the new folders, and the smallest test-harness edits that a moved file forces: path-only changes, per the brief's Decided line (§ Decisions, Tests that name `conductor.py`).

Not in scope:
- Any behaviour change, new mode, option or `FLOW_` variable.
- `feature_flow/cli.py`: it keeps `from feature_flow.conductor import Conductor, NoPhase, Stop` and is not edited.
- Skills, guides, agents, `scripts/` (including `scripts/flow-trust.py`, whose sha is pinned), README and docs (none of them names `conductor.py`).
- The version (stays 0.24.0) and `tests/run.sh`'s pinned version line.
- The brainstorm page (`feature_flow/brainstorm_page.py`; there is no `brainstorm_live.py` in this checkout).

Steps to tickets: 0 → 01, 1 → 03, 2 → 04, 3 → 05, 4 → 06, 5 → 07, 6 → 08, 7 → 09 (serial, batch, end of run) and 10 (lanes), 8 → 11, 9 → 12 (Workspace), 13 (`cwd=` in the helpers outside the package) and 15 (no `os.chdir` left), 10 → 16 (the facade under 300) and 14 (ratchet, with the bar). There is no ticket 02: the settle ticket of the first draft was answered by the brief's Decided line, and numbers are never reused.

## Happy path

1. A session runs `python3 scripts/flow.py f next` → `cli.run` builds `Conductor(feature, scripts)` from `feature_flow.conductor` → the facade loads Settings and the state views, picks the scheduler once and routes to the pending phase in the registry → the phase judges and hands out the next one → the session sees the same `BUILD ...` / `REVIEW ...` line as before.
2. With `FLOW_LANES=2`, the facade picks the LaneScheduler, which leases, merges, refreshes and rebuilds as `dispatch`, `lease`, `integrate`, `refresh` and `rebuild` do today, working in each lane through a Workspace instead of `os.chdir`.
3. When no ticket is left, the shared EndOfRun step runs the acceptance tests, the feature review for deferred tickets, and prints the same `DONE` line.

## Edge cases

| Trigger | Expected behaviour | Handled in ticket |
|---|---|---|
| A run paused between tickets (at a `HANDOFF`) on the old code | `start` and `next` on the new code print what the old code would have: the state keys and format do not change | 05, acceptance A3 |
| A run paused mid-ticket on the old code (any phase, any lane) | No change and nothing to build: `check_code` (kept as it is) stops with today's `flow code changed while building ...` text, as for any change to the flow's files mid-ticket | 05 keeps the state readable; acceptance A4 |
| A bad `FLOW_LANES` (`9`, `x`) | Only `start` stops, with the same message as today (`FLOW_LANES must be 1 to 4, not 9`, or `FLOW_LANES must be a whole number, not x`); other commands ignore it, as today. Settings must not validate it eagerly | 04 |
| Two bad settings at once (a bad profile and `FLOW_MAX_RETRIES=x`) | The same first STOP as today: Settings checks in the order `Conductor.__init__` does now (profile, then the `_env_int` values, then the git worktree, then the state folder) | 04 |
| `FLOW_LANES=2` with `FLOW_RELAY=1`, lanes from a subfolder, `FLOW_DRIVER=robot`, `FLOW_FAST=2` | The same STOP text, from one rules table | 04 |
| An agent driver with no `FLOW_TICKETS_PER_SESSION` or one filled by a profile | `per_session` is 0, as today (`test_agent_driven` reads `Conductor('f', 'scripts').per_session`) | 04 |
| A ticket not yet committed at its base | `base_level` reads `Level:` from the working file but counts `Floor: allow flow-edit` only from the committed ticket (`flow_edit_allowed` returns False when absent); `footprint` reads both at HEAD. The pure rules take the flag from the caller so these differences stay | 06 |
| A level 2 ticket past `FULL_ROUNDS` with only majors | Passes with follow-ups, as `judge_review` does now | 06 |
| A batch | Its tickets go through the same check pipeline without the gate, as `judge_batch` does now | 07 |
| `pick_ticket` and `dispatch` at the end | Their differences stay: `pick_ticket` checks tests due before `--next`, `dispatch` only when no lane is busy; lanes are removed only at the end of a lane run | 09, 10 |
| A level 3 lane ticket whose base is behind the feature head | Refreshed and reviewed again, as `refresh` does now | 10 |
| The session handoff in `dispatch` with busy lanes | `WAIT` instead of `HANDOFF`; re-plan check only with no busy lane; budget offer only with no busy lane | 11 |
| `FLOW_RELAY=1` | `HANDOFF` after each phase, checked before any judging, as `next` does now | 11 |
| Guides and roles while a lane works | Read from the main worktree, never the lane's copies (today via `prompts.REPO`) | 12 |
| A lane worktree that is gone | The same `lane N (...) is gone` STOP | 12 |
| Code that runs in a lane after the switch to `cwd=` | Every git call, check, gate, floor guard, graph read and relative ticket path resolves in the lane folder; the process working folder never changes | 13, 15 |
| `tests/py/test_proof.py` patches `proof.test_first` with a five-argument lambda | Still works: `proof.test_first` keeps its five positional parameters and the conductor calls it with five positional arguments, never a keyword | 15 |
| `tests/py/test_trust_drive.py` and `tests/py/test_trust_runner.py` insert `return` after `check_code`'s docstring (8 spaces in) | Still a code change that stops the run naming the edited file: `check_code` stays a `Conductor` method in `facade.py`, with that docstring, to the end | 03 to 16 |
| A test that patches `Conductor.check_code` (`tests/py/test_proof.py`) | Still disables the code check: every phase calls `check_code` through the Conductor instance | 03 to 16 |
| A test that patches `git._git` with `fail(*args, **kw)` (`tests/py/test_proof.py`) | Still works with the new `cwd=` keyword, which reaches it as `**kw` | 13 |

## Design

```
 cli.py (unchanged)
   │ Conductor(feature, scripts).<command>(...)
   ▼
 conductor/__init__.py ──► facade.Conductor   (17 commands, < 300 lines)
   │                          │
   │      ┌───────────────────┼─────────────────────┬──────────────┐
   │      ▼                   ▼                     ▼              ▼
   │  settings.Settings   store.RunState      schedulers/      planning.Planner
   │  + MODE_RULES        store.TicketState   Serial | Batch    (plan, review,
   │                      (key=value file)    | Lanes ──► EndOfRun   accept, scouts,
   │                                            │                consult, brainstorm)
   │                     guards.BEFORE_TICKET ──┤
   │                     (handoff, replan,      ▼
   │                      budget, smoke)     phases/ REGISTRY + TRANSITIONS
   │                     guards.AFTER_PHASE    Build Review Ask Test Final (+ Merge)
   │                     (relay)                │ uses
   │                                            ▼
   │                         buildchecks (Gate, FloorGuard, Footprint, DoneWhen, TestFirst)
   │                         policy/levels, policy/review, policy/limits (pure)
   │                         workspace.Workspace (folder, state view, lane)
   ▼
 errors.Stop / errors.NoPhase  ──► cli prints STOP <reason>, exit 1 / exit 2
```

Failure path: any layer raises `errors.Stop`; the facade lets it through and `cli.run` prints `STOP <reason>` and logs it, exactly as now.

### Decisions

- **Where the Conductor class lives** — options: in `feature_flow/conductor/__init__.py`; in `feature_flow/conductor/facade.py` (new) with `__init__.py` re-exporting it. Chosen: `facade.py`. Why: the ratchet names one facade file, and `__init__.py` stays a short, stable file that existing tests can name.
- **Tests that name `conductor.py`** — decided by the user (brief, Decided, option A): the package replaces the file, and existing tests that name `feature_flow/conductor.py` change only that path, never what they assert. Where each points:
  - `tests/py/test_trust_drive.py` and `tests/py/test_trust_runner.py` tests that append bytes or check the trust file's list, `tests/py/test_state_report.py` (appends `Conductor.next = crash`, which works because `__init__.py` imports `Conductor`) and `tests/py/test_install.py`: `feature_flow/conductor/__init__.py`, from ticket 03 on.
  - `tests/py/test_trust_drive.py`'s `PlantedBytecode` checks the source holds `b'"BUILD %s %s %s%s"'`: `feature_flow/conductor/facade.py` from ticket 03, `feature_flow/conductor/phases/build.py` from ticket 08 (the build hand-out moves there).
  - `tests/py/test_trust_runner.py`'s `PlantedBytecode.plant` checks the source holds `b'return "OK %s" % token'`, at the same size after the edit, and `PlantedBytecodeCrlf.prepare` converts that same file to CRLF before the plant: both point at `feature_flow/conductor/facade.py`, where `start` keeps that line to the end. `prepare` always names the file `plant` names, in every ticket.
  - The two `check_code` tests read its docstring (`"""Stop when the files the conductor runs from changed since the ticket was picked."""`) and insert `return` after it: `tests/py/test_trust_drive.py`'s `Holes.test_a_builder_commit_that_makes_check_code_return_early` and `tests/py/test_trust_runner.py`'s `test_hole_a_a_committed_return_in_check_code`. Both point at `feature_flow/conductor/facade.py`, where `check_code` stays a `Conductor` method (it is on the compatibility seam too) with that docstring at the same indent, to the end.
  - So the strings live in two files at most: `facade.py` (`return "OK %s" % token` and the `check_code` docstring) and the build phase (`"BUILD %s %s %s%s"`). Any later ticket that moves one of them points every test that reads it at the file that now holds it, in the same commit; every ticket that edits the package lists both test files under `Touches:` for that reason, and both are on the `Shared:` line. `tests/run.sh`'s `flowrepo` copies the whole package folder (ticket 03).
- **Order of the work** — options: the brief's order (golden first, lanes last); by risk. Chosen: the brief's order, one ticket per step; step 7 splits in two (lanes last), step 9 in three, in this order (12 the Workspace, 13 `cwd=` in the helpers outside the package, 15 no `os.chdir` left), each blocked by the one before even where the files would allow otherwise, and step 10 in two (the facade trim, then the ratchet with the bar). Why: the brief fixes it, and each step leaves the suite green.
- **One plan, not rounds** — 15 tickets (01 and 03 to 16; 02 was answered by the brief) is over the guide's "about 12". Options: one plan; round one (steps 0 to 5) and round two (6 to 10). Chosen: one plan. Why: the bar (facade under 300) is only reachable at the end, so a first round could not prove it, and the order is fixed anyway.
- **Golden test drives the CLI** — options: drive `scripts/flow.py` in throwaway repos (as the `*_drive.py` tests do with `tests/py/helpers.py`'s `Repo`); call `Conductor` methods in process. Chosen: the CLI. Why: it records exactly what users see and never depends on internal names that the refactor moves.
- **Golden prompts use fixture guides** — options: copy the real `guides/` and `agents/` into each scenario; write small fixture role and guide files. Chosen: fixtures. Why: a later guide edit must not break the recordings, while prompt assembly (which ticket 12 changes) is still compared.
- **Guarding the recordings** — options: a hash manifest the test checks; the ticket's `Touches:` line. Chosen: `Touches:`. Why: the conductor already fails any build that changes a path outside its Touches, and no ticket after 01 lists `tests/py/golden/`.
- **Packaging** — `pyproject.toml` lists packages by name (`[tool.setuptools] packages = [...]`), so a subpackage missing there is missing from the wheel and `tests/package_smoke.py` ("both installs put the same files in place") fails. Options: add each subpackage when it appears; list all four (`feature_flow.conductor`, `.policy`, `.phases`, `.schedulers`) in ticket 03 with docstring-only `__init__.py` files. Chosen: all in ticket 03. Why: one edit to a shared file, and a test keeps the list and the folders in step.
- **Imports** — `tests/run.sh` fails any `feature_flow` import outside a fixed list of standard modules (`os sys re subprocess hashlib pathlib argparse secrets time datetime shlex typing dataclasses __future__ json textwrap tempfile shutil enum difflib stat traceback fnmatch contextlib html`) and `feature_flow`. So: absolute imports (`from feature_flow.conductor.store import RunState`), never `from . import x` (the check's regex rejects it), and no `abc`, `functools`, `collections` or `itertools`. Python 3.9 floor: `from __future__ import annotations` (Python 3.7+), no `match` (Python 3.10+), `@dataclass(frozen=True)` for Settings.
- **Settings validation stays lazy** — options: validate every `FLOW_` value when Settings is built; keep each check where it runs now. Chosen: Settings holds the raw values and `MODE_RULES` checks them where today's code does (`start`, `lane_next`). Why: a bad `FLOW_LANES` must still stop only `start`.
- **cwd instead of chdir (tickets 13 and 15)** — options: give the helpers an optional `cwd=None` keyword (None: the process folder, so every existing caller and test is unchanged) and pass the Workspace folder; keep one `os.chdir` inside the Workspace. Chosen: `cwd=`. Why: the brief asks for it. It reaches further than the conductor: `checks.gate`, `checks.floor_guard` and `checks.flow_status` run `gate.py`, `floorguard.py` and `status.py` in process, and those read `FLOW_DIR` or `plans` relative to the working folder and run git without `cwd` (`floorguard`'s own `subprocess.run(["git", ...])`). So ticket 13 gives `git.py`, `proc.py`, `checks.py`, `gate.py`, `floorguard.py` and `status.py` the keyword (on their own, before the conductor uses it), and ticket 15 makes the conductor and `proof.py` use it and removes every `os.chdir`.
- **How `proof.test_first` learns the folder** — options: a `cwd=` keyword; the folder rides in the `plan_dir` argument it already takes (an absolute plan folder inside the Workspace's folder; `proof` finds the repo top from it, and a relative `plan_dir` keeps today's behaviour). Chosen: `plan_dir`. Why: `tests/py/test_proof.py` patches `proof.test_first` with `lambda b, c, d, t, r: ...`, which rejects any keyword, and the existing tests may not change what they do. `proof.run_checks` is not patched by any test, so it takes a `cwd=None` keyword.

## Interfaces

All new paths are under `feature_flow/conductor/` (new). Exact signatures are the builders'; the names below are what tests and later tickets rely on.

**Kept, for existing callers and tests** (the compatibility seam):
- `feature_flow.conductor` exports `Conductor`, `Stop`, `NoPhase`, `followups_only` (used by `tests/py/test_levels.py`), `section_after`, `demote`, `owner_hash`.
- `Conductor(feature, scripts)`; its 17 command methods with today's names and arguments: `start`, `next`, `prompt`, `verdict`, `reset`, `fast_switch`, `scouts`, `scout_prompt`, `budget_cmd`, `replan_prompt`, `plan_prompt`, `plan_review_prompt`, `plan_accept`, `plan_scouts`, `plan_scout_prompt`, `consult_prompt`, `brainstorm_prompt`; `log(event)`; the attribute `per_session`.
- `Conductor.check_code` is looked up on the instance by every caller, so `mock.patch.object(conductor.Conductor, "check_code", ...)` (`tests/py/test_proof.py`) still turns it off.
- `Conductor.__new__(Conductor)` with only `c.st = {"base": ..., "ticket": ...}` set, then `c.ticket_at_base()`, returns the ticket at base and raises `Stop` for a bad base (`tests/py/test_proof.py`).
- `feature_flow.lanes.Scoped` and `feature_flow.lanes.RUN_KEYS` still import and behave the same (`tests/py/test_lanes.py`).
- `prompts.find_file(scripts, folder, name)` still works with three arguments (`feature_flow/codehash.py` calls it).

**New:**
- `errors.py`: `Stop`, `NoPhase` (the same class objects the package exports).
- `planning.py`: `Planner` with `plan_prompt`, `plan_review_prompt`, `plan_accept`, `plan_scouts`, `plan_scout_prompt`, `consult_prompt`, `brainstorm_prompt`; the facade forwards each.
- `settings.py`: `Settings`, a frozen dataclass built from the environment, the profile and `commands.md`; `MODE_RULES`, one table of mode rules (lanes vs relay, batch preconditions, lanes need the repo top, the `FLOW_LANES` range, `FLOW_DRIVER` and `FLOW_FAST` values), each row giving the STOP text it raises.
- `store.py`: `RunState` (the whole state dict) and `TicketState` (one ticket's view: the run's keys pass through, a lane's keys are stored as `L<k>.<key>`), over the same dict and the same file; `RUN_KEYS`.
- `policy/levels.py` (pure: values in, values out; no git, files, state or `os`):
  - `declared(text, flow_edit) -> (level, why)`: the level from the ticket text (`Level:`), raised to 3 by `Review: full`, `Type: convert` or `flow_edit` (a bool the caller reads), with today's reason texts; `why` is `""` when not raised. Behind `base_level` (flow_edit from the committed ticket at base) and `footprint`'s level (from the text at HEAD).
  - `measured(level, sensitive_hits, files, lines, binary, small_files, small_lines) -> (level, why)`: raised to 3 by any Sensitive path hit, a level 1 diff over the small limits (or binary) to 2, never lowered. Behind `measure_level`.
  - `describe(level, why) -> str`: today's `describe_level` text (`this ticket is level N (name), raised because ...`).
- `policy/review.py` (pure):
  - `after_checks(level, fast, gate_on, checks_ran, small_note, review_mode, spec_ok, round_no, level_note) -> (decision, review_pass, notes, events)`: `decision` is `"defer"` or `"review"`; `review_pass` is `spec`, `single` or `quality`; `notes` the reviewer notes in today's order and text; `events` the log events (`REVIEW-SMALL`, `REVIEW-SINGLE`). Behind `judge_build` after green checks.
  - `on_fail(level, round_no, review_pass, findings) -> "followups" | "send_back"`: the FAIL branch of `judge_review`.
- `policy/limits.py` (pure): `round_cap(level, max_rounds) -> int`, the rework rounds a ticket of that level gets (today's `round_cap`); the "limits" policy of the design.
- For the three policy modules: builders may add keyword arguments when today's code needs a value not listed, keeping these names.
- `buildchecks.py`: check classes `Gate`, `FloorGuard`, `Footprint`, `DoneWhen`, `TestFirst` and an ordered pipeline that returns the first failure as `(source, report)` or the notes for the reviewer.
- `phases/`: phase classes for build, review, ask, test and final (ticket 08) and merge (ticket 10); `REGISTRY` (phase word to class) and `TRANSITIONS` (which phase may follow which). The phase protocol (the brief's Design): `name`; `lane_scoped` (False for test and final); `hand_out(ws) -> line`; `judge(ws) -> Outcome`; `prompt(ws) -> str`; `record(ws, reply) -> str` (the default raises `NoPhase`); `scout_questions(ws) -> list`; `key(ws) -> str`. `Outcome` has `line` (str or None) and `passed` (bool: the scheduler counts the ticket, or in lanes queues its merge). Until ticket 12, `ws` is the Conductor itself; from ticket 12 it is a `Workspace`.
- `schedulers/`: `SerialScheduler`, `BatchScheduler`, `LaneScheduler` (with the merge phase) and `EndOfRun`. The scheduler protocol: `next(lane)`, `on_passed(ws)`, `resume()` (the next line after a test or final phase; it replaces the 4 copies of `dispatch() if lanes else pick_ticket()`).
- The facade (the brief's Design): owner check, `tick`, then hand off: `next` to the scheduler, `prompt`, `verdict` and `scouts` to the pending phase, the planning commands to `Planner`. `start`, `reset`, `fast_switch`, `budget_cmd` and `replan_prompt` stay facade methods that delegate to guards, budget or settings code.
- `guards.py`: `BEFORE_TICKET`, the ordered guards before each ticket (session handoff, re-plan check, budget, smoke), and `AFTER_PHASE` (relay). `budget.py`: the time budget code (`tick`, `set_budget`, `check_budget`, the report).
- `workspace.py`: `Workspace` (folder, state view, lane), of one of three kinds: the main worktree, lane k, or the integration worktree; handed to phases in place of `self.st` and `self.lane`.

## Acceptance tests

The tester writes these under `plans/conductor-rebuild/acceptance/` (run by the `Acceptance:` command in `commands.md`) from this spec alone, before ticket 01. They drive the CLI, `python3 scripts/flow.py <feature> <command>` with `FLOW_TRUSTED=1` set (as `tests/run.sh`'s `pyflow` does; `next`, `prompt` and `verdict` refuse to run without it), in throwaway git repos (`tests/py/helpers.py`'s `Repo` copies the current `feature_flow/` and `scripts/flow.py` into one). Until the rebuild is done they fail, by design.

- **A1** `python3 -c "import feature_flow.conductor as c; print(c.Conductor, c.Stop, c.NoPhase)"` exits 0 and prints three class names; `feature_flow.conductor.errors.Stop is feature_flow.conductor.Stop`.
- **A2** `feature_flow/conductor.py` does not exist; `feature_flow/conductor/facade.py` is under 300 lines and every other `.py` file under `feature_flow/conductor/` under 400.
- **The old code** for A3 and A4 is the `feature_flow/` tree and `scripts/flow.py` at the first parent of the commit that removed `feature_flow/conductor.py` (`git log -1 --format=%H --diff-filter=D -- feature_flow/conductor.py` names that commit; `git archive <sha>^ feature_flow scripts/flow.py` exports the tree). When the file still exists or no such commit is found, A3 and A4 fail with a message saying so.
- **A3** Two identical throwaway repos with the old code, `FLOW_TICKETS_PER_SESSION=1`, two tickets: drive both through `start`, `next`, the first ticket's build and review, to `HANDOFF`. In one, replace `feature_flow/` and `scripts/flow.py` with the current ones and commit. In both, run `start` then `next`. The lines match after replacing shas, the session token and the repo path with placeholders (in the old twin, commit the same tree unchanged with `--allow-empty` so both have one more commit).
- **A4** (today's behaviour, kept) One throwaway repo with the old code, paused after the first `BUILD` is handed out. Resolve the ticket and, in the same commit, replace `feature_flow/` and `scripts/flow.py` with the current ones (the tree must be clean before `next`). Then `next` exits 1 and prints a line starting `STOP flow code changed while building`, the text the old code's `check_code` gives for any change to its files mid-ticket; it does not print `is damaged`.

## Migration and compatibility

No data migration: the state file keys and format do not change, so a run paused between tickets on the old code resumes on the new; a run paused mid-ticket meets today's `check_code` STOP. The installed copy (`install.py` copies the whole package folder; `scripts/flow-trust.py` and `feature_flow/codehash.py` hash every file under `feature_flow/`, recursively) picks the package up without changes; the trust digest of a run changes once, when the files change, as it does for any upgrade.

## Risks

- A subtle behaviour change slips through a move — the golden test (recorded before ticket 03) and the existing drive tests run after every ticket; every ticket is level 3.
- The run that builds this feature uses the conductor it is rebuilding — this repo has no in-repo install (`.feature-flow/feature_flow` is absent), so the run is driven by the home install, which the edits do not touch. Keep it that way: never run `install.py .` into this repo during the build.
- The wheel misses a new folder — ticket 03's package test checks that every package folder is listed in `pyproject.toml`.
- An import cycle between `feature_flow/lanes.py` and `store.py` when lanes re-exports `Scoped` — `store.py` must not import `lanes`.
- Windows: the golden test runs on the Windows CI job too (tests must not skip by platform, CONTRIBUTING.md), so its normalisation handles `\` paths and CRLF.
