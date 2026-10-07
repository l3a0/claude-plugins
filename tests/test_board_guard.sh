#!/bin/sh
# Tests for hooks/board-guard.sh. Each case feeds sample PreToolUse hook input
# on stdin and checks the exit code: 0 allows the call, 2 blocks it.
# Every case runs against a temporary HOME holding a fake brief, never the
# real one. Run from anywhere: sh tests/test_board_guard.sh

here=$(cd "$(dirname "$0")" && pwd)
guard="$here/../hooks/board-guard.sh"

# The test leaves its temporary folder in the system temp directory.
tmp=$(mktemp -d)
HOME="$tmp/home"
export HOME
unset CLAUDE_CONFIG_DIR CLAUDE_CODE_REMOTE_MEMORY_DIR
mkdir -p "$HOME/.config/board/hypotheses" "$tmp/proj/work/src" "$tmp/proj/work/.ssh" "$tmp/proj/work2"
work=$(cd "$tmp/proj/work" && pwd -P)
printf 'secret\n' > "$HOME/.config/board/hypotheses/x.md"
printf '# Company brief\n\n- Amount: $25,000\n- Normal week: 10\n' > "$HOME/.config/board/brief.md"
printf 'print(1)\n' > "$work/src/app.py"
printf 'KEY=1\n' > "$work/.env"
printf 'KEY=1\n' > "$work/.env.local"
printf 'key\n' > "$work/.ssh/id_ed25519"
printf 'x\n' > "$tmp/proj/work2/notes.md"
ln -s "$HOME/.config/board" "$work/board-link"
mem="$HOME/.claude/agent-memory"
mkdir -p "$mem/l3a0-board-cfo" "$mem/l3a0-board-risk"
printf '# Notes\n' > "$mem/l3a0-board-cfo/MEMORY.md"
printf '# Notes\n' > "$mem/l3a0-board-risk/MEMORY.md"
ln -s "$HOME/.config/board" "$mem/l3a0-board-cfo/board-link"

pass=0
fail=0

# check NAME EXPECTED_STATUS JSON
check() {
  printf '%s' "$3" | sh "$guard" 2>/dev/null
  got=$?
  if [ "$got" -eq "$2" ]; then
    pass=$((pass + 1))
    echo "ok   $1"
  else
    fail=$((fail + 1))
    echo "FAIL $1: expected $2, got $got"
  fi
}

board() {
  printf '{"session_id":"s","cwd":"%s","agent_id":"a1","agent_type":"l3a0:board-cfo","hook_event_name":"PreToolUse","tool_name":"%s","tool_input":%s}' "$work" "$1" "$2"
}

# One tool_input object, built with printf so the shell never re-parses it.
read_of() { printf '{"file_path":"%s"}' "$1"; }
grep_in() { printf '{"pattern":"Amount","path":"%s"}' "$1"; }
search() { printf '{"query":"%s"}' "$1"; }
other() { printf '{"cwd":"%s","agent_id":"a2","agent_type":"%s","tool_name":"Read","tool_input":{"file_path":"%s"}}' "$work" "$1" "$2"; }
main_thread() { printf '{"cwd":"%s","tool_name":"Read","tool_input":{"file_path":"%s"}}' "$work" "$1"; }

check "1 allow: board agent reads inside the working directory" 0 "$(board Read "$(read_of "$work/src/app.py")")"
check "2 deny: board agent reads a hypothesis file" 2 "$(board Read "$(read_of "$HOME/.config/board/hypotheses/x.md")")"
check "3 deny: board agent greps the home directory" 2 "$(board Grep "$(grep_in "$HOME")")"
check "3b deny: board agent greps with path ~" 2 "$(board Grep "$(grep_in "~")")"
check "3c deny: board agent greps an ancestor of the working directory" 2 "$(board Grep "$(grep_in "$tmp/proj")")"
check "4 deny: symlink inside the working directory that leads outside" 2 "$(board Read "$(read_of "$work/board-link/hypotheses/x.md")")"
check "5 deny: .env inside the working directory" 2 "$(board Read "$(read_of "$work/.env")")"
check "5b deny: .env.local inside the working directory" 2 "$(board Read "$(read_of "$work/.env.local")")"
check "5c deny: a file under .ssh inside the working directory" 2 "$(board Read "$(read_of "$work/.ssh/id_ed25519")")"
check "6 deny: web search with a figure from the brief" 2 "$(board WebSearch "$(search 'how to grow a $25,000 trading account')")"
check "6b deny: the same figure written without a comma" 2 "$(board WebSearch "$(search '25000 account day trading rules')")"
check "7 allow: web search with no figure from the brief" 0 "$(board WebSearch "$(search 'FINRA intraday margin standards')")"
check "8 allow: a non-board agent reads anywhere" 0 "$(other Explore "$HOME/.config/board/hypotheses/x.md")"
check "9 allow: the main thread, with no agent_type" 0 "$(main_thread "$HOME/.config/board/brief.md")"
check "10 deny: malformed JSON from a board agent" 2 '{"agent_type":"l3a0:board-cfo","tool_name":"Read","tool_input":{"file_path":'
check "11 allow: Grep with no path defaults to the working directory" 0 "$(board Grep '{"pattern":"print"}')"
check "11b allow: Grep on a folder inside the working directory" 0 "$(board Grep "$(grep_in "$work/src")")"
check "12 deny: a sibling directory that shares the working directory's prefix" 2 "$(board Read "$(read_of "$tmp/proj/work2/notes.md")")"
check "13 deny: a relative path that climbs out" 2 "$(board Read "$(read_of "../work2/notes.md")")"
check "14 deny: Glob with an absolute pattern outside" 2 "$(board Glob "$(printf '{"pattern":"%s/.config/board/**/*.md"}' "$HOME")")"
check "14b deny: Glob with a pattern that climbs out" 2 "$(board Glob '{"pattern":"../**/*.md"}')"
check "14c allow: Glob with a relative pattern" 0 "$(board Glob '{"pattern":"src/**/*.py"}')"
check "15 deny: a board agent with no working directory" 2 "$(printf '{"agent_type":"l3a0:board-risk","tool_name":"Read","tool_input":{"file_path":"%s/src/app.py"}}' "$work")"

