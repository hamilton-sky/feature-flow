#!/bin/bash
# runs two tickets through the real claude on a throwaway project, review included.
# this spends money: each ticket costs at least two sessions.
# usage: RUN_REAL=1 [FLOW_MAX_BUDGET_USD=2] bash tests/smoke-real.sh

set -euo pipefail

if [ "${RUN_REAL:-}" != "1" ]; then
  echo "this spends money. set RUN_REAL=1 to run it." >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
RUNLOG="$(mktemp)"
trap 'rm -rf -- "${TMP:?}" "${RUNLOG:?}"' EXIT
cd "$TMP"

mkdir -p plans/hello/tasks
bash "$ROOT/install.sh" "$TMP" > /dev/null
printf '__pycache__/\n*.pyc\n' > .gitignore

cat > plans/hello/spec.md << 'EOF'
# Hello - Spec

## Goal and the bar
A tiny greeter. The bar: `python3 hello.py Ada` prints `Hello, Ada!`.
EOF

cat > plans/hello/map.md << 'EOF'
# Map: hello

## Destination
`hello.py` greets by name.

**The bar.** `python3 hello.py Ada` prints `Hello, Ada!`.

## Decisions so far

## Open questions
EOF

cat > plans/hello/commands.md << 'EOF'
# Commands: hello

Build: `python3 -m compileall -q .`
Test: `python3 -m unittest test_hello`
Smoke: `python3 -m compileall -q .`
Run: `python3 hello.py Ada`
EOF

cat > plans/hello/learnings.md << 'EOF'
# Learnings: hello

Append one or two lines, newest last, tagged with your ticket number. Never edit or delete
another line.

- (NN) <what you found, and what to do about it>
EOF

cat > plans/hello/tasks/01-greet-function.md << 'EOF'
# Add the greet function

Type: task
Status: open
Blocked by: —
Test first: yes

Create `hello.py` in the repo root with a function `greet(name)` that returns `Hello, <name>!`, and `test_hello.py` with a unittest for it.

## Not in this ticket

- The command line entry point (ticket 02).

## Done when

- `python3 -m unittest test_hello` exits 0 and prints OK.
- `python3 -c "from hello import greet; assert greet('Ada') == 'Hello, Ada!'"` exits 0.

## Reference

- spec.md

## Answer

EOF

cat > plans/hello/tasks/02-command-line.md << 'EOF'
# Add the command line entry point

Type: task
Status: open
Blocked by: 01
Test first: no

Make `python3 hello.py <name>` print the greeting, using `greet`.

## Not in this ticket

- Any option parsing beyond one positional name.

## Done when

- `python3 hello.py Ada` prints exactly `Hello, Ada!`.
- `python3 -m unittest test_hello` still exits 0.

## Reference

- spec.md

## Answer

EOF

git init -q
git config user.email smoke@example.com
git config user.name smoke
git add -A
git commit -qm init

FLOW_MAX_BUDGET_USD="${FLOW_MAX_BUDGET_USD:-2}" FLOW_MAX_TOTAL_USD="${FLOW_MAX_TOTAL_USD:-12}" bash scripts/auto-flow.sh hello 2>&1 | tee "$RUNLOG"

fails=0
check() { if eval "$2" > /dev/null 2>&1; then echo "  ok    $1"; else echo "  FAIL  $1"; fails=$((fails + 1)); fi; }
echo "checks"
check "the bar holds" '[ "$(python3 hello.py Ada)" = "Hello, Ada!" ]'
check "both tickets are resolved" 'bash scripts/flow-status.sh hello --next; [ $? -eq 10 ]'
check "the tree is clean" '[ -z "$(git status --porcelain)" ]'
check "ticket 01 has a Proof section" 'grep -q "Proof" plans/hello/tasks/01-greet-function.md'
check "a test file exists" '[ -f test_hello.py ]'
check "the gate ran the real commands after each ticket" '[ "$(grep -c "gate: 2 command(s) passed" "$RUNLOG")" -ge 2 ]'
check "the agents were used" 'grep -q "builder agent ticket-builder, reviewer agent ticket-reviewer" "$RUNLOG"'
check "ticket 02 has a Built section" 'grep -q "Built" plans/hello/tasks/02-command-line.md'
check "the floor guard never objected, so no false alarm on legitimate edits" '! grep -q "floor guard sent" "$RUNLOG"'
check "commands.md was never modified after the plan" '[ "$(git log --format=%H -- plans/hello/commands.md | wc -l | tr -d " ")" = 1 ]'
if command -v jq > /dev/null 2>&1; then
  check "the cost log has a line for every session" '[ "$(wc -l < .git/flow-cost-hello.log)" -ge 4 ]'
  check "the run printed its total cost" 'grep -q "cost this run" "$RUNLOG"'
fi
echo
git log --oneline
[ "$fails" -eq 0 ]
