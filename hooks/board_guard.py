"""Decide whether an ask-board agent's Read, Grep, Glob, WebSearch, Write or Edit call may run.

board-guard.sh calls this only when the hook input names an agent whose
agent_type starts with "l3a0:board-". Exit 0 allows the call. Exit 2 blocks
it, with the reason on stderr. Any exception also exits 2, so a bug here
blocks a board agent rather than letting its call through.

The rules:

1. Read, Grep and Glob may touch only paths inside the session's working
   directory, the cwd field of the hook input, or inside the agent's own
   memory folder. Paths are resolved with realpath first, so a symlink that
   leads outside is refused.
2. Grep and Glob with no path default to the working directory.
3. Inside those folders, .env and .env.* files, anything under a .ssh, .aws
   or .gnupg directory, and anything under ~/.config/board are refused.
4. Write and Edit may touch only files inside the agent's own memory folder,
   ~/.claude/agent-memory/<agent_type with every character outside
   [A-Za-z0-9_-] replaced by ->/. While ~/.config/board/.cross-examination
   exists, every Write and Edit is refused, so a seat that has learned which
   option the CEO favors cannot record it.
5. A WebSearch query is refused when it contains a number of three or more
   digits that also appears in ~/.config/board/brief.md. Commas and currency
   signs are ignored. A missing brief allows the query.
"""

import json
import os
import re
import sys

BOARD_PREFIX = "l3a0:board-"
SECRET_DIRS = {".ssh", ".aws", ".gnupg"}
GLOB_CHARS = re.compile(r"[*?\[{]")
NUMBER = re.compile(r"\d{3,}")
STRIP = re.compile(r"[,$€£¥]")


class Denied(Exception):
    pass


def board_dir():
    return os.path.realpath(os.path.join(os.path.expanduser("~"), ".config", "board"))


def memory_dir(agent):
    """The folder Claude Code gives an agent with memory: user."""
    base = (
        os.environ.get("CLAUDE_CODE_REMOTE_MEMORY_DIR")
        or os.environ.get("CLAUDE_CONFIG_DIR")
        or os.path.join(os.path.expanduser("~"), ".claude")
    )
    name = re.sub(r"[^A-Za-z0-9_-]", "-", agent) or "unknown"
    return os.path.realpath(os.path.join(base, "agent-memory", name))


def marker():
    return os.path.join(os.path.expanduser("~"), ".config", "board", ".cross-examination")


def inside(target, root):
    return target == root or target.startswith(root.rstrip(os.sep) + os.sep)


def check_path(raw, root, allowed):
    """Resolve raw against root and refuse it unless it stays inside an allowed folder."""
    if not isinstance(raw, str) or raw == "":
        raise Denied("the path is missing or not a string")
    path = os.path.expanduser(raw)
    target = os.path.realpath(os.path.join(root, path))
    home = next((folder for folder in allowed if inside(target, folder)), None)
    if home is None:
        raise Denied(f"{raw} resolves outside the folders this agent may use")
    if inside(target, board_dir()):
        raise Denied(f"{raw} is inside ~/.config/board")
    parts = os.path.relpath(target, home).split(os.sep)
    for part in parts:
        if part in SECRET_DIRS:
            raise Denied(f"{raw} is under a {part} directory")
    name = parts[-1]
    if name == ".env" or name.startswith(".env."):
        raise Denied(f"{raw} is an environment file")
    return target


def check_pattern(pattern, root, allowed):
    """Refuse a glob pattern that climbs out of root or names a secret file."""
    if pattern is None or pattern == "":
        return
    if not isinstance(pattern, str):
        raise Denied("the pattern is not a string")
    if ".." in pattern.replace("\\", "/").split("/"):
        raise Denied(f"the pattern {pattern} climbs out with ..")
    expanded = os.path.expanduser(pattern)
    if os.path.isabs(expanded):
        prefix = GLOB_CHARS.split(expanded, maxsplit=1)[0]
        check_path(os.path.dirname(prefix) or os.sep, root, allowed)
    name = expanded.replace("\\", "/").rstrip("/").split("/")[-1]
    if name == ".env" or name.startswith(".env."):
        raise Denied(f"the pattern {pattern} names an environment file")
    for part in expanded.replace("\\", "/").split("/"):
        if part in SECRET_DIRS:
            raise Denied(f"the pattern {pattern} names a {part} directory")


def numbers(text):
    return set(NUMBER.findall(STRIP.sub("", text)))


def check_search(tool_input):
    query = tool_input.get("query")
    if not isinstance(query, str):
        raise Denied("the search query is missing")
    brief = os.path.join(os.path.expanduser("~"), ".config", "board", "brief.md")
    try:
        with open(brief, encoding="utf-8") as handle:
            text = handle.read()
    except FileNotFoundError:
        return
    shared = numbers(query) & numbers(text)
    if shared:
        raise Denied("the query contains a figure from the brief")


def decide(data):
    agent = data.get("agent_type")
    if not isinstance(agent, str) or not agent.startswith(BOARD_PREFIX):
        return
    tool = data.get("tool_name")
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        raise Denied("the tool input is missing")
    if tool == "WebSearch":
        check_search(tool_input)
        return
    if tool not in ("Read", "Grep", "Glob", "Write", "Edit"):
        return
    cwd = data.get("cwd")
    if not isinstance(cwd, str) or not os.path.isabs(cwd):
        raise Denied("the working directory is missing")
    root = os.path.realpath(cwd)
    own = memory_dir(agent)
    if tool in ("Write", "Edit"):
        if os.path.lexists(marker()):
            raise Denied("cross-examination is under way, so no board agent may write")
        check_path(tool_input.get("file_path"), root, [own])
        return
    allowed = [root, own]
    if tool == "Read":
        check_path(tool_input.get("file_path"), root, allowed)
        return
    raw = tool_input.get("path")
    if raw not in (None, ""):
        check_path(raw, root, allowed)
    key = "pattern" if tool == "Glob" else "glob"
    check_pattern(tool_input.get(key), root, allowed)


def main():
    try:
        decide(json.loads(sys.stdin.read()))
    except Denied as reason:
        sys.stderr.write(f"ask-board guard: {reason}. Board agents may read only inside the working directory and their own memory folder, and write only inside that memory folder.\n")
        return 2
    except Exception as error:  # noqa: BLE001
        sys.stderr.write(f"ask-board guard: blocked after an internal error ({type(error).__name__}).\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
