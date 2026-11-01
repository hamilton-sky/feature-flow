# Contributing

[← README](../README.md) · [Docs index](README.md)

How feature-flow is tested, how to try it by hand, how to run the tests, and how a release reaches PyPI.

## What is tested

| Path | Tested |
|---|---|
| Real repos | Used by its author on several repos besides its own. In a field run on a separate application repo (two features), all 7 issues the reviews caught were confirmed real. That run shaped 0.19.0 to 0.23.0: read only reviewers, agent-driven runs, follow-ups, batches, and the single level 3 review (the 19 separate spec reviews it ran caught nothing the quality review missed). |
| Claude Code | The offline suite, and **one real run of the bar** on the demo project: the two-ticket demo in two `/feature-flow hello auto` sessions with one `HANDOFF` between them, each ticket built by a builder subagent and passed by a reviewer subagent, with all 16 acceptance checks ok. It used about 23k output tokens and 2M cached input tokens on Sonnet. |
| Codex | The install, offline, in CI on Linux and macOS. A probe in the Codex app showed that subagents with separate contexts work and that a reviewer's verdict reaches the session. The full flow is **not yet tested with a real run**. |
| Claude Code on the web | Documented, untested: commit `.claude/`, `scripts/` and `.feature-flow/` into the repo, because cloud sessions read only the repo's `.claude/`. |
| Copilot, Gemini CLI, Cursor | Not tested. Some read `.agents/skills`, so `--agent codex` may already work. |

## Trying it by hand

```bash
bash tests/smoke-real.sh --prepare /tmp/hello-try                    # the demo project, for Claude Code, no model is called
FLOW_AGENT=codex bash tests/smoke-real.sh --prepare /tmp/hello-codex # the same, for Codex
```

Then `cd` into it, start the agent and type `/feature-flow hello` (Codex: `$feature-flow hello`).

## Tests

```bash
bash tests/run.sh
python3 -m unittest discover -s tests/py
python3 -m unittest discover -s packages/forkboard/tests            # Forkboard, the brainstorm page
(cd packages/forkboard/tests/browser && npm install && npm test)    # the page in Chromium
```

Offline and free: no model is called. The suite covers the conductor's every answer and how a run stops, sessions, handoff and takeover, a `.git` the agent cannot write, the gate, the floor guard, plan protection, the prompts and guides, both skills, the installer for both agents, the graph page and its data, the Done when checks, the test-first check, the two reviews and the debugging guide on a send-back, and the acceptance harness. `tests/run.sh` also drives a prepared demo with no model through both checks and both reviews. The page's layout and replay logic are also tested under Node (`tests/viewer-logic.test.js`, skipped when Node is absent). `.github/workflows/tests.yml` runs it on every push to `main` and every pull request, on Ubuntu and on macOS. A fourth job runs the Python unit tests on Windows, including a fixture drive that takes a two-ticket plan through `python scripts/flow.py f start` and `next` to `BUILD` and then `REVIEW`, with `FLOW_TRUSTED=1` set as the runner sets it. `tests/run.sh` itself is a bash harness and does not run on Windows. Windows is tested this way only: no real agent run has been done there.

A `package` job builds the wheel and the sdist and runs `tests/package_smoke.py` on Ubuntu (Python 3.9 and the latest), macOS and Windows: it installs the wheel in a fresh virtual environment, runs `feature-flow install`, and checks that the repo gets the same files as from `install.py` in a clone. Run it locally with `python3 -m pip install build && python3 tests/package_smoke.py`.

Two jobs test Forkboard ([packages/forkboard/](../packages/forkboard/)) on its own: its unit tests and a build-and-install smoke test on Ubuntu, macOS and Windows, and the page driven in Chromium through Playwright (the diagram editor, no sideways scroll at phone width, and a live-page save that clashes with someone else's, reloads and saves again).

`RUN_REAL=1 bash tests/smoke-real.sh --interactive` is the acceptance run with Claude Code. It runs real sessions on the demo project and spends money, which is why it asks for `RUN_REAL=1`.

## Releasing to PyPI

The package is [`feature-flow-cli`](https://pypi.org/project/feature-flow-cli/) (the shorter `feature-flow` is likely refused by PyPI as too close to the existing `featureflow`). Its version is `__version__` in `feature_flow/__init__.py`.

To release, bump `__version__`, merge it to `main`, then tag that commit and push the tag:

```bash
git tag v0.1.1 && git push origin v0.1.1
```

`.github/workflows/release.yml` checks that the tag matches `__version__`, builds the wheel and the sdist, runs `tests/package_smoke.py` on them and publishes them to PyPI. PyPI trusts the workflow as a trusted publisher (owner `hamilton-sky`, repository `feature-flow`, workflow `release.yml`, environment `pypi`), so no token is stored. PyPI never accepts the same version twice.
