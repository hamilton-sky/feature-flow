# Acceptance: the user install runs the flow in a fresh repo and uninstalls clean

Type: task
Status: open
Blocked by: 01, 02, 03, 04, 05, 06
Test first: no

Add a section to `tests/run.sh` (near the other `--user` blocks; follow its `ok`/`bad`/`expect_has` helpers) that runs the bar. In a temp dir: set `HOME`, `CLAUDE_HOME`, `AGENTS_HOME` and `FEATURE_FLOW_HOME` unset-or-under the temp home, `git init` a fresh repo with no feature-flow files, run `python3 "$ROOT/install.py" --user --agent all`, then from the repo run `python3 "$HOME/.feature-flow/scripts/flow.py" demo start` and capture the first line. In a second fresh repo run `python3 "$ROOT/install.py" .` and `python3 scripts/flow.py demo start`. Assert the two first lines are equal. Assert the first repo has no `scripts/`, `.feature-flow/installed.txt` or `.claude`. Run `python3 -m feature_flow uninstall --user` and assert the temp home has no files left (`find "$HOME" -type f` prints nothing) and `~/.feature-flow` is gone. Also assert `python3 -m feature_flow --version` prints `feature-flow 0.4.0`.

If the bar fails, fix the owning code in this ticket only when the fix is a few lines; otherwise reopen the ticket that owns it and say so in the Answer.

## Not in this ticket

- Windows or a real Codex agent run (out of scope for the whole feature).

## Done when

- `bash tests/run.sh` prints `FAIL`-free output and exits 0, including the new bar section.
- `python3 -m unittest discover -s tests/py` prints `OK`.

```check
$ python3 -m unittest discover -s tests/py
prints OK
$ bash tests/run.sh
exit 0
```

## Reference

- spec.md § Goal and the bar
- `tests/run.sh`

## Answer

