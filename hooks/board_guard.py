"""Decide whether an ask-board agent's tool call may run.

board-guard.sh calls this only when the hook input names an agent whose
agent_type starts with "l3a0:board-". Exit 0 allows the call. Exit 2 blocks
it, with the reason on stderr. Any exception also exits 2, so a bug here
blocks a board agent rather than letting its call through. For an allowed
Grep, the script also prints an updatedInput that adds exclusion globs.

The rules:

1. Only the tools in ALLOWED_TOOLS may run. Every other tool is refused,
   including any tool Claude Code adds later.
2. A session whose working directory is the home folder, or an ancestor of
   it, is refused outright. Searching from there would reach every secret.
3. A path or glob pattern that carries leading or trailing whitespace is
   refused. Claude Code trims it before searching, so a padded path would
   pass these checks and then reach a different folder.
4. Read, Grep and Glob may touch only paths inside the session's working
   directory, the cwd field of the hook input, or inside the agent's own
   memory folder. Paths are resolved with realpath first, so a symlink that
   leads outside is refused.
5. Grep and Glob with no path search the working directory. A search whose
   root is ~/.config/board, ~/.claude, ~/.ssh, ~/.aws or ~/.gnupg, or an
   ancestor of one of them, is refused.
6. Names are compared casefolded. Any name starting with .env, anything under
   a .ssh, .aws or .gnupg directory, anything under ~/.config/board, and
   anything under ~/.claude outside the agent's own memory folder is refused.
7. An allowed Grep gets exclusion globs appended, so a recursive search skips
   .env* files and .ssh, .aws and .gnupg folders at any depth.
8. Write and Edit may touch only files inside the agent's own memory folder,
   ~/.claude/agent-memory/<agent_type with every character outside
   [A-Za-z0-9_-] replaced by ->/. While ~/.config/board/.cross-examination
   exists, every Write and Edit is refused, so a seat that has learned which
   option the CEO favors cannot record it.
9. A WebSearch is refused when any string in its input contains a number of
   three or more digits that also appears in ~/.config/board/brief.md. Both
   sides are NFKC-normalised, separators between digits are removed, and
   leading zeros are dropped before comparing. A missing brief allows it.
"""

import json
import os
import re
import sys
import unicodedata

BOARD_PREFIX = "l3a0:board-"

# The six tools a seat uses, plus three that carry no file, shell or network
# access: ToolSearch loads a deferred tool's schema, and SubagentHandback and
# StructuredOutput return the seat's answer to the chair in hosts that use them.
ALLOWED_TOOLS = {
    "Read",
    "Grep",
    "Glob",
    "WebSearch",
    "Write",
    "Edit",
    "ToolSearch",
    "SubagentHandback",
    "StructuredOutput",
}

SECRET_DIRS = {".ssh", ".aws", ".gnupg"}
GLOB_CHARS = re.compile(r"[*?\[{]")

# Every character JavaScript's String.prototype.trim removes.
JS_WHITESPACE = (
    "\t\n\v\f\r          "
    "        　﻿"
)

# Appended to every board agent's Grep. Character classes make each name
# match in any case, because the Grep tool has no --iglob.
GREP_EXCLUSIONS = [
    "!**/.[eE][nN][vV]*",
    "!**/.[sS][sS][hH]",
    "!**/.[sS][sS][hH]/**",
    "!**/.[aA][wW][sS]",
    "!**/.[aA][wW][sS]/**",
    "!**/.[gG][nN][uU][pP][gG]",
    "!**/.[gG][nN][uU][pP][gG]/**",
]

DIGIT_SEPARATOR = re.compile(r"(?<=[0-9])[\s.,_'’](?=[0-9])")
DIGITS = re.compile(r"[0-9]+")


class Denied(Exception):
    pass


def home():
    return os.path.realpath(os.path.expanduser("~"))


def claude_dirs():
    folders = {os.path.join(home(), ".claude")}
    for name in ("CLAUDE_CONFIG_DIR", "CLAUDE_CODE_REMOTE_MEMORY_DIR"):
        if os.environ.get(name):
            folders.add(os.environ[name])
    return [os.path.realpath(folder) for folder in folders]


def board_dir():
    return os.path.realpath(os.path.join(home(), ".config", "board"))


def protected_roots():
    roots = [board_dir()] + claude_dirs()
    roots += [os.path.realpath(os.path.join(home(), name)) for name in sorted(SECRET_DIRS)]
    return roots


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
    """Case-sensitive containment, used for allow checks."""
    return target == root or target.startswith(root.rstrip(os.sep) + os.sep)


def inside_cf(target, root):
    """Casefolded containment, used for deny checks."""
    return inside(target.casefold(), root.casefold())


def check_trim(value, field):
    if isinstance(value, str) and (value != value.strip(JS_WHITESPACE) or value != value.strip()):
        raise Denied(f"the {field} has leading or trailing whitespace")


def is_env_name(name):
    return name.casefold().startswith(".env")


def check_target(target, own, raw):
    """Refuse a resolved path that names a protected folder or a secret file."""
    if inside_cf(target, board_dir()):
        raise Denied(f"{raw} is inside ~/.config/board")
    for folder in claude_dirs():
        if inside_cf(target, folder) and not inside(target, own):
            raise Denied(f"{raw} is inside ~/.claude but outside this agent's own memory folder")
    for name in SECRET_DIRS:
        if inside_cf(target, os.path.join(home(), name)):
            raise Denied(f"{raw} is inside ~/{name}")


