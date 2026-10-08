# Load the feature_flow package by path, so nothing in scripts/ or the repo root can shadow a module

Type: task
Floor: allow flow-edit
Status: open
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
