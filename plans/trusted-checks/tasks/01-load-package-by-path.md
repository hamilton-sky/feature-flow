# Load the feature_flow package by path, so nothing in scripts/ or the repo root can shadow a module

Type: task
Floor: allow flow-edit
Status: resolved
Blocked by: —
Test first: yes

`scripts/flow.py` and its siblings (`flow-status.py`, `gate.py`, `floor-guard.py`, `flow-view.py`) run with their own folder on `sys.path[0]` and insert the package root (the repo root in a checkout, `.feature-flow/` in an install) at position 0. So a new `scripts/secrets.py`, or a `secrets.py` at the root of a feature-flow checkout, replaces the standard library inside the conductor: on main, a planted `scripts/secrets.py` whose `token_hex` returns "planted" makes `start` print `OK planted`.

Change each of these scripts so it adds no folder to `sys.path` and removes its own folder from it, as the very first thing after `import sys` and before any other import (`pathlib` alone pulls in `re`, `fnmatch` and `functools`, which a planted `scripts/re.py` would otherwise replace; use `os.path` only after the removal): find the package root as today (the loop over `here.parent`, `here.parent / ".feature-flow"`), then load `feature_flow` with `importlib.util.spec_from_file_location("feature_flow", root / "feature_flow" / "__init__.py", submodule_search_locations=[str(root / "feature_flow")])`, register it in `sys.modules` before executing it, and import the entry point from it as today. Keep `sys.dont_write_bytecode = True`. Keep the shared lines short and the same in every script; a tiny shared helper is not possible because nothing can be imported before the package is loaded.

Add `tests/py/test_shadow.py`, built on `helpers.Repo`: a planted `scripts/secrets.py` (and, in a second test, a planted `secrets.py` in the repo root) does not change what `start` prints (`OK ` followed by 16 hex characters), `flow-status.py <feature> --check` still prints its normal result with a planted `scripts/json.py`, and a planted `scripts/re.py` that raises on import changes nothing for `start` or `flow-status.py --check`. The same scripts still work when run with `python3 -I`.

## Not in this ticket

- Hashing the scripts: ticket 03 (the runner).
- The user's site-packages (`.pth`, `usercustomize`): closed by the runner calling the conductor with `-I`, ticket 03.

## Done when

- With a planted `scripts/secrets.py` or repo-root `secrets.py`, `start` prints `OK <16 hex>`, not the planted value.
- `python3 -I scripts/flow.py f start` in the fixture repo prints `OK ` followed by 16 hex characters (a test in `test_shadow.py`).
- `python3 -m unittest discover -s tests/py -p "test_shadow.py"` prints `OK`.
- All existing tests still pass: `python3 -m unittest discover -s tests/py` prints `OK`.

```check
$ python3 -m unittest discover -s tests/py -p "test_shadow.py"
prints OK
$ python3 -m unittest discover -s tests/py
prints OK
```

## Reference

- spec.md § Decisions (`scripts/` coverage)
- `scripts/flow.py` and its siblings; `tests/py/helpers.py` (`Repo`)

## Answer

Work started at f22ad3b91efc62396b4c5814093ec26fd7009264. Test-only commit: 3921e7d (`test(trusted-checks): 01 failing test`); at that commit `test_shadow.py` failed 3 of 5 (`OK planted` for both secrets plants, `ImportError: planted re` from `pathlib` -> `glob` -> `re`).

**Built**

- `scripts/flow.py`, `scripts/flow-status.py`, `scripts/gate.py`, `scripts/floor-guard.py`, `scripts/flow-view.py`: the same header in each. Right after `import sys`, unless `sys.flags.isolated` or `sys.flags.safe_path` (Python 3.11+, `-P`/`PYTHONSAFEPATH`) already kept it out, `del sys.path[0]` drops the script's own folder. Then `sys.dont_write_bytecode = True`, then `importlib.util` and `pathlib`; the root is found by the same loop as before, and `feature_flow` is loaded with `spec_from_file_location(..., submodule_search_locations=[pkg])`, registered in `sys.modules` before `exec_module`, and the entry point is imported from it as before. No folder is added to `sys.path`.
- `tests/py/test_shadow.py` (new): 5 tests built on `helpers.Repo` (with `flow-status.py` copied into the fixture's `scripts/`).

**Proof**

- Planted `scripts/secrets.py` / repo-root `secrets.py`: `test_planted_secrets_in_scripts_is_not_imported` and `test_planted_secrets_in_repo_root_is_not_imported` pass; also by hand in a `helpers.Repo` fixture: `scripts plant: (0, 'OK 17c9c08d85704a22')`, `root plant: (0, 'OK 6418a5594bbacef3')`.
- `python3 -I scripts/flow.py f start` in the fixture: `OK 51f44274782bd3da` by hand; `test_scripts_work_under_isolated_mode` asserts `^OK [0-9a-f]{16}$` and that `flow-status.py --check` under `-I` prints the same as without.
- `python3 -m unittest discover -s tests/py -p "test_shadow.py"`: `Ran 5 tests ... OK`.
- `python3 -m unittest discover -s tests/py`: `Ran 271 tests in 94.645s OK`. `bash tests/run.sh`: `464 passed, 0 failed`, exit 0. Smoke command: exit 0.

**Decisions**

- Remove `sys.path[0]` by flag, not by comparing paths: comparing needs `os.path`/`pathlib`, which must not be imported before the removal. Under `-I` (all versions) and `-P`/`PYTHONSAFEPATH` (3.11+) Python never adds the script folder, so the header deletes nothing then (deleting would drop a stdlib entry).
- Added a `for ... else: sys.exit("feature_flow package not found beside ...")`: without it, a missing package would fall through to a confusing `FileNotFoundError` from `exec_module` on the last candidate; before this change it was a `ModuleNotFoundError`.
- The json test plants a `scripts/json.py` that raises on import; it already passed on main for `--check` (status does not import json on that path), so it guards against regression rather than reproducing a hole.

**Shortcuts taken**

- none

**For later tickets**

- Ticket 03 (runner): the scripts now work under `python3 -I`, so the runner can call the conductor with `-I`; nothing in `scripts/` or the repo root is importable by the conductor any more. A script run via `exec` of its source (rather than as `python3 scripts/x.py`) would have `sys.path[0]` as whatever the caller had; the runner should run the conductor as a subprocess `python3 -I <path>`, where nothing is deleted.
- `tests/py/helpers.Repo` copies only `scripts/flow.py`; tests that need another script copy it themselves (as `test_shadow.py` does for `flow-status.py`).
