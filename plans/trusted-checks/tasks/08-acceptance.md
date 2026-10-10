# Acceptance: drive the flow the way the skill does and show every tamper ends in STOP

Type: task
Status: resolved
Blocked by: 01, 02, 04, 05, 06, 07
Test first: no

Add `tests/py/test_trust_drive.py`. It extracts the loader line and pinned sha from `skills/feature-flow/SKILL.md` (as the skill test does), builds a two-ticket fixture repo (`helpers.Repo`, with a `commands.md` whose commands use the interpreter running the test, as `tests/py/test_fixture_drive.py` does), and drives it only through the loader, passing each `TRUST` digest on to the next call and `--after-build` after each BUILD, exactly as the skill says. Point `CLAUDE_HOME`, `AGENTS_HOME` and `FEATURE_FLOW_HOME` at temp folders.

Cases, each from a fresh repo:

- Untampered: resolve each ticket, save `REVIEW: PASS` replies for both passes, and reach `DONE`.
- (a) a builder commit that makes `check_code` return early → `STOP` naming `feature_flow/conductor.py`.
- (b) the builder resolves 01 and writes `phase=` into `flow-f.state` → `STOP` naming the state file, and no `BUILD` for 02 is ever printed.
- (c) the builder's committed test script, run by the plan's `Test:` command, edits `feature_flow/conductor.py` during `next` → `STOP flow code changed during next`.
- A new `.py` file in `feature_flow/`, and an edited guide, role, skill and state file → each a `STOP` naming it.
- A planted `.pyc` for an edited `conductor.py` (source unchanged) is not run.
- No STOP for a new `__pycache__` file or the review-reply file.

Then run the full suites. This ticket proves the map's bar; if a case fails, fix the code in the ticket that owns it and say so in the Answer.

## Not in this ticket

- A real Claude Code, Codex or Windows agent run: out of scope (no Codex from the cloud; Windows runs the unit tests in CI).

## Done when

- `python3 -m unittest discover -s tests/py -p "test_trust_drive.py"` prints `OK`.
- `python3 -m unittest discover -s tests/py -p "test_fixture_drive.py"` prints `OK`.
- `python3 -m unittest discover -s tests/py` prints `OK` and `bash tests/run.sh` exits 0.

```check
$ python3 -m unittest discover -s tests/py -p "test_trust_drive.py"
prints OK
$ python3 -m unittest discover -s tests/py -p "test_fixture_drive.py"
prints OK
$ python3 -m unittest discover -s tests/py
prints OK
$ bash tests/run.sh
exit 0
```

## Reference

- map.md § Destination (the bar)
- `tests/py/test_fixture_drive.py`, `tests/py/test_review_pass.py`, `tests/py/helpers.py`
- learnings.md (the repros)

## Answer

Work started at 25e464a4e73713263ae552e4e95f6b1fa1dca49f. Test first: no.

**Built**

- `tests/py/test_trust_drive.py` (new, 11 tests). It takes the loader line from `skills/feature-flow/SKILL.md` with `loader_line` and `SKILLS`, imported from `test_skill_trust.py`. In the command it puts the quoted `sys.executable` in place of `python3` and the quoted fixture `scripts/flow-trust.py` path in place of `<S>/flow-trust.py`, then runs it through `feature_flow.gate.shell`, as `LoaderRun.run_loader` does. The fixture is a `helpers.Repo` with two tickets and a copy of the runner. It also gets the installed layout: `.feature-flow/guides/`, `.feature-flow/agents/`, `.claude/agents/ticket-builder.md` and `.claude/skills/feature-flow/`. Its `commands.md` has Build and Smoke as `"<python>" -c "pass"` and Test as `"<python>" t.py`, with a harmless committed `t.py`. `CLAUDE_HOME`, `AGENTS_HOME` and `FEATURE_FLOW_HOME` point at temp folders. Every call keeps the `TRUST` digest and passes it as `FLOW_TRUST` on the next call (`new` only on the first call). It passes `FLOW_SESSION` and `FLOW_INVOKE=/feature-flow`, and adds `--after-build <ticket> <sha>` from the BUILD line on the `next` after each BUILD. A review is `next` (REVIEW), then `prompt`, then the reply saved to `.feature-flow/state/flow-review-f.txt`, then `verdict` on that file.
- No production code changed. Every case passed against the code from tickets 01 to 07, so no earlier ticket needed a fix. `scripts/flow-trust.py` is unchanged and the pinned sha stays as it was.

