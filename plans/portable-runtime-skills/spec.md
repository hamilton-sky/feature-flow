# Portable runtime skills — Spec

## Problem

Feature Flow keeps one set of skill files today, but those files are authored for Claude Code. The Codex installer rewrites exact phrases, command syntax, frontmatter and role instructions with `adapters/codex/skill.awk`. That works and is heavily tested, but a harmless wording change can bypass a replacement, runtime support is spread across installer logic, and the repository cannot package the skills as one portable OpenAI plugin without exposing Claude-only behavior.

The unattended Codex path also relies on prose review verdicts, discovers missing CLI capabilities only after work starts, reviews in a read-only sandbox that rejects tests which write files, and commits every change with `git add -A` without first rejecting likely secrets.

## Goal and the bar

Each skill has one canonical definition and one explicit runtime-support declaration. Thin Claude and Codex adapters render the files each environment needs. Common instructions are provider-neutral; genuinely runtime-specific skills such as `drive-flow` stay specific and are installed only where supported. The Codex loop fails early on an incompatible CLI, uses a structured review result when available, reviews in a disposable writable worktree, and validates files before committing. A generated portable plugin contains only Codex-supported skills.

The bar: `bash tests/run.sh` exits 0, reports no failed checks, validates both generated installations and the portable plugin, and exercises the Codex preflight, structured-review fallback, isolated reviewer and commit-safety paths without calling a paid model.

## Stories

### Maintain a skill once

**As a** Feature Flow maintainer, **I want** one canonical skill definition with declared runtime support, **so that** Claude and Codex behavior cannot drift through duplicated edits.

- [ ] Shared instructions and resources have one source.
- [ ] Runtime-specific metadata and invocation text are added by explicit adapters, not arbitrary sentence replacements.
- [ ] A runtime-specific skill is omitted from unsupported installations and packages.

### Install for the current environment

**As a** Claude or Codex user, **I want** the installer to render the correct files for my agent, **so that** invocation syntax, metadata, roles and safety constraints match the environment.

- [ ] Claude installs preserve slash commands, Claude frontmatter and named agents.
- [ ] Codex installs preserve dollar mentions, `agents/openai.yaml`, role prompts and explicit-invocation policy.
- [ ] Installing both environments side by side remains idempotent.

### Run Codex unattended safely

**As a** Codex user, **I want** unsupported CLI versions and unsafe output to stop before a bad commit, **so that** long runs fail predictably and reviews can execute realistic tests.

- [ ] Required Codex capabilities are checked before the first session.
- [ ] Structured review output is normalized to the existing pass/fail contract.
- [ ] Reviewer commands may write only inside a disposable worktree.
- [ ] Likely secrets and invalid diffs are rejected before staging.

### Distribute the workflow

**As a** maintainer, **I want** a validated portable plugin artifact, **so that** the supported skills can be installed without copying implementation-specific source files.

- [ ] The artifact has a valid portable manifest and only supported skills.
- [ ] Offline CI validates installation, packaging and compatibility.
- [ ] Optional real-agent evaluations cover activation without making ordinary CI paid or flaky.

## Scope

In: canonical skill metadata; Claude and Codex rendering; provider-neutral common instructions; supporting references and runtime fragments; installer compatibility; Codex CLI preflight; structured review output; disposable review worktrees; commit-path validation; behavioral skill evaluations; portable plugin packaging; compatibility documentation; CI validation.

Not in scope:
- Implementing `plans/in-session-mode`. Parts of it are prerequisites: its conductor (`flow-step.sh`, its tickets 02 and 03) before the review-path work here, and its `drive-flow` skill and Codex exclusion (its tickets 04 and 05) before the skill-architecture work here. Its paid acceptance run is not a prerequisite.
- A Codex same-session/subagent mode; it needs a separate probe and plan.
- An MCP server, remote service, authentication or UI; this is a local skills-and-scripts package.
- Automatic publication to the public plugin directory; credentials, identity verification and review stay a release operation.
- Replacing Bash and AWK with another runtime; the existing portability target remains Bash 3.2 plus standard AWK.
- Paid model evaluations on every pull request; real-agent evaluation remains opt-in.

