# Commands: <feature>

The real commands for this project, read from its own config (package.json, Makefile,
Taskfile, CI). Approved by a human when the plan is approved. Workers read this file and
must not change it.

The unattended loop runs Smoke before every ticket and Build, Test and Lint after every
ticket, so each must run without asking anything and exit non zero on failure. Delete a line
you do not have; a line left as a placeholder is skipped.

Build: `<command>`
Test: `<command>`
Lint: `<command>`
Smoke: `<the quickest command that proves the base is healthy, run before every ticket>`
Run: `<command, if the feature has something to start>`
