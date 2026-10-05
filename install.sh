#!/bin/bash
# usage: bash install.sh [target-repo] [--user] [--force] [--dry-run]
# copies the skills, agents and scripts into a repo so the flow works there.
#   skills  go to <target>/.claude/skills/   (or ~/.claude/skills/ with --user)
#   agents  go to <target>/.claude/agents/   (or ~/.claude/agents/ with --user)
#   scripts go to <target>/scripts/          (always: the skills call them from the repo)
# a file that already exists and differs is kept and reported, unless --force is given.
# nothing is ever deleted. CLAUDE_HOME overrides ~/.claude for --user.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET=""
USER_LEVEL=0
FORCE=0
DRY=0

usage() {
  sed -n '2,9p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

for arg in "$@"; do
  case "$arg" in
    --user) USER_LEVEL=1 ;;
    --force) FORCE=1 ;;
    --dry-run) DRY=1 ;;
    -h | --help)
      usage
      exit 0
      ;;
    -*)
      echo "unknown option: $arg" >&2
      usage >&2
      exit 2
      ;;
    *) TARGET="$arg" ;;
  esac
done

TARGET="${TARGET:-.}"
if [ ! -d "$TARGET" ]; then
  echo "no such directory: $TARGET" >&2
  exit 2
fi
TARGET="$(cd "$TARGET" && pwd)"

if [ "$USER_LEVEL" = 1 ]; then
  CLAUDE_DIR="${CLAUDE_HOME:-$HOME/.claude}"
else
  CLAUDE_DIR="$TARGET/.claude"
fi

ADDED=0
UPDATED=0
SAME=0
KEPT=0

copy_tree() {
  local src="$1" dest="$2" file rel out
  [ -d "$src" ] || return 0
  while IFS= read -r file; do
    rel="${file#"$src"/}"
    out="$dest/$rel"
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
  done < <(find "$src" -type f ! -name '.DS_Store' | sort)
}

[ "$DRY" = 0 ] || echo "dry run: nothing will be written"
echo "installing into $TARGET"
copy_tree "$HERE/skills" "$CLAUDE_DIR/skills"
copy_tree "$HERE/agents" "$CLAUDE_DIR/agents"
copy_tree "$HERE/scripts" "$TARGET/scripts"

echo
VERB="added"
[ "$DRY" = 0 ] || VERB="would add"
echo "$VERB $ADDED, updated $UPDATED, already current $SAME, kept $KEPT"

if [ "$DRY" = 0 ]; then
  git -C "$TARGET" rev-parse --git-dir > /dev/null 2>&1 || echo "note: $TARGET is not a git repository, and the loop needs one"
  command -v jq > /dev/null 2>&1 || echo "note: install jq to get the cost log"
  echo "next: /plan-feature <feature-name> in Claude Code"
fi
