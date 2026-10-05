#!/bin/bash
# usage: bash install.sh [target-repo] [--agent claude|codex|all] [--user] [--force] [--dry-run]
# copies the skills, agents and scripts into a repo so the flow works there.
#   --agent claude (default)
#     skills  go to <target>/.claude/skills/   (or ~/.claude/skills/ with --user)
#     agents  go to <target>/.claude/agents/   (or ~/.claude/agents/ with --user)
#   --agent codex: the same skills are rewritten for Codex when they are installed
#     skills  go to <target>/.agents/skills/   (or ~/.agents/skills/ with --user), with an agents/openai.yaml each
#     roles   go to <target>/.agents/flow-roles/ (always: the loop and the review command read them from the repo)
#   --agent all does both.
#   scripts go to <target>/scripts/          (always: the skills call them from the repo)
# a file that already exists and differs is kept and reported, unless --force is given.
# nothing is ever deleted. CLAUDE_HOME overrides ~/.claude and AGENTS_HOME overrides ~/.agents for --user.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET=""
AGENT="claude"
USER_LEVEL=0
FORCE=0
DRY=0

usage() {
  sed -n '2,13p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
  case "$1" in
    --agent)
      if [ $# -lt 2 ]; then
        echo "--agent needs a value: claude, codex or all" >&2
        usage >&2
        exit 2
      fi
      AGENT="$2"
      shift
      ;;
    --agent=*) AGENT="${1#--agent=}" ;;
    --user) USER_LEVEL=1 ;;
    --force) FORCE=1 ;;
    --dry-run) DRY=1 ;;
    -h | --help)
      usage
      exit 0
      ;;
    -*)
      echo "unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *) TARGET="$1" ;;
  esac
  shift
done

case "$AGENT" in
  claude | codex | all) ;;
  *)
    echo "unknown agent: $AGENT (use claude, codex or all)" >&2
    exit 2
    ;;
esac

TARGET="${TARGET:-.}"
if [ ! -d "$TARGET" ]; then
  echo "no such directory: $TARGET" >&2
  exit 2
fi
TARGET="$(cd "$TARGET" && pwd)"

if [ "$USER_LEVEL" = 1 ]; then
  CLAUDE_DIR="${CLAUDE_HOME:-$HOME/.claude}"
  AGENTS_DIR="${AGENTS_HOME:-$HOME/.agents}"
else
  CLAUDE_DIR="$TARGET/.claude"
  AGENTS_DIR="$TARGET/.agents"
fi

ADDED=0
UPDATED=0
SAME=0
KEPT=0
GENERATED=""
AGENT_NOTE=""
[ "$AGENT" = claude ] || AGENT_NOTE=" ($AGENT)"
trap '[ -z "$GENERATED" ] || rm -f -- "${GENERATED:?}"' EXIT

# one file: add it, replace it (--force), leave it alone (same) or keep the user's version
place() {
  local file="$1" out="$2"
  if [ ! -e "$out" ]; then
    echo "  add     $out"
    ADDED=$((ADDED + 1))
    [ "$DRY" = 1 ] || { mkdir -p "$(dirname "$out")" && cp -p "$file" "$out"; }
  elif cmp -s "$file" "$out"; then
    SAME=$((SAME + 1))
  elif [ "$FORCE" = 1 ]; then
    echo "  update  $out"
    UPDATED=$((UPDATED + 1))
    [ "$DRY" = 1 ] || cp -p "$file" "$out"
  else
    echo "  kept    $out (differs from this version, use --force to replace it)"
    KEPT=$((KEPT + 1))
  fi
}

copy_tree() {
  local src="$1" dest="$2" file rel
  [ -d "$src" ] || return 0
  while IFS= read -r file; do
    rel="${file#"$src"/}"
    place "$file" "$dest/$rel"
  done < <(find "$src" -type f ! -name '.DS_Store' | sort)
}

# run the Codex transform on one file and place the result
generate() { # kind source destination
  [ -n "$GENERATED" ] || GENERATED="$(mktemp)"
  awk -v emit="$1" -v skills="$SKILL_NAMES" -f "$HERE/adapters/codex/skill.awk" "$2" > "$GENERATED"
  chmod 644 "$GENERATED"
  place "$GENERATED" "$3"
}

install_codex() {
  local dir name file rel
  SKILL_NAMES=""
  for dir in "$HERE"/skills/*; do
    [ -f "$dir/SKILL.md" ] || continue
    SKILL_NAMES="$SKILL_NAMES $(basename "$dir")"
  done
  for dir in "$HERE"/skills/*; do
    [ -f "$dir/SKILL.md" ] || continue
    name="$(basename "$dir")"
    while IFS= read -r file; do
      rel="${file#"$dir"/}"
      if [ "$rel" = "SKILL.md" ]; then
        generate skill "$file" "$AGENTS_DIR/skills/$name/SKILL.md"
        generate yaml "$file" "$AGENTS_DIR/skills/$name/agents/openai.yaml"
      else
        place "$file" "$AGENTS_DIR/skills/$name/$rel"
      fi
    done < <(find "$dir" -type f ! -name '.DS_Store' | sort)
  done
  for file in "$HERE"/agents/*.md; do
    [ -f "$file" ] || continue
    generate role "$file" "$TARGET/.agents/flow-roles/$(basename "$file")"
  done
}

[ "$DRY" = 0 ] || echo "dry run: nothing will be written"
echo "installing into $TARGET${AGENT_NOTE}"
if [ "$AGENT" = claude ] || [ "$AGENT" = all ]; then
  copy_tree "$HERE/skills" "$CLAUDE_DIR/skills"
  copy_tree "$HERE/agents" "$CLAUDE_DIR/agents"
fi
if [ "$AGENT" = codex ] || [ "$AGENT" = all ]; then
  install_codex
fi
copy_tree "$HERE/scripts" "$TARGET/scripts"

echo
VERB="added"
[ "$DRY" = 0 ] || VERB="would add"
echo "$VERB $ADDED, updated $UPDATED, already current $SAME, kept $KEPT"

if [ "$DRY" = 0 ]; then
  git -C "$TARGET" rev-parse --git-dir > /dev/null 2>&1 || echo "note: $TARGET is not a git repository, and the loop needs one"
  command -v jq > /dev/null 2>&1 || echo "note: install jq to get the cost log"
  if [ "$AGENT" = claude ] || [ "$AGENT" = all ]; then
    echo "next: /plan-feature <feature-name> in Claude Code"
  fi
  if [ "$AGENT" = codex ] || [ "$AGENT" = all ]; then
    echo "next: \$plan-feature <feature-name> in Codex"
  fi
fi
