#!/bin/bash
# Run JavaScript in one Chrome tab on read.amazon.com through AppleScript and print what it returns.
#
#   cjs.sh WINDOW_ID TAB_ID FILE.js     run a file's JavaScript in that tab
#   cjs.sh WINDOW_ID TAB_ID -e 'EXPR'   run one expression, such as a poll: -e 'JSON.stringify(window.__pg)'
#   cjs.sh --list                       print "window id, tab id, URL" for each read.amazon.com tab
#
# This is the route when the Claude-in-Chrome extension's javascript_tool fails with "Cannot access a
# chrome-extension:// URL of different extension" (SKILL.md, The one prerequisite). A permission the owner
# refused, or a policy that blocks the browser tool, is the owner's to lift, and this script is no way around it.
#
# It needs Chrome's View > Developer > Allow JavaScript from Apple Events and the macOS Automation grant for the
# terminal to control Chrome. Together they let any process holding the grant run JavaScript in any tab, so
# this script runs only in a tab on https://read.amazon.com/, and never launches Chrome. It checks the tab's URL
# before sending the script, and the script itself starts with GUARD below, which throws unless the page that
# runs it is on that origin, so a navigation between the two steps cannot redirect it. Undo both settings after
# the run (SKILL.md, Step 6).
#
# `execute` returns only a synchronous value, so an async script stores its result on window and a second call
# polls for it. Return strings, such as JSON.stringify(...), because AppleScript mangles objects.
set -euo pipefail

GUARD='if (location.origin !== "https://read.amazon.com") throw new Error("refused: not on read.amazon.com");'

if [ "${1:-}" = "--list" ]; then
  exec osascript <<'AS'
if application "Google Chrome" is not running then error "Google Chrome is not running"
set out to ""
tell application "Google Chrome"
  repeat with w in windows
    repeat with t in tabs of w
      if (URL of t) starts with "https://read.amazon.com/" then
        set out to out & (id of w) & ", " & (id of t) & ", " & (URL of t) & linefeed
      end if
    end repeat
  end repeat
end tell
return out
AS
fi

[ $# -eq 3 ] || [ $# -eq 4 ] || { sed -n '2,6p' "$0" >&2; exit 2; }
if [ "$3" = "-e" ]; then
  mode=expr src=${4:?-e needs an expression}
else
  mode=file src=$3
  [ -f "$src" ] || { echo "no such file: $src" >&2; exit 2; }
  src=$(cd "$(dirname "$src")" && pwd)/$(basename "$src")
fi

# A file is read as UTF-8 inside AppleScript, so curly quotes and other non-ASCII text in it arrive intact.
osascript - "$1" "$2" "$mode" "$src" "$GUARD" <<'AS'
on run argv
  set w to (item 1 of argv) as integer
  set t to (item 2 of argv) as integer
  if item 3 of argv is "file" then
    set js to read POSIX file (item 4 of argv) as «class utf8»
  else
    set js to item 4 of argv
  end if
  set js to (item 5 of argv) & linefeed & js
  if application "Google Chrome" is not running then error "Google Chrome is not running"
  tell application "Google Chrome"
    if (URL of tab id t of window id w) does not start with "https://read.amazon.com/" then
      error "refused: tab " & (item 2 of argv) & " is not on https://read.amazon.com/"
    end if
    return execute (tab id t of window id w) javascript js
  end tell
end run
AS