write_of() { printf '{"file_path":"%s","content":"note"}' "$1"; }
edit_of() { printf '{"file_path":"%s","old_string":"a","new_string":"b"}' "$1"; }
check "20 allow: a seat writes its own memory" 0 "$(board Write "$(write_of "$mem/l3a0-board-cfo/MEMORY.md")")"
check "20b allow: a seat edits its own memory" 0 "$(board Edit "$(edit_of "$mem/l3a0-board-cfo/MEMORY.md")")"
check "21 deny: a seat writes another seat's memory" 2 "$(board Write "$(write_of "$mem/l3a0-board-risk/MEMORY.md")")"
check "22 deny: a seat writes conftest.py in the working directory" 2 "$(board Write "$(write_of "$work/conftest.py")")"
check "23 deny: a seat writes the brief" 2 "$(board Write "$(write_of "$HOME/.config/board/brief.md")")"
printf '' > "$HOME/.config/board/.cross-examination"
check "24 deny: a memory write while cross-examination is under way" 2 "$(board Write "$(write_of "$mem/l3a0-board-cfo/MEMORY.md")")"
mv "$HOME/.config/board/.cross-examination" "$HOME/.config/board/.cross-examination.done"
check "25 allow: a seat reads its own memory" 0 "$(board Read "$(read_of "$mem/l3a0-board-cfo/MEMORY.md")")"
check "25b deny: a seat reads another seat's memory" 2 "$(board Read "$(read_of "$mem/l3a0-board-risk/MEMORY.md")")"
check "26 deny: a symlink inside the memory folder that leads out" 2 "$(board Read "$(read_of "$mem/l3a0-board-cfo/board-link/brief.md")")"
check "26b deny: a write through that symlink" 2 "$(board Write "$(write_of "$mem/l3a0-board-cfo/board-link/brief.md")")"

home=$(cd "$HOME" && pwd -P)
check "19 deny: ~/.config/board when the session runs from the home directory" 2 "$(printf '{"cwd":"%s","agent_type":"l3a0:board-cfo","tool_name":"Read","tool_input":{"file_path":"%s/.config/board/brief.md"}}' "$home" "$home")"

mv "$HOME/.config/board/brief.md" "$HOME/.config/board/brief.md.off"
check "16 allow: web search when the brief is missing" 0 "$(board WebSearch "$(search '25000 account day trading rules')")"
mv "$HOME/.config/board/brief.md.off" "$HOME/.config/board/brief.md"

# With python3 absent from PATH, board agents are blocked and others pass.
mkdir "$tmp/bin"
for tool in sh cat grep dirname; do
  ln -s "$(command -v "$tool")" "$tmp/bin/$tool"
done
nopy() {
  printf '%s' "$3" | PATH="$tmp/bin" sh "$guard" 2>/dev/null
  got=$?
  if [ "$got" -eq "$2" ]; then pass=$((pass + 1)); echo "ok   $1"; else fail=$((fail + 1)); echo "FAIL $1: expected $2, got $got"; fi
}
nopy "17 deny: board agent when python3 is missing" 2 "$(board Read "$(read_of "$work/src/app.py")")"
nopy "18 allow: non-board agent when python3 is missing" 0 "$(other Explore /etc/hosts)"

echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
