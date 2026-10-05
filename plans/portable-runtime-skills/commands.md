# Commands: portable-runtime-skills

The real commands for this project, read from its CI workflow. Approved by the user with the graph. Workers read this file and must not change it.

The unattended loop runs Smoke before every ticket and Test after every ticket, so each must run without asking anything and exit non zero on failure. This project has no separate build or lint command.

Test: `bash tests/run.sh`
Smoke: `bash -c 'for f in scripts/*.sh install.sh tests/*.sh examples/*.sh; do bash -n "$f" || exit 1; done'`