**Proof**

- `python3 -m unittest discover -s tests/py -p "test_trust_drive.py"`: `Ran 11 tests in 21.308s` / `OK`. The cases, each in a fresh repo:
  - Untampered: start, BUILD 01, resolve, then spec and quality REVIEW with `prompt` (holds `(spec pass)` / `(quality pass)`) and `REVIEW: PASS` verdicts (`OK`), then BUILD 02 and the same again. The last `next` prints exactly one line starting `DONE f is complete`.
  - (a): a builder commit puts `return` right after the `check_code` docstring (inserted on bytes, keeping the file's own line ending), and the tree is clean after it. The next call STOPs with `STOP flow files changed since the last step:`, names `feature_flow/conductor.py`, prints no TRUST and no BUILD, REVIEW or DONE.
  - (b): 01 is resolved, then `phase=` is appended to `flow-f.state`. The next call STOPs and names the state file. A retry with the same digest and `--after-build` STOPs again, and neither call prints a `BUILD` line or `02-b.md`.
  - (c): the builder commits a `t.py` that appends to `feature_flow/conductor.py`. The gate's Test command runs it during `next`, and the test checks that the conductor bytes changed, so `t.py` really ran. The first line is exactly `STOP flow code changed during next: feature_flow/conductor.py`, and no TRUST is printed.
  - New `feature_flow/extra.py`, edited `.feature-flow/guides/build.md`, edited `.claude/agents/ticket-builder.md`, edited `.claude/skills/feature-flow/SKILL.md`, a line appended to `flow-f.state`: each STOPs, and the STOP line names that path.
  - Planted .pyc: after `start`, a TIMESTAMP .pyc is compiled from a conductor.py that prints `BXILD` instead of `BUILD`, with the same mtime and size. The source is then put back byte for byte. The drive's `next` prints exactly `BUILD plans/f/tasks/01-a.md 01 <head>`. As a control, the same conductor run directly as `flow.py f next` prints `BXILD ...`, so the plant was real.
  - No STOP: a new `feature_flow/__pycache__/junk.cpython-99.pyc` plus the review-reply file, then `next` prints TRUST and `REVIEW ... 01`. The untampered drive also writes the reply file four times and never STOPs.
- `python3 -m unittest discover -s tests/py -p "test_fixture_drive.py"`: `Ran 2 tests in 1.692s` / `OK`.
- `python3 -m unittest discover -s tests/py`: `Ran 361 tests in 195.920s` / `OK`, rc 0. `bash tests/run.sh`: `465 passed, 0 failed`, rc 0. Smoke command: exit 0.
- No skip, `.only(` or expectedFailure in the new file (grep: no hits). No platform branch: only `gate.shell` picks the shell. Hashed files are edited as bytes.

**Decisions**

- Each tamper happens where a builder would make it: during the build, before or with its commit. So every STOP is on the `next --after-build` call the skill makes, and the ticket has no `Floor:` line. This is the path where a flow-edit build could otherwise slip through.
- The fixture installs the real guides, roles and skill under `.feature-flow/` and `.claude/`. That way `prompt` works, the drive is the skill's full REVIEW -> prompt -> verdict loop, and the edited guide, role and skill are files the runner really hashes.
- The planted .pyc forges the BUILD line instead of `start`'s OK, so the check sits inside the drive. `test_trust_runner.py` already covers the `start` form.
- Shared setup: one `Drive` base class, with a fresh repo per test, as the ticket asks. The file runs in about 21 s.

**Shortcuts taken**

- none

**For later tickets**

- The bar in map.md § Destination is met. The README's Protected paragraph (ticket 07) matches what this file proves, so nothing there changes.
