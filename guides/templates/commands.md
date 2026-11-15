# Commands: <feature>

The real commands for this project, read from its own config (package.json, Makefile,
Taskfile, CI). Approved by a human when the plan is approved. Workers read this file and
must not change it. Each command must run without asking anything and exit non zero on
failure. Delete a line you do not have; a line left as a placeholder is skipped.

`Mode:` says what kind of work this is and sets the reviews, the gate, the lanes and the
scouts for you (docs/modes.md): `fix` (one bug), `small` (a clear change, one review at the
end), `feature` (the default: two reviewers side by side, a review of each round), `careful`
(auth, money, data, shared code: the full gate and two reviewers on every ticket) or `explore`
(a brainstorm first, then built as feature).

Mode: `feature`
Build: `<command>`
Test: `<command>`
Lint: `<command>`
Smoke: `<the quickest command that proves the base is healthy, run before every ticket>`

Optional lines (delete the ones you do not need):

Quick: `<the fast subset of Test, run after the tickets in the middle of the plan; Test runs after the last ticket and before each handoff>`
Typecheck: `<the type checker, such as tsc --noEmit or mypy, run after Lint>`
Security: `<a security scan, such as semgrep --config auto --error, run after Lint>`
Check <path>: `<a command for one part of the repo, run only when a ticket changes a path under it. replace <path> with it, e.g. Check web/: npm run e2e>`
Run: `<command, if the feature has something to start>`
Setup: `<what a fresh checkout needs before Build and Test run, such as npm ci. run once in each lane worktree>`
Shared: `<paths many tickets change, comma separated, such as a changelog or a version file. a ticket touching one is never built beside another>`
Sensitive: `<paths that make any ticket touching them level 3, comma separated. a folder ends with /, a * glob crosses folders. e.g. src/auth/, *token*>`
Acceptance: `<the command that runs only the tests in plans/<feature>/acceptance/, which a tester writes from spec.md before the build. never part of Test>`
Lanes: `<auto or 1 to 4: how many tickets build side by side. the mode picks without it: auto, at most 2 with careful; small batches instead>`
Gate: `<each, batch N or end: when the full gate and the review run. the mode picks without it: small end, feature batch 3, careful each. off unsafe only when the plan cannot run its commands at all>`
Floor: `<allow <category>, reason: <why the bar moves for this plan>. categories: skip, suppress, empty-catch, test-delete, threshold, trivial-assert, config>`
