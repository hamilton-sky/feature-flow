# Document the same-session mode in the README

Type: task
Status: open
Blocked by: 04, 05
Test first: no

Add a "Same-session mode" section to `README.md`, after "Running unattended", and keep it honest about what is enforced and what is not.

It says: how to run it (`/drive-flow csv-export`, or `/drive-flow csv-export auto` to ask nothing, Claude Code only, the two agents must be installed); what happens per ticket (conductor line, subagent, gate and floor guard run by the script, reviewer subagent, verdict); a short table of `/run-flow` against `/drive-flow` (where the work runs, who owns the order, limits and cost log, visibility, context growth); what the script enforces (the order, the limits, the state in `.git/flow-step-<feature>.state` that survives a closed session) and what it cannot (the session can still ignore a line, but the script judges the build, the gate and the floor guard from the repo; the review verdict is relayed by the session and the script cannot prove a reviewer wrote it, so this mode trusts the session for the review where the headless loop does not); and that Codex has no same-session mode yet.

Add a row to the "What is tested" table for "Claude Code, same-session (`/drive-flow`)" with the status "Not yet tested with a real run". The acceptance ticket changes that row. Add `drive-flow` to the skills table and to the quick start table of invocations (Codex column: not available). Update the "N checks" number in the Tests section to the number `bash tests/run.sh` prints.

## Not in this ticket

- The real run and the tested row's final wording: ticket 07.
- Any change to the scripts or skills.

## Done when

- `grep -c '/drive-flow' README.md` prints at least `4`, and `grep -n 'Same-session mode' README.md` prints one heading line.
- `grep -c 'Not yet tested with a real run' README.md` prints `1`.
- `grep -ci 'relayed by the session' README.md` prints at least `1`.
- `n=$(bash tests/run.sh | tail -1 | awk '{print $1}'); grep -c "^$n checks" README.md` prints `1`.
- `grep -cE 'Same-session|drive-flow' README.md` is at least `6`, and every markdown link or anchor the section adds resolves to a heading that exists in the file.

## Reference

- README.md (the "Running unattended" and "What is tested" sections)
- plans/in-session-mode/spec.md § Design, Scope
- skills/drive-flow/SKILL.md from ticket 04

## Answer

