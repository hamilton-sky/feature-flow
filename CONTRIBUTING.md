# Contributing

feature-flow is a small, standard-library Python project with one maintainer. Issues and field-run reports are the most useful thing you can send (see [docs/field-run.md](docs/field-run.md)).

- Run the checks before a pull request: `bash tests/run.sh`, which runs the unit tests in `tests/py` as four shards side by side (`python3 tests/shard.py all 4`, each shard in its own process and temp folder). CI runs the same four shards as parallel jobs (`python tests/shard.py <k> 4`) on Linux, macOS and Windows, and `tests/run.sh` on Linux and macOS. A pull request that changes only `docs/`, `README.md`, `CONTRIBUTING.md` or `LICENSE` runs a short docs check instead. The package jobs run on `main` only.
- Forkboard, the brainstorm's review page, is its own package in [packages/forkboard/](packages/forkboard/), with its own checks: `python3 -m unittest discover -s packages/forkboard/tests`, and `npm install && npm test` in `packages/forkboard/tests/browser/` to drive the page in Chromium. It never reads or writes feature-flow's files; feature-flow hands it a review document.
- Tests must not skip by platform (`skipUnless`): the floor guard treats a new skip as weakening the bar. Write test commands that work everywhere, for example `python -c` scripts.
- Editing `scripts/flow-trust.py` changes the sha256 its skills pin. Re-pin it in `skills/feature-flow/SKILL.md` and `adapters/codex/feature-flow/SKILL.md` and run the tests.
- The page is a view over the files ([docs/source-of-truth.md](docs/source-of-truth.md)): a page feature must not keep anything the session cannot write into a plan or brainstorm file through a named command.
- Keep to what a bug or an observed run shows. A new option multiplies the combinations the tests have to cover (`tests/py/test_mode_matrix.py`).
- Describe the change in the pull request as before and after, in plain language.
