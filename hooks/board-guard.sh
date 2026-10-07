#!/bin/sh
# PreToolUse guard for the ask-board agents.
#
# Claude Code runs this before every tool call in every session while the
# plugin is enabled. Only calls from an agent whose agent_type starts with
# "l3a0:board-" are checked. Every other caller, the main thread included,
# exits 0 here without starting Python.
#
# Exit 0 allows the call, and for a board agent's Grep the Python check
# prints an updatedInput that adds exclusion globs. Exit 2 blocks the call,
# in every permission mode.
# Claude Code treats any other exit code as a non-blocking error and lets the
# call through, so for a board agent every failure below turns into exit 2.

input=$(cat) || input=""

if ! printf '%s' "$input" | grep -Eq '"agent_type"[[:space:]]*:[[:space:]]*"l3a0:board-'; then
  exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ask-board guard: python3 is not installed, so board agents cannot read or search. Install python3 to convene the board." >&2
  exit 2
fi

dir=$(dirname "$0")
printf '%s' "$input" | python3 "$dir/board_guard.py"
status=$?
if [ "$status" -eq 0 ]; then
  exit 0
fi
if [ "$status" -ne 2 ]; then
  echo "ask-board guard: the check failed with status $status, so the call is blocked." >&2
fi
exit 2
