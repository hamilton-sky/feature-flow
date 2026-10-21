# Commands: <feature>

The real commands for this project, read from its own config (package.json, Makefile,
Taskfile, CI). Approved by a human when the plan is approved. Workers read this file and
must not change it.

The flow runs Smoke before every ticket and Build, Test and Lint after every
ticket, so each must run without asking anything and exit non zero on failure. `Quick:` is
optional: when set, it runs in place of Test after the tickets in the middle of the plan, and
Test runs after the last ticket and before each handoff. `Sensitive:` is optional: a ticket whose
diff touches one of its paths is reviewed as level 3 whatever its own `Level:` says. `Shared:` and
`Setup:` matter only when tickets are built side by side (`FLOW_LANES`): a ticket that touches a
`Shared:` path is built alone, and `Setup:` runs once in each new lane worktree. Delete a line
you do not have; a line left as a placeholder is skipped.

Build: `<command>`
Test: `<command>`
Quick: `<optional: the fast subset of Test, run after the tickets in the middle of the plan; Test runs after the last ticket and before each handoff>`
Lint: `<command>`
Smoke: `<the quickest command that proves the base is healthy, run before every ticket>`
Run: `<command, if the feature has something to start>`
Shared: `<optional: paths many tickets change, comma separated, such as a changelog, a version file or a routes table. a ticket touching one is never built beside another>`
Setup: `<optional: what a fresh checkout needs before Build and Test run, such as npm ci or a venv install. run once in each lane worktree>`
Sensitive: `<optional: paths that make any ticket touching them level 3, comma separated. a folder ends with /, a * glob crosses folders. e.g. src/auth/, *token*, scripts/>`
