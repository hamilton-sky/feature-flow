# Document the user install and bump the version to 0.4.0

Type: task
Status: open
Blocked by: —
Test first: no

Set `__version__ = "0.4.0"` in `feature_flow/__init__.py`. In `README.md` describe the two choices: `feature-flow install --user` (once, for every repo: skills and roles in `~/.claude` / `~/.agents`, the conductor, guides and package in `~/.feature-flow/`, `FEATURE_FLOW_HOME` moves it, no repo files) and `feature-flow install <repo>` (one repo; its copy wins when present). Fix the lines that now say otherwise: the sentence near "To remove it" about `uninstall --user` (it also removes `~/.feature-flow`), the table row "The skill goes to", and the sentence ending "With `--user` the skill goes to the user folder, but the scripts and `.feature-flow/` stay in the repo". Update the `uninstall` line in `command.USAGE` (`feature_flow/command.py`) to name `~/.feature-flow`. Search README for `0.3` to catch a version mention.

## Not in this ticket

- Any behaviour change: tickets 01 to 05.

## Done when

- `python3 -m feature_flow --version` prints `feature-flow 0.4.0`.
- `grep -c "FEATURE_FLOW_HOME" README.md` prints a number above 0, and README no longer says the scripts "stay in the repo" for `--user`.
- `python3 -m unittest discover -s tests/py` passes.

```check
$ python3 -m feature_flow --version
prints feature-flow 0.4.0
$ grep -c "FEATURE_FLOW_HOME" README.md
exit 0
```

## Reference

- `README.md` (install, uninstall and table sections), `feature_flow/command.py` (`USAGE`), `feature_flow/__init__.py`

## Answer

