# Commands: in-session-mode

The real commands for this project, read from its own config: CI runs `bash tests/run.sh`, there is no build step and no linter. Approved by a human when the plan is approved. Workers read this file and must not change it.

The unattended loop runs Smoke before every ticket and Test after every ticket, so each must run without asking anything and exit non zero on failure.

Test: `bash tests/run.sh`
Smoke: `bash -c 'for f in scripts/*.sh install.sh tests/*.sh examples/*.sh; do bash -n "$f" || exit 1; done'`