def check_path(raw, root, allowed, own, field="path"):
    """Resolve raw against root and refuse it unless it stays inside an allowed folder."""
    if not isinstance(raw, str) or raw == "":
        raise Denied(f"the {field} is missing or not a string")
    check_trim(raw, field)
    target = os.path.realpath(os.path.join(root, os.path.expanduser(raw)))
    base = next((folder for folder in allowed if inside(target, folder)), None)
    if base is None:
        raise Denied(f"{raw} resolves outside the folders this agent may use")
    check_target(target, own, raw)
    parts = os.path.relpath(target, base).split(os.sep)
    for part in parts:
        if part.casefold() in SECRET_DIRS:
            raise Denied(f"{raw} is under a {part} directory")
        if is_env_name(part):
            raise Denied(f"{raw} names an environment file")
    return target


def check_search_root(search_root, raw):
    """Refuse a Grep or Glob whose root contains a protected folder."""
    for protected in protected_roots():
        if inside_cf(protected, search_root):
            raise Denied(f"searching {raw} would reach {protected}")


def check_pattern(pattern, root, allowed, own, field):
    """Refuse a glob pattern that climbs out, names a secret, or roots a search too high."""
    if pattern is None or pattern == "":
        return
    if not isinstance(pattern, str):
        raise Denied(f"the {field} is not a string")
    check_trim(pattern, field)
    pieces = pattern.replace("\\", "/").split("/")
    if ".." in pieces:
        raise Denied(f"the {field} {pattern} climbs out with ..")
    for piece in pieces:
        if piece.casefold() in SECRET_DIRS:
            raise Denied(f"the {field} {pattern} names a {piece} directory")
    name = pieces[-1] if pieces[-1] else (pieces[-2] if len(pieces) > 1 else "")
    if is_env_name(name):
        raise Denied(f"the {field} {pattern} names an environment file")
    expanded = os.path.expanduser(pattern)
    if os.path.isabs(expanded):
        prefix = GLOB_CHARS.split(expanded, maxsplit=1)[0]
        base = os.path.dirname(prefix) or os.sep
        target = check_path(base, root, allowed, own, field)
        check_search_root(target, pattern)


def ascii_digits(text):
    out = []
    for char in text:
        if char.isdecimal() and not "0" <= char <= "9":
            out.append(str(unicodedata.decimal(char)))
        else:
            out.append(char)
    return "".join(out)


def figures(text):
    """Every number of three or more digits in text, in raw and joined forms."""
    normal = ascii_digits(unicodedata.normalize("NFKC", text))
    found = set()
    for variant in (normal, DIGIT_SEPARATOR.sub("", normal)):
        for run in DIGITS.findall(variant):
            run = run.lstrip("0")
            if len(run) >= 3:
                found.add(run)
    return found


def strings_in(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from strings_in(key)
            yield from strings_in(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings_in(item)


def check_search(tool_input):
    if not isinstance(tool_input.get("query"), str):
        raise Denied("the search query is missing")
    brief = os.path.join(os.path.expanduser("~"), ".config", "board", "brief.md")
    try:
        with open(brief, encoding="utf-8") as handle:
            secret = figures(handle.read())
    except FileNotFoundError:
        return
    for text in strings_in(tool_input):
        if figures(text) & secret:
            raise Denied("the search contains a figure from the brief")


def decide(data):
    """Return None to allow, or a replacement tool input to allow with changes."""
    agent = data.get("agent_type")
    if not isinstance(agent, str) or not agent.startswith(BOARD_PREFIX):
        return None
    tool = data.get("tool_name")
    if tool not in ALLOWED_TOOLS:
        raise Denied(f"board agents may not use {tool}")
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        raise Denied("the tool input is missing")
    cwd = data.get("cwd")
    if not isinstance(cwd, str) or not os.path.isabs(cwd):
        raise Denied("the working directory is missing")
    root = os.path.realpath(cwd)
    if inside_cf(home(), root):
        raise Denied("the session runs from the home folder or above it. Start the sitting from a project folder")
    if tool == "WebSearch":
        check_search(tool_input)
        return None
    if tool not in ("Read", "Grep", "Glob", "Write", "Edit"):
        return None
    own = memory_dir(agent)
    if tool in ("Write", "Edit"):
        if os.path.lexists(marker()):
            raise Denied("cross-examination is under way, so no board agent may write")
        check_path(tool_input.get("file_path"), root, [own], own, "file_path")
        return None
    allowed = [root, own]
    if tool == "Read":
        check_path(tool_input.get("file_path"), root, allowed, own, "file_path")
        return None
    raw = tool_input.get("path")
    if raw in (None, ""):
        search_root = root
    else:
        search_root = check_path(raw, root, allowed, own)
    check_search_root(search_root, raw or cwd)
    key = "pattern" if tool == "Glob" else "glob"
    check_pattern(tool_input.get(key), root, allowed, own, key)
    if tool == "Grep":
        updated = dict(tool_input)
        current = updated.get("glob") or ""
        updated["glob"] = " ".join(part for part in [current, *GREP_EXCLUSIONS] if part)
        return updated
    return None


def main():
    try:
        updated = decide(json.loads(sys.stdin.read()))
    except Denied as reason:
        sys.stderr.write(
            f"ask-board guard: {reason}. Board agents may read only inside the working directory "
            "and their own memory folder, and write only inside that memory folder.\n"
        )
        return 2
    except Exception as error:  # noqa: BLE001
        sys.stderr.write(f"ask-board guard: blocked after an internal error ({type(error).__name__}).\n")
        return 2
    if updated is not None:
        sys.stdout.write(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "updatedInput": updated}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
