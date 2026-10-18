# Commands: <feature>

The real commands for this project, read from its own config (package.json, Makefile,
Taskfile, CI). Approved by a human when the plan is approved. Workers read this file and
must not change it.

The flow runs Smoke before every ticket and Build, Test and Lint after every
ticket, so each must run without asking anything and exit non zero on failure. `Quick:` is
optional: when set, it runs in place of Test after most tickets, and Test runs after the last
ticket and after a ticket marked `Gate: full`. The gate's commands see `FLOW_BASE`, the commit the
ticket started from, so Quick may test only what changed (`git diff --name-only "$FLOW_BASE" HEAD`).
`Times:` is for people: how long each command took when the planner ran it. Delete a line
you do not have; a line left as a placeholder is skipped.

Build: `<command>`
Test: `<command>`
Quick: `<optional: the fast subset of Test (the changed packages, say), run after most tickets; Test runs after the last ticket and after Gate: full tickets>`
Lint: `<command>`
Smoke: `<the quickest command that proves the base is healthy, run before every ticket>`
Run: `<command, if the feature has something to start>`
Times: <measured once by the planner, for example: Smoke 40s | Quick 1m10s | Test 6m | Lint 20s>