## Happy path

1. The maintainer edits one canonical `SKILL.md`, its resources and its runtime metadata.
2. `install.sh --agent claude` renders Claude frontmatter, slash invocations and named-agent files into `.claude/`.
3. `install.sh --agent codex` renders OpenAI metadata, dollar invocations and role files into `.agents/`, excluding unsupported skills.
4. `scripts/package-plugin.sh` builds a clean portable plugin from the same Codex-supported sources.
5. `FLOW_AGENT=codex bash scripts/auto-flow.sh <feature>` checks CLI capabilities, builds tickets, reviews each committed state in a disposable worktree, normalizes the verdict, validates changed paths and commits only after the checks pass.
6. Offline CI installs both variants, validates the package and runs every deterministic workflow check.

## Edge cases

| Trigger | Expected behaviour | Handled in ticket |
|---|---|---|
| The in-session `drive-flow` skill or its Codex exclusion is missing | Workers stop before changing the skill architecture and report the prerequisite | 01 |
| The in-session conductor is missing | Workers stop before changing the review path and report the prerequisite | 07 |
| A skill supports Claude only | Claude installs it; Codex and the portable plugin omit it with an explicit message | 03, 04, 10 |
| Shared instructions contain a runtime-specific command | Parity checks fail and identify the skill and text | 05 |
| Codex lacks a required flag | The loop exits before the first model session with the missing capability | 06 |
| Structured output is unavailable or `jq` is absent | The existing exact text verdict remains the supported fallback | 07 |
| A review command writes caches or generated files | It succeeds inside the disposable worktree and leaves the main tree unchanged | 08 |
| The plan folder or the installed skills and roles are git ignored or untracked | They are copied into the review worktree read only, so the reviewer finds the ticket, the skill and its role | 08 |
| Worktree creation or cleanup fails | The run stops with the path and recovery command; it never silently reviews in the main tree | 08 |
| A builder creates a likely secret | The commit is refused and the suspicious path is printed | 09 |
| An optional activation evaluation has no credentials | It skips with an explicit message while offline CI remains green | 15 |
| Plugin packaging sees an unsupported skill | The skill is omitted and the package report names it | 10 |

## Design

```
 canonical skill + runtime metadata + shared resources
                         │
             ┌───────────┴───────────┐
             ▼                       ▼
      [Claude renderer]        [Codex renderer]
             │                       │
       .claude/skills          .agents/skills
       .claude/agents          .agents/flow-roles
                                     │
                                     ▼
                              [plugin packager]
                                     │
                           portable plugin artifact

 Codex loop ─► preflight ─► build ─► validate ─► commit
                                      │
                                      ▼
                            disposable review worktree
                                      │
                             JSON or text verdict
                                      │
                             normalized PASS / FAIL
```

### Decisions

