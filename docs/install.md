# Installing feature-flow

[← README](../README.md) · [Docs index](README.md)

Every way to install feature-flow, what the installer writes, how to remove it, and how to upgrade. The [README](../README.md#quick-start) has the short version.

## From PyPI

The package is [`feature-flow-cli`](https://pypi.org/project/feature-flow-cli/). Install it once as a tool with [uv](https://docs.astral.sh/uv/) (or pipx), and the `feature-flow` command is on your PATH:

```bash
uv tool install feature-flow-cli          # or: pipx install feature-flow-cli
feature-flow install --user               # every repo, Claude Code (add --agent codex or --agent all)
feature-flow install /path/to/your/repo   # or one repo, with the files committed into it
```

To run the installer once without installing the tool:

```bash
uvx feature-flow-cli install /path/to/your/repo --agent all   # or: pipx run feature-flow-cli install ...
```

The package puts a `feature-flow` command on your PATH with `install`, `uninstall`, `status <feature>`, `view <feature>`, `reset <feature>`, `report <feature>`, `eval <feature>`, `import <folder> <feature>` and `brainstorm-page <feature>`. It installs the same files, byte for byte, as `install.py` from a clone.

## From a clone

You need `git` and `python3` (3.9 or later, standard library only), and Claude Code or Codex. No `bash` or `awk` is needed to run feature-flow: every script is Python. On Windows use `python` where this page says `python3`.

```bash
git clone https://github.com/hamilton-sky/feature-flow.git
cd feature-flow

python3 install.py /path/to/your/repo                  # for Claude Code
python3 install.py /path/to/your/repo --agent codex    # for Codex
python3 install.py /path/to/your/repo --agent all      # both, side by side

# `bash install.sh ...` still works on Linux and macOS: it only runs install.py
```

## As a Claude Code plugin

As a Claude Code plugin, with nothing written into your repo (this repo is its own marketplace):

```
/plugin marketplace add hamilton-sky/feature-flow
/plugin install feature-flow@feature-flow
```

The plugin carries the skills, the roles (named `feature-flow:ticket-builder` and so on), the conductor, the scripts and the guides, and the skill runs the conductor from the plugin's folder. A repo with its own install still uses that one. Claude Code cloud sessions (claude.ai/code) do not install plugins, so for them install into the repo and commit `.claude/`, `scripts/` and `.feature-flow/` as below. The plugin path is new and has not had a real run yet.

## Two ways to install

- `feature-flow install --user`: once, for every repo. Skills and roles go to `~/.claude` / `~/.agents`, the conductor, guides and package to `~/.feature-flow/`. `FEATURE_FLOW_HOME` moves that folder. No repo files are written.
- `feature-flow install <repo>`: one repo. When a repo has its own copy, that copy wins over the user install.

## What the installer does

| | Claude Code (`--agent claude`, the default) | Codex (`--agent codex`) |
|---|---|---|
| The skill goes to | `<repo>/.claude/skills/` (`--user`: `~/.claude/skills/`) | `<repo>/.agents/skills/` (`--user`: `~/.agents/skills/`) |
| Roles go to | `<repo>/.claude/agents/` | `<repo>/.agents/flow-roles/`, put in front of each subagent's prompt |
| Scripts go to | `<repo>/scripts/` | `<repo>/scripts/` |
| Guides, roles and the conductor go to | `<repo>/.feature-flow/` | `<repo>/.feature-flow/` |

Next to the `feature-flow` skill it installs `architect-review` and `automation-design`. The installer never deletes anything. A file that already exists and differs is kept and reported; `--force` replaces it. `--dry-run` shows what would change and writes nothing. `CLAUDE_HOME` and `AGENTS_HOME` move the user folders. With `--user` the skill and roles go to the user folders, and the scripts, guides, conductor and package go to `~/.feature-flow/` (`FEATURE_FLOW_HOME` moves it); nothing is written into a repo.

The Claude Code skill is `skills/feature-flow/`. The Codex skill is written by hand in `adapters/codex/feature-flow/`, with an `agents/openai.yaml` that sets `allow_implicit_invocation: false`, so it runs only when you name it. The steps are the same; only the way a subagent is started differs. Your own `AGENTS.md` and `CLAUDE.md` are never touched.

## Committing or hiding the install

The installer lists what it wrote in `.feature-flow/installed.txt`, with each file's hash in `.feature-flow/installed.sha256`. Commit those files (`git add --pathspec-from-file=.feature-flow/installed.txt`); until you do, the flow does not count them as uncommitted changes. Installing a newer version over an older one updates every file nobody edited since it was installed, and keeps (and names) the ones you changed; `--force` replaces those too.

To keep the install out of git, so only your plans and tickets get committed, install with `--private`. It lists the installed files in `.git/info/exclude`, which git reads like `.gitignore` but never commits, and later installs keep that list up to date. If you already committed the install, it prints the `git rm --cached` command that untracks it and keeps the files. Every clone then needs its own install.

## Uninstalling

To remove it, run `feature-flow uninstall` (or `uvx feature-flow-cli uninstall`) in the repo. It removes exactly the files listed in `.feature-flow/installed.txt`, and only while they still hold the bytes the installer wrote: a file you edited is kept and named, and `--force` removes it too. It also drops the `--private` block from `.git/info/exclude`. Your `plans/`, your tickets and the run logs in `.feature-flow/state/` are never touched. `--dry-run` shows what would go. If you installed with `--user`, `feature-flow uninstall --user` removes the personal copy in `~/.claude` and `~/.agents`, and `~/.feature-flow`, the same way (the repo's own install is separate and needs its own `uninstall`).

## Upgrading

Earlier versions had seven skills and an unattended loop. The five flow skills are gone, and `/feature-flow` replaces them:

- `plan-feature` → `/feature-flow <feature>` before a plan exists.
- `/next-phase` and `/review-ticket` → `/feature-flow <feature>`, which runs a builder and a fresh reviewer subagent for every ticket.
- `show-flow` → `/feature-flow <feature> show`.
- `/run-flow` and `scripts/auto-flow.sh` → `/feature-flow <feature> auto`, with a `HANDOFF` every few tickets. There is no cost log any more.

The installer never deletes the old skill folders, but it names any it finds. Delete them from `.claude/skills/` or `.agents/skills/` yourself.

**Between versions, upgrade between features, not in the middle of a run.** The skill pins the sha256 of `scripts/flow-trust.py`, so a session started with the old skill stops with `flow-trust.py does not match this skill` once the new runner is installed. Finish the feature (or reach a `HANDOFF`), install the new version, commit it, and start the next session. Plans keep working across versions: a ticket with no `Level:` line keeps the pre-0.9.0 review rules, a plan with no `Touches:` lines runs one ticket at a time, and a plan with no `Acceptance:` line runs without a tester. [docs/releases.md](releases.md) lists what changed in each version.
