#!/bin/bash
# usage: bash scripts/auto-flow.sh <feature>
# one fresh claude session per ticket, then a floor guard and an independent review,
# until every ticket is resolved or the run gets stuck.
# the ticket file is the judge: a session only counts if it leaves its ticket resolved.
# env: FLOW_DIR, FLOW_TICKETS (ticket location), FLOW_ALLOWED_TOOLS, FLOW_MAX_RETRIES,
#      FLOW_REVIEW (on or off, default on), FLOW_MAX_REVIEW_ROUNDS (default 3),
#      FLOW_MODEL, FLOW_REVIEW_MODEL (model for building, model for reviewing),
#      FLOW_MAX_TURNS, FLOW_MAX_BUDGET_USD (limits per session), FLOW_MAX_TOTAL_USD (limit per run),
#      FLOW_SMOKE (command run before every ticket, default: the Smoke line of commands.md),
#      FLOW_COST (on or off, default on: log cost per session, needs jq),
#      FLOW_GATE (on or off, default on: run Build, Test and Lint from commands.md after every ticket),
#      FLOW_AGENTS (auto, on or off, default auto: use the ticket-builder and ticket-reviewer agents when installed),
#      FLOW_CLAUDE_ARGS (extra flags for every session), FLOW_SLEEP (seconds between tickets)

set -euo pipefail

FEATURE="${1:?usage: bash scripts/auto-flow.sh <feature>}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATUS="$HERE/flow-status.sh"
GUARD="$HERE/floor-guard.sh"
GATE="$HERE/gate.sh"
COMMANDS="${FLOW_DIR:-plans}/$FEATURE/commands.md"
MAX_RETRIES="${FLOW_MAX_RETRIES:-2}"
MAX_ROUNDS="${FLOW_MAX_REVIEW_ROUNDS:-3}"
REVIEW="${FLOW_REVIEW:-on}"
MODEL="${FLOW_MODEL:-}"
REVIEW_MODEL="${FLOW_REVIEW_MODEL:-}"
MAX_TOTAL="${FLOW_MAX_TOTAL_USD:-}"
ALLOWED_TOOLS="${FLOW_ALLOWED_TOOLS:-Edit,Write,Read,Glob,Grep,Bash}"
REVIEW_TOOLS="Read,Glob,Grep,Bash"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

HAVE_JQ=0
TOTAL_COST=0
COSTED=0
NAME=""

fail() {
  echo -e "${RED}$1${NC}" >&2
  exit 1
}

summary() {
  if [ "$HAVE_JQ" = 1 ] && [ "$COSTED" -gt 0 ]; then
    echo -e "${GREEN}cost this run: \$$TOTAL_COST over $COSTED session(s). log: $COST_LOG${NC}"
  fi
  return 0
}

ticket_state() {
  awk 'FNR <= 20 && /^Status:/ { sub(/^Status:[ \t]*/, ""); print tolower($0); exit }' "$1"
}

set_open() {
  local file="$1" tmp="$1.tmp"
  awk 'FNR <= 20 && !done && /^Status:/ { print "Status: open"; done = 1; next } { print }' "$file" > "$tmp"
  mv "$tmp" "$file"
}

record_cost() {
  local raw="$1" role="$2" line cost
  line="$(jq -r '[(.num_turns // 0), (.total_cost_usd // 0), (.is_error // false), (.subtype // "")] | @csv' "$raw" 2> /dev/null)" || return 0
  [ -n "$line" ] || return 0
  cost="$(printf '%s' "$line" | cut -d, -f2)"
  printf '%s,%s,%s,%s\n' "$(date +%H:%M:%S)" "${NAME:-setup}" "$role" "$line" >> "$COST_LOG"
  TOTAL_COST="$(awk -v a="$TOTAL_COST" -v b="$cost" 'BEGIN { printf "%.4f", a + b }')"
  COSTED=$((COSTED + 1))
  if [ -n "$MAX_TOTAL" ] && awk -v a="$TOTAL_COST" -v m="$MAX_TOTAL" 'BEGIN { exit !(a > m) }'; then
    fail "total cost cap reached: \$$TOTAL_COST is over FLOW_MAX_TOTAL_USD=$MAX_TOTAL"
  fi
}

pick_agent() {
  local name file_project file_user
  AGENT_NAME=""
  case "$1" in
    build) name="ticket-builder" ;;
    review) name="ticket-reviewer" ;;
    *) return 0 ;;
  esac
  file_project=".claude/agents/$name.md"
  file_user="$HOME/.claude/agents/$name.md"
  case "${FLOW_AGENTS:-auto}" in
    off) return 0 ;;
    on)
      [ -f "$file_project" ] || [ -f "$file_user" ] || fail "FLOW_AGENTS=on but the agent $name is not installed"
      AGENT_NAME="$name"
      ;;
    *)
      if [ -f "$file_project" ] || [ -f "$file_user" ]; then AGENT_NAME="$name"; fi
      ;;
  esac
}

