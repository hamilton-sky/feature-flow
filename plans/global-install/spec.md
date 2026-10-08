# global-install — Spec

## Problem

`feature-flow install --user` puts only the skills and the four roles in `~/.claude` and `~/.agents`. The conductor (`scripts/flow.py` and its siblings), the guides and the Python package (`feature_flow/`) are still copied into every repo (`scripts/`, `.feature-flow/guides`, `.feature-flow/feature_flow`), so the skill alone cannot run the flow in a repo that has no install. A user who wants feature-flow everywhere must install it repo by repo; one who wants it in a single repo has no clean way to say so.

## Goal and the bar

A user chooses per user: `feature-flow install --user` once for every repo, or `feature-flow install <repo>` for one repo. After a user install, `/feature-flow` (Claude Code) and `$feature-flow` (Codex) work in any git repo with no per-repo files. A repo's own install, when present, wins.

The bar: in a fresh git repo with no feature-flow files, after `HOME=<tmp> feature-flow install --user`, `python3 $HOME/.feature-flow/scripts/flow.py demo start` run from that repo prints the same first line as `python3 scripts/flow.py demo start` does in a repo install. `feature-flow uninstall --user` then leaves the home folder without feature-flow files. `python3 -m unittest discover -s tests/py` and `bash tests/run.sh` pass.

## Scope

In: `install --user` writes the conductor, guides, roles and package under `~/.feature-flow/`; the Claude and Codex skills pick the repo's conductor when it has one, else the home one; hash record and upgrade rules for the home folder; `uninstall --user` removes it; the code-hash tripwire covers the home conductor; README; version 0.4.0.
Not in scope: any change to ticket or plan formats; planner, reviewer and builder behaviour; a real Windows or Codex agent run; a server or daemon; removing the per-repo install (it stays and wins).

## Design

Layout of the home install (the same shape `scripts/flow.py` already searches: `here.parent/feature_flow`):

    ~/.feature-flow/
    ├── scripts/        flow.py, flow-status.py, flow-view.py, gate.py, floor-guard.py, flow-view.html
    ├── guides/         the guides and templates
    ├── agents/         the four role files (what prompts.find_file reads)
    ├── feature_flow/   the Python package
    └── feature-flow.sha256   hash record, paths relative to ~/.feature-flow

`FEATURE_FLOW_HOME` overrides the folder, like `CLAUDE_HOME` and `AGENTS_HOME` do for the skill folders.

    repo has scripts/flow.py ?
      yes ──► python3 scripts/flow.py ...                 (repo wins)
      no  ──► python3 ~/.feature-flow/scripts/flow.py ... (or $FEATURE_FLOW_HOME)
    both:  state, plans, tickets stay in the repo (.feature-flow/state/, plans/)

State stays in the repo for free: the conductor finds the repo from the working directory (`git.toplevel()`), and only reads its own code from beside `flow.py`. The tripwire already hashes the running conductor's files (`codehash._files` uses the running package and the `scripts` folder it was given, and falls back to absolute paths for files outside the repo), so it covers the home conductor without a code change; ticket 04 proves it with a test.

### Decisions

- **Where the conductor lives** — options: A) `~/.feature-flow/` with the same shape as a repo install; B) inside `~/.claude` (Claude only). Chosen: A. Why: both Claude and Codex need it, and `flow.py` already finds `feature_flow/` beside `scripts/`. Rejected: B.
- **How the skill finds the conductor** — options: A) a short rule in SKILL.md (repo `scripts/flow.py` first, else the home path); B) a `feature-flow` command on PATH. Chosen: A (the brief's assumption). Why: no PATH setup, and `uvx` runs leave nothing on PATH. Rejected: B.
- **What `--user` means** — options: A) `--user` becomes the global install, no repo files written; B) a new flag such as `--global` beside the old `--user`. Chosen: A (the brief's assumption). Why: `uninstall --user` already means this. Consequence: `--user` no longer writes into a repo; a target argument given with `--user` is ignored and the first output line names where it installs.
- **Subagent prompts** — the guides say `python3 scripts/flow-status.py ...`, and a subagent gets only the guide text. When the conductor runs from a scripts folder other than `./scripts`, `prompts` rewrites `python3 scripts/` to the absolute folder in the guide text it hands out. Rejected: editing every guide to say "the conductor's folder" (many files, and repo installs would lose their plain text). The SKILL rule covers the orchestrating session itself.
- **Codex roles** — a user install writes the raw roles to `~/.feature-flow/agents/` only (the conductor builds prompts from them); the `.agents/flow-roles/` copy stays a repo-install feature. The Codex skill checks `.agents/flow-roles/` in the repo, else `~/.feature-flow/agents/`.
- **Upgrade rules** — same as today: a file that still holds its recorded (or a released) hash is updated, an edited one is kept and named, `--force` replaces it. The record is `feature-flow.sha256` in `~/.feature-flow/`, the same name `~/.claude` and `~/.agents` use.

## Migration and compatibility

A repo install is untouched and wins. A user who ran the old `install --user` keeps their skills; running the new one adds `~/.feature-flow/`. Repo files written earlier stay until `feature-flow uninstall` in that repo.

## Risks

- Home folder not writable or `HOME` unset — the installer reports the OSError (existing handler in `install.main`).
- A stale home conductor older than the skill — the skill and the conductor are installed together by one command; `--force` and a re-install fix a mismatch.
