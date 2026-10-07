# Commands: proven-checks

The real commands for this project, read from its own CI (`.github/workflows/tests.yml`): `python3 -m unittest discover -s tests/py` and `bash tests/run.sh`. There is no build step and no linter. Approved by a human when the plan is approved. Workers read this file and must not change it.

The flow runs Smoke before every ticket and Test after every ticket, so each must run without asking anything and exit non zero on failure.

Test: `python3 -m unittest discover -s tests/py && bash tests/run.sh`
Smoke: `python3 -c "import ast,pathlib; [ast.parse(p.read_text(encoding='utf-8'), str(p)) for d in ('feature_flow', 'scripts') for p in pathlib.Path(d).rglob('*.py')]"`