run_claude() {
  local prompt="$1" tools="$2" model="$3" role="$4" rc=0 raw text extra
  local args=(-p "$prompt" --allowedTools "$tools")
  pick_agent "$role"
  [ -z "$AGENT_NAME" ] || args+=(--agent "$AGENT_NAME")
  [ -z "$model" ] || args+=(--model "$model")
  [ -z "${FLOW_MAX_TURNS:-}" ] || args+=(--max-turns "$FLOW_MAX_TURNS")
  [ -z "${FLOW_MAX_BUDGET_USD:-}" ] || args+=(--max-budget-usd "$FLOW_MAX_BUDGET_USD")
  if [ -n "${FLOW_CLAUDE_ARGS:-}" ]; then
    read -r -a extra <<< "$FLOW_CLAUDE_ARGS"
    args+=("${extra[@]}")
  fi
  if [ "$HAVE_JQ" = 1 ]; then
    raw="$(mktemp)"
    claude "${args[@]}" --output-format json > "$raw" < /dev/null || rc=$?
    text="$(jq -r '.result // empty' "$raw" 2> /dev/null || true)"
    if [ -n "$text" ]; then
      printf '%s\n' "$text"
    else
      echo "[no result text: $(jq -r '.subtype // "unknown"' "$raw" 2> /dev/null || echo unreadable)]"
    fi
    record_cost "$raw" "$role"
    rm -f -- "$raw"
  else
    claude "${args[@]}" < /dev/null || rc=$?
  fi
  return "$rc"
}

count_run() {
  RUNS=$((RUNS + 1))
  [ "$RUNS" -le "$RUN_LIMIT" ] || fail "run limit of $RUN_LIMIT sessions reached, stopping"
}

smoke_command() {
  local cmd="${FLOW_SMOKE:-}"
  if [ -z "$cmd" ] && [ -f "$COMMANDS" ]; then
    cmd="$(awk '/^Smoke:/ { sub(/^Smoke:[ \t]*/, ""); gsub(/`/, ""); print; exit }' "$COMMANDS")"
  fi
  case "$cmd" in
    "" | "<"*) return 0 ;;
  esac
  printf '%s' "$cmd"
}

run_smoke() {
  local cmd out
  cmd="$(smoke_command)"
  [ -n "$cmd" ] || return 0
  out="$(mktemp)"
  echo -e "${YELLOW}  smoke: $cmd${NC}"
  if ! bash -c "$cmd" > "$out" 2>&1; then
    tail -20 "$out" >&2
    rm -f -- "$out"
    fail "smoke test failed before $1: the base is already broken. fix it first. command: $cmd"
  fi
  rm -f -- "$out"
}

implement() {
  local attempt=0 state
  while [ "$attempt" -lt "$MAX_RETRIES" ]; do
    attempt=$((attempt + 1))
    count_run
    run_claude "/next-phase $FEATURE auto" "$ALLOWED_TOOLS" "$MODEL" build || echo -e "${YELLOW}  claude exited non zero on attempt $attempt${NC}"
    state="$(ticket_state "$TICKET")"
    case "${state%% *}" in
      resolved | done | closed) return 0 ;;
      claimed | in-progress) set_open "$TICKET" ;;
    esac
    echo -e "${YELLOW}  $NAME is not resolved after attempt $attempt${NC}"
  done
  fail "$NAME is still unresolved after $MAX_RETRIES attempt(s)"
}

review() {
  local out attempt=0 verdict=""
  out="$(mktemp)"
  while [ "$attempt" -lt "$MAX_RETRIES" ]; do
    attempt=$((attempt + 1))
    count_run
    run_claude "/review-ticket $FEATURE $NUM $BASE" "$REVIEW_TOOLS" "$REVIEW_MODEL" review > "$out" || true
    cat "$out"
    verdict="$(grep -E '^REVIEW: (PASS|FAIL)[[:space:]]*$' "$out" | tail -1 || true)"
    [ -z "$verdict" ] || break
  done
  if ! git diff --quiet || ! git diff --cached --quiet; then
    rm -f -- "$out"
    fail "the reviewer changed tracked files, which a reviewer must never do"
  fi
  case "$verdict" in
    "REVIEW: PASS")
      rm -f -- "$out"
      return 0
      ;;
    "REVIEW: FAIL")
      FINDINGS="$(head -120 "$out")"
      rm -f -- "$out"
      return 1
      ;;
  esac
  rm -f -- "$out"
  fail "no review verdict for $NAME after $MAX_RETRIES attempt(s)"
}

