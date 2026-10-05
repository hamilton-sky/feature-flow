#!/bin/bash
# usage: bash scripts/auto-flow.sh <feature>
# one fresh agent session per ticket, then a floor guard and an independent review,
# until every ticket is resolved or the run gets stuck.
# the ticket file is the judge: a session only counts if it leaves its ticket resolved.
# env: FLOW_AGENT (claude or codex, default claude: which CLI runs the sessions),
#      FLOW_DIR, FLOW_TICKETS (ticket location), FLOW_ALLOWED_TOOLS, FLOW_MAX_RETRIES,
#      FLOW_REVIEW (on or off, default on), FLOW_MAX_REVIEW_ROUNDS (default 3),
#      FLOW_MODEL, FLOW_REVIEW_MODEL (model for building, model for reviewing),
#      FLOW_MAX_TURNS, FLOW_MAX_BUDGET_USD (limits per session), FLOW_MAX_TOTAL_USD (limit per run),
#        these three and FLOW_ALLOWED_TOOLS are claude only: codex has no such flag and reports no dollars,
#      FLOW_SMOKE (command run before every ticket, default: the Smoke line of commands.md),
#      FLOW_COST (on or off, default on: log cost per session, needs jq),
#      FLOW_GATE (on or off, default on: run Build, Test and Lint from commands.md after every ticket),
#      FLOW_AGENTS (auto, on or off, default auto: use the ticket-builder and ticket-reviewer agents when installed;
#        for codex they are the role files in .agents/flow-roles/ that install.sh --agent codex writes),
#      FLOW_CLAUDE_ARGS, FLOW_CODEX_ARGS (extra flags for every session), FLOW_SLEEP (seconds between tickets)

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
AGENT="${FLOW_AGENT:-claude}"
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
TOKENS_IN=0
TOKENS_OUT=0
NAME=""

fail() {
  echo -e "${RED}$1${NC}" >&2
  exit 1
}

summary() {
  if [ "$HAVE_JQ" = 1 ] && [ "$COSTED" -gt 0 ]; then
    if [ "$AGENT" = codex ]; then
      echo -e "${GREEN}tokens this run: $TOKENS_IN in, $TOKENS_OUT out over $COSTED session(s), no dollar figure. log: $COST_LOG${NC}"
    else
      echo -e "${GREEN}cost this run: \$$TOTAL_COST over $COSTED session(s). log: $COST_LOG${NC}"
    fi
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

# codex reports tokens and no dollars: log the tokens, leave the dollar column at 0
record_tokens() {
  local raw="$1" role="$2" rc="$3" line tin tout
  line="$(jq -Rrn --argjson rc "$rc" '[inputs | fromjson? | select(type == "object" and .type == "turn.completed") | .usage] | [length, 0, ($rc != 0), "completed", (map(.input_tokens // 0) | add // 0), (map(.output_tokens // 0) | add // 0)] | @csv' "$raw" 2> /dev/null)" || return 0
  [ -n "$line" ] || return 0
  printf '%s,%s,%s,%s\n' "$(date +%H:%M:%S)" "${NAME:-setup}" "$role" "$line" >> "$COST_LOG"
  tin="$(printf '%s' "$line" | cut -d, -f5)"
  tout="$(printf '%s' "$line" | cut -d, -f6)"
  TOKENS_IN=$((TOKENS_IN + tin))
  TOKENS_OUT=$((TOKENS_OUT + tout))
  COSTED=$((COSTED + 1))
}

# the builder and the reviewer roles. claude runs a session as the agent (--agent). codex has no such
# flag, so its role is a text file that goes in front of the prompt.
pick_agent() {
  local name file_project file_user
  AGENT_NAME=""
  AGENT_FILE=""
  case "$1" in
    build) name="ticket-builder" ;;
    review) name="ticket-reviewer" ;;
    *) return 0 ;;
  esac
  if [ "$AGENT" = codex ]; then
    file_project=".agents/flow-roles/$name.md"
    file_user=""
  else
    file_project=".claude/agents/$name.md"
    file_user="$HOME/.claude/agents/$name.md"
  fi
  if [ -f "$file_project" ]; then
    AGENT_FILE="$file_project"
  elif [ -n "$file_user" ] && [ -f "$file_user" ]; then
    AGENT_FILE="$file_user"
  fi
  case "${FLOW_AGENTS:-auto}" in
    off) return 0 ;;
    on)
      [ -n "$AGENT_FILE" ] || fail "FLOW_AGENTS=on but the agent $name is not installed"
      AGENT_NAME="$name"
      ;;
    *)
      if [ -n "$AGENT_FILE" ]; then AGENT_NAME="$name"; fi
      ;;
  esac
}

