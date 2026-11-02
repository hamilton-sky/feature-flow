# Fixing a bug

[← README](../README.md) · [Docs index](README.md)

`/feature-flow <name> fix` is the short path for one bug with one cause. It skips the brief, the planner, the plan reviewer and the brainstorm page. The checks stay the same as for any ticket: a failing regression test first, the gate, the floor guard, the footprint and a fresh reviewer.

```
/feature-flow fix-empty-export fix            find the cause, then fix it after your yes
/feature-flow fix-empty-export fix diagnose   find the cause and stop
```

The full rules the session follows are in [guides/fix.md](../guides/fix.md).

## What happens

1. **Reproduce.** The session finds a command that fails now and will pass once the bug is gone, and runs it. If it cannot make the bug happen, it says so and stops, without guessing a cause.
2. **Find the cause.** It reads the code and runs read-only commands (`git log -p`, the smallest failing case, working code to compare against), one hypothesis at a time. It changes nothing.
3. **The diagnosis.** It writes `.feature-flow/state/fix-<name>.md`: the `Repro:` command, the `Cause:`, the `Fix:`, the paths the fix will change (`Touches:`), a level, and the evidence.
4. **Your one yes.** It shows you the cause, the fix and the command: yes, edit, or diagnosis only. With `diagnose` it stops here.
5. **A plan of one ticket.** `flow-status.py <name> --fix <diagnosis>` writes `plans/<name>/`: a spec made from the diagnosis, and one ticket with `Type: fix`, `Test first: yes`, your `Touches:` and level, and a check block that runs the `Repro:` command. `commands.md` takes the command lines of the newest plan in the repo, with `Profile: normal`. When there is no other plan, the session fills in `commands.md` with you. The session lints the plan, commits it as `docs(<name>): fix plan`, and starts the build.
6. **The build.** The builder gets the debugging guide from its first attempt. It commits a regression test that fails on the bug, then the fix. The conductor proves the test failed before the fix, runs the gate, the floor guard, the footprint and the `Repro:` check, and a reviewer reads the change.

## When not to use it

- **Two causes, a fix across many parts of the code, or a choice that changes what the user gets.** The session stops and offers the usual plan (`/feature-flow <name>`, with `brainstorm` for real options).
- **A one-line edit you can check by eye.** feature-flow is more than it needs.
- **A bug in auth, tokens, permissions, money, data loss or feature-flow's own code.** Give the diagnosis `Level: 3`. The ticket then gets the level 3 review, which probes every input as a hostile caller.
