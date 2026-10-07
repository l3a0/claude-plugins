#!/bin/sh
# Tests for hooks/board-guard.sh. Each case feeds sample PreToolUse hook input
# on stdin and checks the exit code: 0 allows the call, 2 blocks it.
# Every case runs against a temporary HOME holding a fake brief, never the
# real one. Run from anywhere: sh tests/test_board_guard.sh
#
# The leak test at the end runs real ripgrep the way Claude Code's Grep tool
# does. It finds rg on PATH, or in $RG, or runs Claude Code's own binary
# under the name rg. Set BOARD_TEST_SKIP_RG=1 to skip it where none exists.

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
printf 'LEAKME KEY=1\n' > "$work/.env"
printf 'LEAKME KEY=1\n' > "$work/.env.local"
printf 'LEAKME KEY=1\n' > "$work/.envrc"
printf 'LEAKME key\n' > "$work/.ssh/id_ed25519"
printf 'LEAKME ok\n' > "$work/src/ok.txt"
mkdir -p "$work/sub/.SSH" "$work/sub/.Aws" "$work/sub/.gnupg"
printf 'LEAKME\n' > "$work/sub/.ENVRC"
printf 'LEAKME\n' > "$work/sub/.env_prod"
printf 'LEAKME\n' > "$work/sub/.SSH/id_rsa"
printf 'LEAKME\n' > "$work/sub/.Aws/credentials"
printf 'LEAKME\n' > "$work/sub/.gnupg/key"
printf 'LEAKME fine\n' > "$work/sub/notes.txt"
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
  printf '%s' "$3" | sh "$guard" 2>/dev/null >"$tmp/out"
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

