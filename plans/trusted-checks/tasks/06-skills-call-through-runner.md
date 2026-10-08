# Make both skills call the conductor only through the pinned runner

Type: task
Floor: allow flow-edit
Status: open
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
