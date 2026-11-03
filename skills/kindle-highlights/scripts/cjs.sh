#!/bin/bash
# Run JavaScript in one Chrome tab through AppleScript and print what it returns.
#
#   cjs.sh WINDOW_ID TAB_ID FILE.js     run a file's JavaScript in that tab
#   cjs.sh WINDOW_ID TAB_ID -e 'EXPR'   run one expression, such as a poll: -e 'JSON.stringify(window.__pg)'
#   cjs.sh --list                       print "window id, tab id, URL" for every Chrome tab
#
# This is the route when the browser-control tools cannot run JavaScript, such as when the Claude-in-Chrome
# extension's javascript_tool fails or is blocked. It needs Chrome's View > Developer > Allow JavaScript from
# Apple Events, and the macOS Automation grant for the terminal to control Chrome. Either one lets any process
# run JavaScript in any tab, so it refuses a tab whose URL is not on https://read.amazon.com/, and it never
# launches Chrome. Undo both after the run (SKILL.md, Step 6).
#
# `execute` returns only a synchronous value, so an async script stores its result on window and a second call
# polls for it. Return strings, such as JSON.stringify(...), because AppleScript mangles objects.
set -euo pipefail

if [ "${1:-}" = "--list" ]; then
  exec osascript <<'AS'
if application "Google Chrome" is not running then error "Google Chrome is not running"
set out to ""
tell application "Google Chrome"
  repeat with w in windows
    repeat with t in tabs of w
      set out to out & (id of w) & ", " & (id of t) & ", " & (URL of t) & linefeed
    end repeat
  end repeat
end tell
return out
AS
fi

[ $# -eq 3 ] || [ $# -eq 4 ] || { sed -n '2,9p' "$0" >&2; exit 2; }
if [ "$3" = "-e" ]; then
  mode=expr src=${4:?-e needs an expression}
else
  mode=file src=$3
  [ -f "$src" ] || { echo "no such file: $src" >&2; exit 2; }
  src=$(cd "$(dirname "$src")" && pwd)/$(basename "$src")
fi

# A file is read as UTF-8 inside AppleScript, so curly quotes and other non-ASCII text in it arrive intact.
osascript - "$1" "$2" "$mode" "$src" <<'AS'
on run argv
  set w to (item 1 of argv) as integer
  set t to (item 2 of argv) as integer
  if item 3 of argv is "file" then
    set js to read POSIX file (item 4 of argv) as «class utf8»
  else
    set js to item 4 of argv
  end if
  if application "Google Chrome" is not running then error "Google Chrome is not running"
  tell application "Google Chrome"
    set u to URL of tab id t of window id w
    if u does not start with "https://read.amazon.com/" then error "refused: tab " & (item 2 of argv) & " is on " & u
    return execute (tab id t of window id w) javascript js
  end tell
end run
AS