- **Cross-plan order** — options: run both plans concurrently, port first, or finish the interactive plan first. Chosen: depend on the parts that matter, not on the whole plan. The skill-architecture tickets (01 onward) wait for the in-session `drive-flow` skill and its Codex exclusion; the review-path tickets (07, 08) wait for the in-session conductor, whose policy mirrors `review()`; the preflight (06) and commit safety (09) touch neither and start at once. Why: the in-session plan ends with a manual, paid run that nothing here needs, and the Codex safety fixes should not wait on it.
- **Two tracks** — the Codex loop hardening (06, 07, 08, 09, 17) and the portable skills (01 to 05, 10, 11, 13 to 16) share only the acceptance ticket 12. They can be worked in parallel, and may later become two plans.
- **Canonical content** — options: keep Claude as canonical, keep Codex as canonical, or use shared instructions plus runtime metadata and fragments. Chosen: shared instructions plus explicit runtime material. Why: neither environment becomes an accidental source of truth for the other.
- **Migration order** — options: neutralize the Markdown first or build both renderers first. Chosen: build renderers first, then neutralize. Why: every intermediate ticket keeps current installations and tests working.
- **Runtime support** — options: separate skip lists or one matrix beside the skills. Chosen: one non-executable, AWK-readable runtime declaration per skill. Why: installers, tests and packaging consume the same fact without sourcing code.
- **Review contract** — options: replace the text verdict everywhere or normalize structured Codex output behind the existing contract. Chosen: normalize behind the existing contract. Why: the interactive `flow-step.sh` plan and Claude review path continue to use exact `REVIEW: PASS` or `REVIEW: FAIL` lines.
- **Writable review isolation** — options: keep read-only, allow writes in the main tree, or use a disposable worktree. Chosen: disposable worktree, for the headless reviewer of both agents (Claude's has no sandbox at all today). Why: tests may write files, while reviewer changes must never reach the builder checkout. A worktree holds only tracked files, so the plan folder and the installed skills and roles are copied in when they are ignored or untracked.
- **Outside facts** — the Codex help output, the official skill layout and the portable plugin layout are not in this repository. The ticket that first relies on each records it in `references.md` with its source and date, and later tickets read it from there.
- **Plugin output** — options: expose the repository root directly or generate a filtered artifact. Chosen: generate a filtered artifact. Why: the repository contains Claude-only skills and development files that do not belong in the Codex/OpenAI package.
- **CLI compatibility** — options: pin one version string or test capabilities. Chosen: test capabilities. Why: flags, not a version label, determine whether the loop can run.

## Interfaces

Each skill gets a non-executable metadata file consumed as data, never sourced by the shell. It records the argument hint, implicit-invocation policy and supported runtimes. The exact syntax is fixed by the first ticket and must be parseable by Bash 3.2 plus standard AWK.

The adapters accept a source skill directory and emit a complete runtime skill directory. Claude output may add Claude-only frontmatter. Codex output may add `agents/openai.yaml`. Runtime fragments are explicit files or structured renderer inputs; renderers do not search for prose sentences to replace.

The Codex preflight reports each missing executable or flag and exits nonzero before `run_codex` starts a session.

Structured Codex reviews use a checked-in JSON Schema with a verdict enum, per-check results and findings. The loop converts that object into the existing textual review report and final verdict line. Without structured-output support, it uses the current text response contract.

The plugin packager writes to a caller-selected output directory, refuses a nonempty destination unless explicitly told to replace its own generated output, and supports a check mode that builds in a temporary directory and validates without dirtying the repository.

## Migration and compatibility

The skill-architecture tickets start only after the in-session `drive-flow` skill and its Codex exclusion are resolved, and the review-path tickets only after the in-session conductor is. The `drive-flow` skill remains Claude-only. Its support declaration replaces the Codex-specific skip list as the single source of truth, while preserving the installed behavior introduced by that plan.

`flow-step.sh` keeps its text verdict interface. Codex JSON output is an implementation detail of the headless loop and is normalized before shared policy sees it. Changes to shared retry, verdict or safety policy require parity coverage for both `auto-flow.sh` and `flow-step.sh`.

The command-line interface of `install.sh` remains compatible. Existing generated files are kept unless `--force` is supplied, as today. The package build is additive and does not make the current installer obsolete.

## Risks

- Neutral wording may weaken a skill's precise runtime behavior — golden installation tests and behavioral evaluations compare the rendered results.
- Adapter changes may create a circular build dependency — renderers land while the legacy source still works, then the source conversion removes legacy assumptions.
- Disposable Git worktrees can be left behind after interruption — cleanup uses traps and errors include a manual recovery command.
- A worktree lacks ignored files — the plan folder, skills and roles are copied in, and a fixture with an ignored `plans/` proves it.
- The structured-output flag may not exist in the installed Codex — the preflight finds out, and the text contract stays the fallback.
- Commit safety covers only the Codex loop — Claude builders commit for themselves inside `next-phase` and `drive-flow`, and the README says so.
- Secret detection can raise false positives — it targets untracked high-risk filenames, prints the reason and documents a narrow explicit override rather than silently staging.
- The interactive and headless state machines can drift — CI covers their shared verdict and stop contracts, while runtime-specific behavior stays separate.
- Plugin rules can change — packaging validates the generated artifact and keeps manifest generation isolated from the canonical skills.
