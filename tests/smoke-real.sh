#!/bin/bash
# the demo project, two tickets, for trying the flow with a real agent.
# usage: [FLOW_AGENT=claude|codex] bash tests/smoke-real.sh --prepare DIR
#          builds the project in the empty folder DIR, installed for the agent, and stops.
#          no model is called, so it costs nothing: use it to try the skill by hand in the agent's own UI.
#        RUN_REAL=1 [FLOW_MAX_BUDGET_USD=6] [FLOW_TICKETS_PER_SESSION=1] bash tests/smoke-real.sh --interactive
#          the acceptance run of the one-skill flow, and it spends money: claude -p "/feature-flow hello auto",
#          one session after another while the flow hands off, at most three. the project folder is kept and printed.

set -euo pipefail

PREPARE=""
case "${1:-}" in
  --prepare)
    PREPARE="${2:-}"
    [ -n "$PREPARE" ] || { echo "usage: bash tests/smoke-real.sh --prepare DIR" >&2; exit 2; }
    ;;
  --interactive)
    if [ "${RUN_REAL:-}" != "1" ]; then
      echo "this spends money. set RUN_REAL=1 to run it." >&2
      exit 2
    fi
    ;;
  *)
    echo "usage: bash tests/smoke-real.sh --prepare DIR | --interactive (with RUN_REAL=1)" >&2
    exit 2
    ;;
esac

AGENT="${FLOW_AGENT:-claude}"
[ -n "$PREPARE" ] || AGENT=claude
case "$AGENT" in
  claude | codex) ;;
  *)
    echo "FLOW_AGENT must be claude or codex, not $AGENT" >&2
    exit 2
    ;;
esac

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -n "$PREPARE" ]; then
  mkdir -p "$PREPARE"
  if [ -n "$(ls -A "$PREPARE")" ]; then
    echo "$PREPARE is not empty, use a new folder" >&2
    exit 2
  fi
  TMP="$(cd "$PREPARE" && pwd)"
else
  TMP="$(mktemp -d)"
fi
cd "$TMP"

mkdir -p plans/hello/tasks
bash "$ROOT/install.sh" "$TMP" --agent "$AGENT" > /dev/null
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

```check
$ python3 -m unittest test_hello
$ python3 -c "from hello import greet; assert greet('Ada') == 'Hello, Ada!'"
```

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

```check
$ python3 hello.py Ada
prints Hello, Ada!
$ python3 -m unittest test_hello
```

## Reference

- spec.md

## Answer

EOF

git init -q
git config user.email smoke@example.com
git config user.name smoke
git add -A
git commit -qm init

if [ -n "$PREPARE" ]; then
  echo "prepared $TMP for $AGENT. no model was called."
  if [ "$AGENT" = codex ]; then
    echo "try it by hand:  cd $TMP && codex    then type:  \$feature-flow hello"
  else
    echo "try it by hand:  cd $TMP && claude   then type:  /feature-flow hello"
  fi
  exit 0
fi

# one session after another, each started the way a user would type it. the flow log in
# .feature-flow/state/, not the session's chat, says how each session ended.
export FLOW_TICKETS_PER_SESSION="${FLOW_TICKETS_PER_SESSION:-1}"
TOOLS="${FLOW_ALLOWED_TOOLS:-Agent,Task,Bash,Read,Glob,Grep,Edit,Write}"
BUDGET="${FLOW_MAX_BUDGET_USD:-6}"
ended=""
echo "project: $TMP (kept)"
for n in 1 2 3; do
  echo "session $n: claude -p \"/feature-flow hello auto\""
  claude -p "/feature-flow hello auto" --allowedTools "$TOOLS" --max-budget-usd "$BUDGET" < /dev/null || true
  ended="$(cut -d, -f3 .feature-flow/state/flow-hello.log 2> /dev/null | grep -E '^(HANDOFF|DONE|STOP)$' | tail -1 || true)"
  last="$(tail -1 .feature-flow/state/flow-hello.log 2> /dev/null | cut -d, -f3 || true)"
  if [ "$ended" != "$last" ] || [ -z "$ended" ]; then
    echo "  FAIL  session $n ended without HANDOFF, DONE or STOP"
    echo "the feature is still owned by that session. once you are sure no claude session is working in $TMP, continue with:"
    echo "  cd $TMP && FLOW_TAKEOVER=1 FLOW_TICKETS_PER_SESSION=$FLOW_TICKETS_PER_SESSION claude -p \"/feature-flow hello auto\" --allowedTools \"$TOOLS\" --max-budget-usd $BUDGET"
    exit 1
  fi
  echo "session $n ended on $ended"
  [ "$ended" = HANDOFF ] || break
done
fails=0
check() { if eval "$2" > /dev/null 2>&1; then echo "  ok    $1"; else echo "  FAIL  $1"; fails=$((fails + 1)); fi; }
has() { grep -q ",$1,$2\$" .feature-flow/state/flow-hello.log; }
echo "checks"
check "the run ended on DONE" '[ "$ended" = DONE ]'
check "the bar holds" '[ "$(python3 hello.py Ada)" = "Hello, Ada!" ]'
check "both tickets are resolved" 'python3 scripts/flow-status.py hello --next; [ $? -eq 10 ]'
check "the tree is clean" '[ -z "$(git status --porcelain)" ]'
check "each ticket landed as a commit" '[ "$(git rev-list --count HEAD)" -ge 3 ]'
for t in 01 02; do
  for e in BUILD GATE-PASS GUARD-PASS DONEWHEN-PASS REVIEW VERDICT-PASS; do check "ticket $t: the log has $e" "has $t $e"; done
done
check "ticket 01: the log has TESTFIRST-PASS" "has 01 TESTFIRST-PASS"
check "the first session handed off once, between the tickets" '[ "$(grep -c ",HANDOFF$" .feature-flow/state/flow-hello.log)" = 1 ] && [ "$(grep -n ",HANDOFF$" .feature-flow/state/flow-hello.log | cut -d: -f1)" -lt "$(grep -n ",02,BUILD$" .feature-flow/state/flow-hello.log | head -1 | cut -d: -f1)" ]'
echo
cat .feature-flow/state/flow-hello.log
git log --oneline
[ "$fails" -eq 0 ]
