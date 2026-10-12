# Contributing

feature-flow is a small, standard-library Python project with one maintainer. Issues and field-run reports are the most useful thing you can send (see [docs/field-run.md](docs/field-run.md)).

- Run the checks before a pull request: `python3 -m unittest discover -s tests/py` and `bash tests/run.sh`. CI runs both on Linux, macOS and Windows.
- Tests must not skip by platform (`skipUnless`): the floor guard treats a new skip as weakening the bar. Write test commands that work everywhere, for example `python -c` scripts.
- Editing `scripts/flow-trust.py` changes the sha256 its skills pin. Re-pin it in `skills/feature-flow/SKILL.md` and `adapters/codex/feature-flow/SKILL.md` and run the tests.
- Keep to what a bug or an observed run shows. A new option multiplies the combinations the tests have to cover (`tests/py/test_mode_matrix.py`).
- Describe the change in the pull request as before and after, in plain language.
