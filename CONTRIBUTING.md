# Contributing

feature-flow is a small, standard-library Python project with one maintainer. Issues and field-run reports are the most useful thing you can send (see [docs/field-run.md](docs/field-run.md)).

- Run the checks before a pull request: `bash tests/run.sh`, which runs the unit tests in `tests/py` as four shards side by side (`python3 tests/shard.py all 4`, each shard in its own process and temp folder). CI runs the same four shards as parallel jobs (`python tests/shard.py <k> 4`) on Linux and macOS, eight on Windows, and `tests/run.sh` on Linux and macOS. The shards are balanced by each test file's time in `tests/py/timings.json`; after adding or slowing down a test file, refresh it with `python3 tests/shard.py time`. A pull request that changes only `docs/`, `README.md`, `CONTRIBUTING.md` or `LICENSE` runs a short docs check instead. The package jobs run on `main` only.
- Forkboard, the brainstorm's review page, is its own package in [packages/forkboard/](packages/forkboard/), with its own checks: `python3 -m unittest discover -s packages/forkboard/tests`, and `npm install && npm test` in `packages/forkboard/tests/browser/` to drive the page in Chromium. It never reads or writes feature-flow's files; feature-flow hands it a review document.
- Tests must not skip by platform (`skipUnless`): the floor guard treats a new skip as weakening the bar. Write test commands that work everywhere, for example `python -c` scripts.
- Editing `scripts/flow-trust.py` changes the sha256 its skills pin. Re-pin it in `skills/feature-flow/SKILL.md` and `adapters/codex/feature-flow/SKILL.md` and run the tests.
- The page is a view over the files ([docs/source-of-truth.md](docs/source-of-truth.md)): a page feature must not keep anything the session cannot write into a plan or brainstorm file through a named command.
- Keep to what a bug or an observed run shows. A new option multiplies the combinations the tests have to cover (`tests/py/test_mode_matrix.py`).
- Describe the change in the pull request as before and after, in plain language.

## Where code lives

`feature_flow/` holds the four entry modules at its top (`__init__.py`, `__main__.py`, `command.py` for the `feature-flow` command, `cli.py` for `scripts/flow.py`) and six folders, top to bottom:

| Folder | Holds |
|---|---|
| `commands/` | one module per user command: `flow_status` (the `flow-status.py` dispatcher), `doctor`, `report`, `evaluate`, `importer`, `fixer`, `clean`, `install`, `uninstall`, `config`, `released` |
| `pages/` | the HTML pages: `view`, `flow_page`, `flow_plan`, `brainstorm_page`, `studio` (finds Forkboard) |
| `conductor/` | the run's state machine and its helpers: phases, schedulers, policy, `lanes`, `scouts`, `prompts`, `codehash`, `codeintel` |
| `verify/` | the checks that judge a ticket: `gate`, `floorguard`, `proof`, `checks` |
| `plan/` | reading and checking plan files, no processes: `tickets`, `status` (the graph reader), `lint`, `modes`, `builders`, `brainstorm_mode`, `repaircheck`, `reality` |
| `infra/` | leaves: `git`, `state`, `proc`, `suggest`, `plan_lock` |

A module may import its own folder or any folder below it, never one above, and `infra/` imports nothing else from `feature_flow`. `tests/py/test_layout.py` checks this with every import, including those inside functions, and also checks for import cycles, that every folder is in `pyproject.toml`'s `packages`, and the line limits. A new module goes in the folder whose job it does; a new folder needs a line in `pyproject.toml`.
