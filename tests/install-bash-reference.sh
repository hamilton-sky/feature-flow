#!/bin/bash
# usage: bash install.sh [target-repo] [--agent claude|codex|all] [--user] [--force] [--dry-run]
# copies the feature-flow skill, its roles, scripts and guides into a repo so the flow works there.
#   --agent claude (default)
#     skills  go to <target>/.claude/skills/   (or ~/.claude/skills/ with --user)
#     agents  go to <target>/.claude/agents/   (or ~/.claude/agents/ with --user)
#   --agent codex: the Codex skill from adapters/codex/, the other skills with a Codex header
#     skills  go to <target>/.agents/skills/   (or ~/.agents/skills/ with --user)
#     roles   go to <target>/.agents/flow-roles/ (always: the skill reads them from the repo)
#   --agent all does both.
#   scripts go to <target>/scripts/ and guides, roles and the Python package to <target>/.feature-flow/
#     (always: the skill and scripts/flow.py read them from the repo)
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
  sed -n '2,14p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

# the skills this installs
SKILLS="feature-flow architect-review automation-design"

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
  done < <(find "$src" -type f ! -name '.DS_Store' ! -name '*.pyc' ! -path '*/__pycache__/*' | sort)
}

# write a transformed copy of one file to a temp file and place that
place_filtered() { # filter source destination
  [ -n "$GENERATED" ] || GENERATED="$(mktemp)"
  "$1" "$2" > "$GENERATED"
  chmod 644 "$GENERATED"
  place "$GENERATED" "$3"
}

# a Codex skill header holds only the name and a quoted description; the body is left as it is
codex_header() {
  awk '
    NR == 1 && $0 == "---" { fm = 1; print; next }
    fm && $0 == "---" { fm = 0; print; next }
    fm && /^name:/ { print; next }
    fm && /^description:/ {
      d = substr($0, 13); sub(/^[ \t]+/, "", d); sub(/[ \t]+$/, "", d)
      e = ""
      for (i = 1; i <= length(d); i++) { c = substr(d, i, 1); if (c == "\\" || c == "\"") e = e "\\"; e = e c }
      print "description: \"" e "\""; next
    }
    fm { next }
    { print }
  ' "$1"
}

# a role file without its frontmatter, so it can go in front of a prompt
role_body() {
  awk 'NR == 1 && $0 == "---" { fm = 1; next } fm && $0 == "---" { fm = 0; skip = 1; next } fm { next } skip && $0 == "" { next } { skip = 0; print }' "$1"
}

# a skill folder this installer does not own but that drives the flow (it runs the ticket scripts or
# ends a review with a verdict) is left from an earlier version: named once, never deleted
report_leftovers() {
  local dir path name found=""
  for dir in "$@"; do
    for path in "$dir"/*/SKILL.md; do
      [ -f "$path" ] || continue
      name="$(basename "$(dirname "$path")")"
      case " $SKILLS " in *" $name "*) continue ;; esac
      grep -qE 'scripts/flow-status\.sh|REVIEW: PASS' "$path" && found="$found $name"
    done
  done
  [ -z "$found" ] || echo "note: left from an earlier feature-flow, no longer installed:$found. delete them, /feature-flow replaces them"
}

install_codex() {
  local name file
  copy_tree "$HERE/adapters/codex/feature-flow" "$AGENTS_DIR/skills/feature-flow"
  for name in $SKILLS; do
    [ "$name" != feature-flow ] || continue
    while IFS= read -r file; do
      if [ "$file" = "$HERE/skills/$name/SKILL.md" ]; then
        place_filtered codex_header "$file" "$AGENTS_DIR/skills/$name/SKILL.md"
      else
        place "$file" "$AGENTS_DIR/skills/$name/${file#"$HERE/skills/$name"/}"
      fi
    done < <(find "$HERE/skills/$name" -type f ! -name '.DS_Store' | sort)
  done
  for file in "$HERE"/agents/*.md; do
    [ -f "$file" ] || continue
    place_filtered role_body "$file" "$TARGET/.agents/flow-roles/$(basename "$file")"
  done
}

[ "$DRY" = 0 ] || echo "dry run: nothing will be written"
echo "installing into $TARGET${AGENT_NOTE}"
LEFT_DIRS=()
if [ "$AGENT" = claude ] || [ "$AGENT" = all ]; then
  for name in $SKILLS; do copy_tree "$HERE/skills/$name" "$CLAUDE_DIR/skills/$name"; done
  copy_tree "$HERE/agents" "$CLAUDE_DIR/agents"
  LEFT_DIRS+=("$CLAUDE_DIR/skills")
fi
if [ "$AGENT" = codex ] || [ "$AGENT" = all ]; then
  install_codex
  LEFT_DIRS+=("$AGENTS_DIR/skills")
fi
copy_tree "$HERE/scripts" "$TARGET/scripts"
copy_tree "$HERE/guides" "$TARGET/.feature-flow/guides"
copy_tree "$HERE/agents" "$TARGET/.feature-flow/agents"
copy_tree "$HERE/feature_flow" "$TARGET/.feature-flow/feature_flow"

echo
VERB="added"
[ "$DRY" = 0 ] || VERB="would add"
echo "$VERB $ADDED, updated $UPDATED, already current $SAME, kept $KEPT"
report_leftovers "${LEFT_DIRS[@]}"

if [ "$DRY" = 0 ]; then
  git -C "$TARGET" rev-parse --git-dir > /dev/null 2>&1 || echo "note: $TARGET is not a git repository, and the flow needs one"
  command -v python3 > /dev/null 2>&1 || echo "note: install python3 (3.9 or later): scripts/flow.py needs it"
  if [ "$AGENT" = claude ] || [ "$AGENT" = all ]; then
    echo "next: /feature-flow <feature-name> in Claude Code"
  fi
  if [ "$AGENT" = codex ] || [ "$AGENT" = all ]; then
    echo "next: \$feature-flow <feature-name> in Codex"
  fi
fi