send_back() {
  local source="$1" round="$2"
  {
    echo
    echo "## Review findings (round $round, $source)"
    echo
    printf '%s\n' "$FINDINGS"
  } >> "$TICKET"
  set_open "$TICKET"
  if git add -- "$TICKET" 2> /dev/null; then
    git commit -q -m "chore($FEATURE): $NUM review findings, round $round" || true
  fi
}

command -v claude > /dev/null 2>&1 || fail "claude CLI not found"
git rev-parse --git-dir > /dev/null 2>&1 || fail "not inside a git repository"
[ -f "$STATUS" ] || fail "missing $STATUS"
[ -f "$GUARD" ] || fail "missing $GUARD"
GATE_ON=0
if [ "${FLOW_GATE:-on}" != "off" ]; then
  [ -f "$GATE" ] || fail "missing $GATE"
  GATE_ON=1
fi

if [ "${FLOW_COST:-on}" != "off" ]; then
  if command -v jq > /dev/null 2>&1; then
    HAVE_JQ=1
  else
    echo "note: install jq to log the cost of every session"
  fi
fi
COST_LOG="$(git rev-parse --absolute-git-dir)/flow-cost-$FEATURE.log"
trap summary EXIT

bash "$STATUS" "$FEATURE" --check || fail "ticket check failed, fix the tickets first"
[ -z "$(git status --porcelain)" ] || fail "working tree is not clean, commit or stash first"

TOTAL=$(bash "$STATUS" "$FEATURE" --counts | sed -n 's/.*total=\([0-9]*\).*/\1/p')
RUN_LIMIT=$((TOTAL * 2 * MAX_RETRIES * (MAX_ROUNDS + 1) + 1))
RUNS=0
DONE_TICKETS=0

pick_agent build
BUILD_AGENT="${AGENT_NAME:-none}"
pick_agent review
REVIEW_AGENT="${AGENT_NAME:-none}"
echo -e "${GREEN}auto-flow: $FEATURE ($TOTAL tickets, review $REVIEW, gate $([ "$GATE_ON" = 1 ] && echo on || echo off), builder agent $BUILD_AGENT, reviewer agent $REVIEW_AGENT)${NC}"

while true; do
  rc=0
  TICKET=$(bash "$STATUS" "$FEATURE" --next 2> /dev/null) || rc=$?
  case $rc in
    0) ;;
    10)
      echo -e "${GREEN}$FEATURE is complete: $DONE_TICKETS ticket(s) resolved in this run${NC}"
      exit 0
      ;;
    11) fail "stuck: unfinished tickets remain but none is ready. run: bash scripts/flow-status.sh $FEATURE" ;;
    *) fail "flow-status.sh failed with exit code $rc" ;;
  esac

  NAME="$(basename "$TICKET" .md)"
  NUM="${NAME%%-*}"
  BASE="$(git rev-parse HEAD)"
  echo -e "${YELLOW}ticket $NAME${NC}"
  run_smoke "$NAME"

  round=0
  while true; do
    implement
    [ -z "$(git status --porcelain)" ] || fail "working tree is dirty after $NAME, it should have been committed"

    FINDINGS=""
    SOURCE=""
    if [ "$GATE_ON" = 1 ] && ! gate_out="$(bash "$GATE" "$FEATURE" 2>&1)"; then
      FINDINGS="$gate_out"
      SOURCE="gate"
    elif ! guard_out="$(bash "$GUARD" "$FEATURE" "$NUM" "$BASE" 2>&1)"; then
      FINDINGS="$guard_out"
      SOURCE="floor guard"
    elif [ "$REVIEW" != "off" ] && ! review; then
      SOURCE="independent review"
    fi

    if [ "$GATE_ON" = 1 ] && [ "$SOURCE" != "gate" ]; then
      echo -e "${YELLOW}  $(printf '%s' "$gate_out" | tail -1)${NC}"
    fi

    [ -n "$FINDINGS" ] || break

    round=$((round + 1))
    [ "$round" -le "$MAX_ROUNDS" ] || fail "$NAME still fails the $SOURCE after $MAX_ROUNDS round(s)"
    echo -e "${YELLOW}  $SOURCE sent $NAME back (round $round)${NC}"
    send_back "$SOURCE" "$round"
  done

  DONE_TICKETS=$((DONE_TICKETS + 1))
  echo -e "${GREEN}  $NAME resolved${NC}"
  sleep "${FLOW_SLEEP:-2}"
done