# Review of d31e97c, findings 1 to 7, plus the tool allowlist.
hjson() { printf '{"cwd":"%s","agent_id":"a1","agent_type":"l3a0:board-cfo","tool_name":"%s","tool_input":%s}' "$1" "$2" "$3"; }
check "27 deny: Grep path with a leading space (finding 1)" 2 "$(board Grep "$(grep_in " $HOME/.config/board")")"
check "27b deny: Grep path with a leading tab" 2 "$(board Grep "$(printf '{"pattern":"x","path":"\\t%s/.config/board"}' "$HOME")")"
check "27c deny: Grep path with a leading newline" 2 "$(board Grep "$(printf '{"pattern":"x","path":"\\n%s/.config/board"}' "$HOME")")"
check "27d deny: Grep path with a leading space and a tilde" 2 "$(board Grep "$(grep_in " ~/.config/board")")"
check "27e deny: Glob path with a leading space" 2 "$(board Glob "$(printf '{"pattern":"**/*.md","path":" %s/.config/board"}' "$HOME")")"
check "27f deny: Grep path with a leading byte-order mark" 2 "$(board Grep "$(printf '{"pattern":"x","path":"\\ufeff%s/.config/board"}' "$HOME")")"
check "27g deny: Read file_path with trailing whitespace" 2 "$(board Read "$(read_of "$work/src/app.py ")")"
check "27h deny: Glob pattern with a leading space" 2 "$(board Glob '{"pattern":" **/*.md"}')"
check "27i deny: Grep glob with a trailing non-breaking space" 2 "$(board Grep "$(printf '{"pattern":"x","glob":"*.md\\u00a0"}')")"
check "28 deny: Grep with no path when cwd is the home folder (finding 2)" 2 "$(hjson "$HOME" Grep '{"pattern":"favored"}')"
check "28b deny: Grep with no path when cwd is an ancestor of home" 2 "$(hjson "$tmp" Grep '{"pattern":"favored"}')"
check "28c deny: WebSearch when cwd is the home folder" 2 "$(hjson "$HOME" WebSearch '{"query":"FINRA margin"}')"
check "28d deny: Grep with no path when cwd is ~/.config" 2 "$(hjson "$HOME/.config" Grep '{"pattern":"favored"}')"
check "28e deny: Glob with no path when cwd is ~/.config" 2 "$(hjson "$HOME/.config" Glob '{"pattern":"**/*.md"}')"
check "28f allow: Grep of the seat's own memory folder" 0 "$(board Grep "$(grep_in "$mem/l3a0-board-cfo")")"
check "29 deny: Read of .ENV in cwd (finding 4)" 2 "$(board Read "$(read_of "$work/.ENV")")"
check "29b deny: Read of .SSH/id_ed25519 in cwd" 2 "$(board Read "$(read_of "$work/.SSH/id_ed25519")")"
check "29c deny: Read of .config/BOARD/brief.md from cwd ~/.config" 2 "$(hjson "$HOME/.config" Read "$(read_of "$HOME/.config/BOARD/brief.md")")"
check "29d deny: Read of another seat's memory through a different case" 2 "$(hjson "$HOME/.CLAUDE" Read "$(read_of "$HOME/.CLAUDE/agent-memory/l3a0-board-risk/MEMORY.md")")"
check "29e deny: Read of another seat's memory from cwd ~/.claude" 2 "$(hjson "$HOME/.claude" Read "$(read_of "$mem/l3a0-board-risk/MEMORY.md")")"
check "29f deny: Glob pattern naming .SSH" 2 "$(board Glob '{"pattern":"**/.SSH/*"}')"
check "30 deny: Read of .envrc (finding 5)" 2 "$(board Read "$(read_of "$work/.envrc")")"
check "30b deny: Read of .env-local" 2 "$(board Read "$(read_of "$work/.env-local")")"
check "30c deny: Read of .env_prod" 2 "$(board Read "$(read_of "$work/sub/.env_prod")")"
check "31 deny: figure written as 25 000 (finding 6)" 2 "$(board WebSearch "$(search '25 000 account')")"
check "31b deny: figure written as 25.000" 2 "$(board WebSearch "$(search '25.000 account')")"
check "31c deny: figure written as 25_000" 2 "$(board WebSearch "$(search '25_000 account')")"
check "31d deny: figure written with a typographic apostrophe" 2 "$(board WebSearch "$(search '25’000 account')")"
check "31e deny: figure in full-width digits" 2 "$(board WebSearch "$(search '２５０００ account')")"
check "31f deny: figure with leading zeros" 2 "$(board WebSearch "$(search '0025000 account')")"
check "31g deny: figure with a non-breaking space" 2 "$(board WebSearch "$(printf '{"query":"25\\u00a0000 account"}')")"
check "31h deny: figure with a thin space" 2 "$(board WebSearch "$(printf '{"query":"25\\u2009000 account"}')")"
check "31i allow: scientific notation stays out of reach, as documented" 0 "$(board WebSearch "$(search '2.5e4 account')")"
check "31j allow: a magnitude suffix stays out of reach, as documented" 0 "$(board WebSearch "$(search '25k account')")"
check "32 deny: figure in allowed_domains (finding 7)" 2 "$(board WebSearch '{"query":"margin rules","allowed_domains":["fund25000.example.com"]}')"
check "32b deny: figure in blocked_domains" 2 "$(board WebSearch '{"query":"margin rules","blocked_domains":["x25000.example.com"]}')"
check "33 deny: a board agent calls Bash" 2 "$(board Bash '{"command":"cat ~/.config/board/brief.md"}')"
check "33b deny: a board agent calls REPL" 2 "$(board REPL '{"code":"1"}')"
check "33c deny: a board agent calls WebFetch" 2 "$(board WebFetch '{"url":"https://example.com","prompt":"x"}')"
check "33d deny: a board agent calls an unknown future tool" 2 "$(board FutureTool '{}')"
check "33e allow: a board agent calls ToolSearch" 0 "$(board ToolSearch '{"query":"select:WebSearch"}')"
check "33f allow: a non-board agent calls Bash" 0 "$(printf '{"cwd":"%s","agent_type":"Explore","tool_name":"Bash","tool_input":{"command":"ls"}}' "$work")"

# An allowed Grep comes back with the exclusions appended last.
check "34 allow: Grep with a user glob gets exclusions appended" 0 "$(board Grep '{"pattern":"x","glob":".en[v]"}')"
if python3 -c '
import json, sys
out = json.load(open(sys.argv[1]))["hookSpecificOutput"]
glob = out["updatedInput"]["glob"].split()
assert out["hookEventName"] == "PreToolUse" and "permissionDecision" not in out
assert glob[0] == ".en[v]" and glob[-1].startswith("!**/.[gG]"), glob
' "$tmp/out"; then pass=$((pass + 1)); echo "ok   34b updatedInput keeps the user glob first and the exclusions last"
else fail=$((fail + 1)); echo "FAIL 34b updatedInput shape"; fi

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

