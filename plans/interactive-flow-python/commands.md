# Commands: interactive-flow-python

The real commands for this project, read from its own config: CI runs `bash tests/run.sh`, there is no build step and no linter. Approved by a human when the plan is approved. Workers read this file and must not change it.

The unattended loop runs Smoke before every ticket and Test after every ticket, so each must run without asking anything and exit non zero on failure.

Test: `bash tests/run.sh`
Smoke: `bash -c 'for f in scripts/*.sh install.sh tests/*.sh examples/*.sh; do [ -e "$f" ] || continue; bash -n "$f" || exit 1; done; python3 -c "import ast,pathlib; [ast.parse(p.read_text(), str(p)) for d in (\"feature_flow\", \"scripts\") if pathlib.Path(d).is_dir() for p in pathlib.Path(d).rglob(\"*.py\")]"'`
