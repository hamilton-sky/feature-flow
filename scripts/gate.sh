#!/bin/bash
# usage: bash scripts/gate.sh <feature>
# runs the Build, Test and Lint commands from plans/<feature>/commands.md in that order and
# stops at the first one that fails. empty values and placeholders in angle brackets are skipped.
# the commands run from the current directory and must exit non zero on failure.
# exit 0 everything passed or nothing to run, 1 a command failed, 2 usage error.

set -uo pipefail

FEATURE="${1:-}"
if [ -z "$FEATURE" ]; then
  echo "usage: bash scripts/gate.sh <feature>" >&2
  exit 2
fi

FILE="${FLOW_DIR:-plans}/$FEATURE/commands.md"
if [ ! -f "$FILE" ]; then
  echo "gate: no commands.md for $FEATURE, nothing to run"
  exit 0
fi

ran=0
for key in Build Test Lint; do
  cmd="$(awk -v k="$key" '$0 ~ "^" k ":" { sub("^" k ":[ \t]*", ""); gsub(/`/, ""); print; exit }' "$FILE")"
  case "$cmd" in
    "" | "<"*) continue ;;
  esac
  ran=$((ran + 1))
  out="$(mktemp)"
  echo "gate: $key: $cmd"
  if ! bash -c "$cmd" > "$out" 2>&1; then
    echo "gate: $key failed. the last lines of its output:"
    tail -40 "$out"
    rm -f -- "$out"
    exit 1
  fi
  rm -f -- "$out"
done

if [ "$ran" -gt 0 ]; then
  echo "gate: $ran command(s) passed"
else
  echo "gate: no commands defined, nothing to run"
fi
