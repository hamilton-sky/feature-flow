# Make both skills call the conductor only through the pinned runner

Type: task
Floor: allow flow-edit
Status: resolved
Blocked by: 03, 04, 05
Test first: yes

Edit `skills/feature-flow/SKILL.md` (Claude) and `adapters/codex/feature-flow/SKILL.md` (Codex). Both carry, byte for byte, the same loader line from spec.md § Interfaces with the sha256 of `scripts/flow-trust.py` (LF-normalised bytes) filled in, and the same short rules:

- Every conductor command (`start`, `next`, `prompt`, `verdict`, `reset`, `plan-prompt`, `plan-review-prompt`, `plan-accept`) runs as `FLOW_TRUST=<digest> <other FLOW_* vars> <loader> <S>/flow-trust.py <sha> <feature> <command>`, where `<S>` is the folder of the `flow.py` the skill picks (global-install's rule: the repo's `scripts/`, else the home one). Show the full command once, as the existing example does.
- The first line of the output is `TRUST <digest>`: keep it, pass it as `FLOW_TRUST` on the next call, and treat the rest as the conductor's output (for `prompt`, the subagent's prompt is everything after that line). Use `FLOW_TRUST=new` only on this session's first conductor call, or with an old-style handoff.
- If you no longer have the last `TRUST` digest, stop and say so. Never guess it.
- On the `next` right after a `BUILD <ticket> <NN> <sha>`, add `--after-build <ticket> <sha>` before the feature. If the output has a `FLOW-EDIT <paths>` line, carry on; without `auto`, first tell the user which flow files changed.
- On a `STOP` from the runner or the loader (`flow-trust.py does not match this skill`: say to reinstall feature-flow), report it, show the `python3 <S>/flow-status.py <feature>` table, and stop. Never fix it and carry on.
- `HANDOFF` now has a third field: tell the user to type the whole line. When the feature is followed by a 16-hex word, that word is the digest: pass it as `FLOW_TRUST` on `start`. When a resumed session gets no digest, warn that it could not check the flow's files since the last session.

Remove the now-wrong direct `python3 scripts/flow.py <feature> next` example. Keep everything else in each skill.

Add `tests/py/test_skill_trust.py`: extract the loader line and the pinned sha from both SKILL.md files; both lines are identical; the sha equals sha256 of `scripts/flow-trust.py` with CRLF turned into LF; running the extracted loader, with its leading `python3` replaced by the quoted `sys.executable` (the Windows CI job has `python`, not `python3`), (through the platform shell: `bash -c` on Linux and macOS, `cmd.exe /c` on Windows, as `feature_flow/gate.py` picks it) in a fixture repo with `FLOW_TRUST=new ... start` prints `TRUST ` then `OK `; the same with a planted `hashlib.py` in the repo root is unaffected; a runner file with one byte changed makes it print `flow-trust.py does not match this skill` and exit 1; a CRLF copy of the runner still matches; and neither SKILL.md contains `scripts/flow.py <feature> next` or `flow.py <feature> next` as a direct command.

Then refresh this repo's tracked copies so `tests/py/test_own_install.py` stays green: `python3 install.py . --agent all --force`, committing only the skill copies that changed.

## Not in this ticket

- README and `guides/build.md`: ticket 07.
- The end-to-end drive with every tamper case: ticket 08.

## Done when

- Both SKILL.md files hold the identical loader line, and its sha matches `scripts/flow-trust.py`.
- Neither SKILL.md contains a direct `python3 scripts/flow.py <feature> next` command.
- `python3 -m unittest discover -s tests/py -p "test_skill_trust.py"` prints `OK`, and so does `-p "test_own_install.py"`.
- `python3 -m unittest discover -s tests/py` prints `OK`.

```check
$ python3 -m unittest discover -s tests/py -p "test_skill_trust.py"
prints OK
$ python3 -m unittest discover -s tests/py -p "test_own_install.py"
prints OK
$ python3 -m unittest discover -s tests/py
prints OK
```

## Reference

- spec.md § Interfaces, § Happy path, § Edge cases
- `skills/feature-flow/SKILL.md`, `adapters/codex/feature-flow/SKILL.md`, `feature_flow/gate.py` (`shell`), `tests/py/test_own_install.py`

## Answer

Work started at d8ff4447d973169e092c580acdc623e265754952. Test-only commit: 2030abf (`test(trusted-checks): 06 failing test`). At that commit `test_skill_trust.py` failed all 9 tests: neither SKILL.md had a loader line ("expected one loader line, found 0"), and both still held the direct `flow.py <feature> next` example.