# the prompt that starts a skill: /name in claude, $name in codex
skill_prompt() {
  if [ "$AGENT" = codex ]; then
    printf '$%s %s' "$1" "$2"
  else
    printf '/%s %s' "$1" "$2"
  fi
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

# one codex session. the builder may write the workspace (but codex keeps .git read only, so the loop
# commits for it), the reviewer may only read. the last message goes to a file and is printed from there.
run_codex() {
  local prompt="$1" model="$3" role="$4" rc=0 last events sandbox full text extra
  local args=()
  pick_agent "$role"
  case "$role" in
    review) sandbox="read-only" ;;
    *) sandbox="workspace-write" ;;
  esac
  full="$prompt"
  [ -z "$AGENT_NAME" ] || full="$(cat "$AGENT_FILE")"$'\n\n'"$prompt"
  last="$(mktemp)"
  args=(exec --sandbox "$sandbox" -o "$last")
  [ -z "$model" ] || args+=(-m "$model")
  if [ -n "${FLOW_CODEX_ARGS:-}" ]; then
    read -r -a extra <<< "$FLOW_CODEX_ARGS"
    args+=("${extra[@]}")
  fi
  if [ "$HAVE_JQ" = 1 ]; then
    events="$(mktemp)"
    codex "${args[@]}" --json "$full" > "$events" < /dev/null || rc=$?
    record_tokens "$events" "$role" "$rc"
    rm -f -- "${events:?}"
  else
    codex "${args[@]}" "$full" > /dev/null < /dev/null || rc=$?
  fi
  text="$(cat "$last" 2> /dev/null || true)"
  if [ -n "$text" ]; then
    printf '%s\n' "$text"
  else
    echo "[no result text: codex wrote no last message]"
  fi
  rm -f -- "${last:?}"
  return "$rc"
}

run_agent() {
  if [ "$AGENT" = codex ]; then
    run_codex "$@"
  else
    run_claude "$@"
  fi
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

# codex cannot write .git, so a resolved ticket is committed here, the way the builder skill would have
commit_for_agent() {
  local title
  [ "$AGENT" = codex ] || return 0
  [ -n "$(git status --porcelain)" ] || return 0
  title="$(awk 'FNR <= 5 && /^# / { sub(/^# /, ""); print; exit }' "$TICKET")"
  { git add -A && git commit -q -m "feat($FEATURE): $NUM ${title:-$NAME}"; } || fail "could not commit $NAME for codex, whose sandbox keeps .git read only"
}

implement() {
  local attempt=0 state
  while [ "$attempt" -lt "$MAX_RETRIES" ]; do
    attempt=$((attempt + 1))
    count_run
    run_agent "$(skill_prompt next-phase "$FEATURE auto")" "$ALLOWED_TOOLS" "$MODEL" build || echo -e "${YELLOW}  $AGENT exited non zero on attempt $attempt${NC}"
    state="$(ticket_state "$TICKET")"
    case "${state%% *}" in
      resolved | done | closed)
        commit_for_agent
        return 0
        ;;
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
    run_agent "$(skill_prompt review-ticket "$FEATURE $NUM $BASE")" "$REVIEW_TOOLS" "$REVIEW_MODEL" review > "$out" || true
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

case "$AGENT" in
  claude | codex) ;;
  *) fail "FLOW_AGENT must be claude or codex, not $AGENT" ;;
esac
command -v "$AGENT" > /dev/null 2>&1 || fail "$AGENT CLI not found"
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

if [ "$AGENT" = codex ]; then
  [ -z "$MAX_TOTAL" ] || echo "note: FLOW_MAX_TOTAL_USD does not apply to codex, which reports tokens and no dollars"
  [ -z "${FLOW_MAX_TURNS:-}" ] || echo "note: FLOW_MAX_TURNS is ignored: codex has no turn limit"
  [ -z "${FLOW_MAX_BUDGET_USD:-}" ] || echo "note: FLOW_MAX_BUDGET_USD is ignored: codex has no budget limit"
  [ -z "${FLOW_ALLOWED_TOOLS:-}" ] || echo "note: FLOW_ALLOWED_TOOLS is ignored: codex is limited by its sandbox, not a tool list"
  echo "note: only the run limit, the retries and the review rounds stop a runaway codex run"
fi

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
if [ "$AGENT" = codex ]; then
  echo -e "${GREEN}auto-flow: $FEATURE ($TOTAL tickets, review $REVIEW, gate $([ "$GATE_ON" = 1 ] && echo on || echo off), codex, builder role $BUILD_AGENT, reviewer role $REVIEW_AGENT)${NC}"
else
  echo -e "${GREEN}auto-flow: $FEATURE ($TOTAL tickets, review $REVIEW, gate $([ "$GATE_ON" = 1 ] && echo on || echo off), builder agent $BUILD_AGENT, reviewer agent $REVIEW_AGENT)${NC}"
fi

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