# Leak test: run real ripgrep the way Claude Code's Grep tool builds its
# arguments, with and without the guard's exclusions, over secret files.
if [ "${BOARD_TEST_SKIP_RG:-}" = "1" ]; then
  echo "skip 35 real-rg leak test (BOARD_TEST_SKIP_RG=1)"
elif python3 - "$guard" "$work" <<'PY'
import json, os, shutil, subprocess, sys

guard, work = sys.argv[1], sys.argv[2]


def rg_command():
    if os.environ.get("RG"):
        return [os.environ["RG"]], None
    found = shutil.which("rg")
    if found:
        return [found], None
    for claude in (os.environ.get("CLAUDE_CODE_EXECPATH"), os.path.expanduser("~/.local/bin/claude"), shutil.which("claude")):
        if claude and os.access(claude, os.X_OK):
            return ["rg"], claude
    sys.exit("no ripgrep found: install rg, set RG, or set BOARD_TEST_SKIP_RG=1")


def claude_code_rg_args(tool_input):
    # The argument order of Claude Code 2.1.241's Grep tool.
    args = ["--hidden"]
    for vcs in (".git", ".svn", ".hg", ".bzr", ".jj", ".sl"):
        args += ["--glob", "!" + vcs]
    args += ["--max-columns", "500", "-n", tool_input["pattern"]]
    for piece in (tool_input.get("glob") or "").split():
        parts = [piece] if "{" in piece and "}" in piece else [p for p in piece.split(",") if p]
        for part in parts:
            args += ["--glob", part]
    return args


def run_rg(tool_input):
    argv, executable = rg_command()
    path = tool_input.get("path") or work
    result = subprocess.run(argv + claude_code_rg_args(tool_input) + [path], capture_output=True, text=True, cwd=work, executable=executable)
    return result.stdout


def guarded(tool_input):
    hook = {"cwd": work, "agent_id": "a1", "agent_type": "l3a0:board-cfo", "tool_name": "Grep", "tool_input": tool_input}
    result = subprocess.run(["sh", guard], input=json.dumps(hook), capture_output=True, text=True)
    if result.returncode == 2:
        return None
    assert result.returncode == 0, (tool_input, result.returncode, result.stderr)
    return json.loads(result.stdout)["hookSpecificOutput"]["updatedInput"]


SECRETS = (".env", ".envrc", ".env.local", "id_ed25519", ".ENVRC", ".env_prod", "id_rsa", "credentials", "key")
cases = [
    {"pattern": "LEAKME"},
    {"pattern": "LEAKME", "glob": ".en[v]"},
    {"pattern": "LEAKME", "glob": "*"},
    {"pattern": "LEAKME", "glob": "{.env,*.txt,.envrc}"},
    {"pattern": "LEAKME", "glob": "**/.ssh/**"},
    {"pattern": "LEAKME", "path": os.path.join(work, "sub")},
]
failed = 0
baseline = run_rg({"pattern": "LEAKME"})
if not any(name in baseline for name in (".env", "id_ed25519", ".ENVRC")):
    print("FAIL 35 baseline: unguarded rg did not find the secrets, so the test proves nothing")
    failed += 1
for number, case in enumerate(cases, 1):
    updated = guarded(case)
    if updated is None:
        print(f"ok   35.{number} the guard blocks {case} outright")
        continue
    out = run_rg(updated)
    leaked = [line for line in out.splitlines() if os.path.basename(line.split(":", 1)[0]) in SECRETS]
    found_ok = any(line.split(":", 1)[0].endswith(("ok.txt", "notes.txt")) for line in out.splitlines())
    if leaked or (case.get("glob") in (None, "*") and not found_ok):
        print(f"FAIL 35.{number} {case}: leaked {leaked}, found ordinary files {found_ok}")
        failed += 1
    else:
        print(f"ok   35.{number} real rg leaks nothing for {case}")
sys.exit(1 if failed else 0)
PY
then pass=$((pass + 1)); echo "ok   35 real-rg leak test"
else fail=$((fail + 1)); echo "FAIL 35 real-rg leak test"; fi

echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