**Built**

- `skills/feature-flow/SKILL.md` and `adapters/codex/feature-flow/SKILL.md`: a new `## Calling the conductor` section (identical in both apart from `FLOW_INVOKE` and subagent/child agent). It has the spec's loader line with the sha256 of `scripts/flow-trust.py` (`4e033dade18143518b8694661ecd93d3ec152b559ee19e3fbcec8f09aef6b902`, LF bytes) filled in, the full command shown once, and the rules: keep the `TRUST` digest and pass it as `FLOW_TRUST`; `new` only on the session's first call or an old-style handoff; no digest means stop, never guess; `--after-build <ticket> <sha>` on the `next` after a BUILD; `FLOW-EDIT` means carry on (tell the user first without `auto`); a `STOP` first line or the loader's `flow-trust.py does not match this skill` (say reinstall) means report, show the `flow-status.py` table and stop, and never act on the conductor output that can follow an after-call STOP; the HANDOFF digest goes in as `FLOW_TRUST` on `start`, and a resume without one warns. The Plan and Before-building `start` lines now point at the runner. The BUILD bullet now says `next` with `--after-build`. The HANDOFF bullet says to type the whole line with its digest. "act on its one line" now says after `TRUST` (and any `FLOW-EDIT`). The direct `FLOW_SESSION=... python3 scripts/flow.py <feature> next` example is removed. Everything else is unchanged.
- `tests/py/test_skill_trust.py` (new, 9 tests): extracts the single loader line and pinned sha from both skills. It checks that the lines are identical and equal the spec's loader plus the sha, that the sha equals the LF sha256 of the runner, that every `flow-trust.py <sha>` in a skill uses that sha, and that there is no direct `flow.py <feature> next|prompt|verdict`. It runs the extracted line (`python3` replaced by the quoted `sys.executable`, `<S>/flow-trust.py` by the quoted fixture path) through `feature_flow.gate.shell` in a `helpers.Repo` fixture with `FLOW_TRUST=new ... f start`. Checks: `TRUST <digest>` then `OK `; a planted `hashlib.py` in the repo root is ignored; one changed byte gives exit 1 and `flow-trust.py does not match this skill` on stderr, with no TRUST; a CRLF copy still gives TRUST then OK. No test skips or branches on the platform; only `gate.shell` picks the shell.
- `.claude/skills/feature-flow/SKILL.md`, `.agents/skills/feature-flow/SKILL.md`: refreshed by `python3 install.py . --agent all --force` (it reported "updated 2"). The untracked `.feature-flow/` copies that the install also wrote were deleted, not committed (`test_own_install` forbids tracking them).

**Proof**

- Identical loader line, sha matches: `test_both_skills_hold_one_identical_loader_line`, `test_the_loader_line_is_the_one_from_the_spec` and `test_the_pinned_sha_is_the_runners_lf_sha256` pass. `grep -o "flow-trust.py <64 hex>"` over both files gives 6 hits, all `4e033dad...6b902`.
- No direct command: `grep -c "flow.py <feature> next"` gives 0 for both files. `test_no_skill_calls_the_conductor_directly` passes.
- `python3 -m unittest discover -s tests/py -p "test_skill_trust.py"`: `Ran 9 tests ... OK`. `-p "test_own_install.py"`: `Ran 2 tests ... OK`.
- `python3 -m unittest discover -s tests/py`: `Ran 350 tests in 170.184s` / `OK`, exit 0.
- `bash tests/run.sh`: `465 passed, 0 failed`, exit 0. Smoke command: exit 0.

**Decisions**

- The digest word in the HANDOFF rule is written as `<16 hex>.<16 hex>`, which is what the runner really prints (`<code>.<state>`). The ticket's "16-hex word" would not match it.
- The plan prompts (`plan-prompt`, `plan-review-prompt`) get the same "everything after the TRUST line" rule as `prompt`, because they also go through the runner.
- `<S>` stays a placeholder in both the loader line and the full example, so the loader line is byte for byte the same in both skills and the same for a repo or home install.
- The test checks the whole loader text against the spec's, not just that the two skills agree, so a drift in both copies is still caught.

**Shortcuts taken**

- none

**For later tickets**

- 07: when the runner changes, the pinned sha in both skills (and their installed copies, via `install.py . --agent all --force`) must change with it, or `test_skill_trust.py` and `test_own_install.py` fail. The README's direct form can use the loader line from the skills.
- 08: drive through the loader with `LoaderRun.run_loader` in `test_skill_trust.py` as a model (extracted line, `gate.shell`, `FLOW_TRUST` in env).

