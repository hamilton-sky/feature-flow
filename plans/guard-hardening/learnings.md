# Learnings: guard-hardening

Append one line per lesson: `- (NN) what you found`. Never rewrite existing lines.
- (01) A new tests/py fixture that needs the installed layout: delete feature_flow/ and scripts/ from helpers.Repo, run install.py [--private] into it; use `git commit --allow-empty` since a private install adds nothing to commit.
- (02) lookbehind in floorguard regexes is fine now (no mawk); 'pytest.importorskip' is matched as a prefix, so don't use it as a look-alike.
- (03) in a shared helpers.Repo test, a 'Floor: allow' line committed in one step leaks into later steps; rewrite the ticket's Floor line before each base commit. Use commit --allow-empty when a step may not change anything.
- (04) a conductor test that needs prompts must copy agents/ and guides/ into helpers.Repo; a verdict file must live outside the repo or the next pick sees a dirty tree.
- (05) tests/run.sh takes ~2 minutes with the unit tests; run it in the background or with a long timeout.
- (06) a test that starts a sleeper must pass the timeout as a float argument (gate.run(..., timeout=0.02)); the env var is whole minutes. Use sys.executable plus a script file in test commands so the same command runs under bash and cmd.exe.
- (07) a ticket added after the base fails the floor guard and one committed during review stops the run, so test a stale limit by editing limit= in the state file.
- (08) after 'install.py . --agent all --force' in this repo, rm .feature-flow/{agents,guides,feature_flow,installed.txt,installed.sha256} (never state/) or the tree stays dirty.
