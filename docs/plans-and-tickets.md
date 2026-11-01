# Plans and tickets

[← README](../README.md) · [Docs index](README.md)

The files a plan is made of, the lines `commands.md` can hold, the ticket format and its rules, and how to start a plan from Spec Kit or OpenSpec.

## The plan folder

```
plans/
└── csv-export/
    ├── spec.md          what and why
    ├── map.md           destination, the bar, decisions so far     (workers append only)
    ├── commands.md      build, test, lint, smoke commands           (frozen once approved)
    ├── learnings.md     traps workers found                         (workers append only)
    ├── brainstorm.md    the options weighed and the one picked      (only after a brainstorm)
    └── tasks/
        ├── 01-types.md
        ├── 02-service.md
        └── 03-acceptance.md
```

`commands.md` and `learnings.md` are separate from the map because they follow different rules. Commands are approved by a human and read by the scripts, so they are frozen. Learnings grow with every ticket, so they are append only and a human prunes them (`--check` warns past 40 lines). The map stays short.

The lines `commands.md` can hold ([template](../guides/templates/commands.md)); delete the ones you do not need:

| Line | Needed | What reads it |
|---|---|---|
| `Build:`, `Test:`, `Lint:` | yes (`Test:` at least) | the gate, after every ticket |
| `Smoke:` | yes | run before every ticket; the run stops if it fails |
| `Quick:` | no | a fast subset of Test for the tickets in the middle of a plan |
| `Run:` | no | how to start what the feature builds |
| `Acceptance:` | no | turns on the [tester](helpers.md#acceptance-tests-the-tester); runs only `plans/<feature>/acceptance/` |
| `Sensitive:` | no | paths that make any ticket touching them level 3 |
| `Shared:`, `Setup:` | no | for [lanes](speed.md#tickets-side-by-side-lanes): paths that keep a ticket alone, and what a fresh worktree needs |
| `Profile:` | no | `careful`, `standard`, `normal` or `fast` for this plan ([profiles](speed.md#profiles)); a new plan's template says `standard` |
| `Gate:` | no | when the full gate and the review run: `each`, `batch N` or `end` ([checkpoints](speed.md#when-the-gate-runs-checkpoints)); without it the profile picks; `off unsafe` turns the gate off |

One markdown file per ticket in `plans/<feature>/tasks/NN-slug.md`:

````
# Add the retry policy to the job runner

Type: task                 task | settle | convert
Status: open               open | claimed | resolved | parked
Blocked by: 01, 02         or —
Test first: yes            yes | no
Level: 2                   1 light | 2 standard | 3 boundary
Touches: src/export/       the paths it changes; a build outside them goes back
Floor: allow config        optional, only when a human decides the guard may let it through

...what to do and why...

## Not in this ticket
## Done when                 commands and the results they print
```check
$ python3 -m unittest discover -s tests/py
exit 0
prints OK
```
## Reference
## Answer                    Built, Proof, Decisions, Shortcuts taken, Review fixes, For later tickets
````

- **Order comes from `Blocked by`**, not from numbers. A ticket is *ready* when it is open and every ticket it is blocked by is resolved. Lowest number wins.
- **Status lives only in the ticket files.** `map.md` never repeats it.
- **The Answers are the handoff between subagents.** The next builder reads the Answers of the tickets it depends on.
- `settle` tickets record a decision. `convert` tickets migrate something and must be safe to run twice.
- **A worker may change only** its own Status line and Answer, lines appended to `map.md` and `learnings.md`, and the code the ticket calls for. Rewriting its own Done when, editing another ticket, or touching `commands.md` fails the guard.
- `Floor:` categories: `skip`, `suppress`, `empty-catch`, `test-delete`, `threshold`, `trivial-assert` (an assertion that cannot fail, added to a test file: `assert True`, `assertEqual(x, x)`, `expect(v).toBe(v)`), `config`, `ticket-edit`, `commands-edit`, and `flow-edit` (allows the conductor's code check below, for the build only). `skip` covers skipped, expected-fail and focused tests (`.only(`, `fit(`, `fdescribe(` on test paths); `config` covers more lint and test config files, the lint and test sections of `pyproject.toml` and `setup.cfg`, scripts and test keys in `package.json`, new skip or xfail words in `conftest.py`, and a `Makefile` only when `commands.md` uses `make`. A test file that loses assertions is shown to the reviewer as a warning, not a finding. The line is read from the ticket as it was before the work started, so a worker cannot excuse itself.
- The guard needs the plan to be tracked by git. If you keep tickets in an ignored folder, it cannot see changes to them.
- The commands in `commands.md` run with nobody watching and must exit non zero on failure.

## Starting from Spec Kit or OpenSpec

If you already plan with [GitHub Spec Kit](https://github.com/github/spec-kit) or [OpenSpec](https://github.com/Fission-AI/OpenSpec), feature-flow can build what they planned:

```bash
feature-flow import specs/001-photo-albums albums              # a Spec Kit feature folder (or its tasks.md)
feature-flow import openspec/changes/add-auth auth             # an OpenSpec change folder
python3 scripts/flow-status.py albums --import specs/001-photo-albums   # the same, from a repo install
```

Or ask the session to plan `albums` from `specs/001-photo-albums`. Either way it writes `plans/<feature>/`, never over an existing plan (`--dry-run` shows what it would write):

- **One ticket per phase or section**, its tasks as the Done when items, so thirty small tasks become five tickets with real reviews, not thirty.
- **Order:** each section waits for the one before. Spec Kit's user story phases (`[US1]`, `[US2]`) wait only for the phases before the first story, so with lanes they are built side by side, and the polish phase waits for every story.
- **Touches:** the paths the tasks name, when every task in the section names one.
- **spec.md** carries the source's `spec.md` and `plan.md` (Spec Kit) or `proposal.md` and `design.md` (OpenSpec).
- **What you add:** the commands (`commands.md` is the template), a `check` block per ticket and the levels. `flow-status.py <feature> --lint` says what is missing. The skill does this with you, then asks for a yes before it commits the plan.
